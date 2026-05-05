/**
 * ViFake Analytics — Background Service Worker
 * Handles API communication, state management, badge updates
 */

const DEFAULT_API_URL = 'https://vifake-analytics-api.onrender.com';
const DEFAULT_AUTH_TOKEN = 'demo-token-123';
const LOCAL_API_URL = 'http://localhost:8000';

// ─── State ───
let apiUrl = DEFAULT_API_URL;
let authToken = DEFAULT_AUTH_TOKEN;
let recentScans = [];
const MAX_RECENT = 20;

// ─── Init ───
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({
    apiUrl: DEFAULT_API_URL,
    authToken: DEFAULT_AUTH_TOKEN,
    autoScan: false,
    recentScans: [],
    totalScans: 0,
    scamDetected: 0,
  });

  // Register right-click context menu
  chrome.contextMenus.create({
    id: 'vifake-scan-post',
    title: '🛡️ Quét bài viết với ViFake',
    contexts: ['page', 'selection', 'image', 'video', 'link'],
  });

  console.log('[ViFake] Extension installed');
});

// Handle right-click menu click
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== 'vifake-scan-post') return;
  if (!tab?.id) return;
  // Send message to content script to scan from last right-clicked element
  chrome.tabs.sendMessage(tab.id, {
    action: 'scanFromContextMenu',
    selectionText: info.selectionText || '',
  }).catch(err => console.error('[ViFake] Failed to send context menu message:', err));
});

// Load settings on startup
chrome.storage.local.get(['apiUrl', 'authToken', 'recentScans'], (data) => {
  apiUrl = data.apiUrl || DEFAULT_API_URL;
  authToken = data.authToken || DEFAULT_AUTH_TOKEN;
  recentScans = data.recentScans || [];

  // Ensure defaults are persisted (for users who installed before defaults existed)
  const toSet = {};
  if (!data.apiUrl) toSet.apiUrl = DEFAULT_API_URL;
  if (!data.authToken) toSet.authToken = DEFAULT_AUTH_TOKEN;
  if (Object.keys(toSet).length > 0) chrome.storage.local.set(toSet);
});

// ─── Message Handler ───
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'analyze') {
    handleAnalyze(msg.payload, sender.tab?.id)
      .then(sendResponse)
      .catch(err => sendResponse({ error: err.message }));
    return true; // async response
  }

  if (msg.action === 'getStatus') {
    chrome.storage.local.get(['apiUrl', 'authToken', 'totalScans', 'scamDetected', 'recentScans'], sendResponse);
    return true;
  }

  if (msg.action === 'updateSettings') {
    chrome.storage.local.set(msg.settings, () => {
      apiUrl = msg.settings.apiUrl || apiUrl;
      authToken = msg.settings.authToken || authToken;
      sendResponse({ ok: true });
    });
    return true;
  }

  if (msg.action === 'getRecentScans') {
    chrome.storage.local.get(['recentScans'], (data) => {
      sendResponse(data.recentScans || []);
    });
    return true;
  }
});

// ─── Core: Analyze ───
async function handleAnalyze(payload, tabId) {
  const { text, url, platform } = payload;

  if (!text || text.trim().length < 10) {
    return { error: 'Nội dung quá ngắn để phân tích' };
  }

  // Update badge to scanning
  if (tabId) {
    chrome.action.setBadgeText({ text: '...', tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#6366f1', tabId });
  }

  try {
    // Load current settings
    const settings = await getStorage(['apiUrl', 'authToken']);
    const currentApiUrl = settings.apiUrl || DEFAULT_API_URL;
    const currentToken = settings.authToken || 'demo-token-123';

    // Step 1: Submit analysis job
    const submitRes = await fetch(`${currentApiUrl}/api/v1/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${currentToken}`,
      },
      body: JSON.stringify({
        url: url || 'https://facebook.com/unknown',
        platform: platform || 'facebook',
        priority: 'high',
        content: text,
      }),
    });

    if (!submitRes.ok) {
      const errBody = await submitRes.text();
      throw new Error(`API error ${submitRes.status}: ${errBody}`);
    }

    const submitData = await submitRes.json();
    const jobId = submitData.job_id;

    // Step 2: Poll for result
    const result = await pollForResult(currentApiUrl, currentToken, jobId);

    // Step 3: Store result
    const scanRecord = {
      id: jobId,
      text: text.substring(0, 100) + (text.length > 100 ? '...' : ''),
      result: result,
      timestamp: Date.now(),
      platform: platform || 'facebook',
    };

    await addRecentScan(scanRecord);

    // Step 4: Update badge
    if (tabId) {
      updateBadge(tabId, result);
    }

    return result;
  } catch (err) {
    console.error('[ViFake] Analysis failed:', err);
    if (tabId) {
      chrome.action.setBadgeText({ text: '!', tabId });
      chrome.action.setBadgeBackgroundColor({ color: '#ef4444', tabId });
    }
    return { error: err.message };
  }
}

// ─── Poll for Job Result ───
async function pollForResult(baseUrl, token, jobId, maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    await sleep(1000);

    try {
      const res = await fetch(`${baseUrl}/api/v1/job/${jobId}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (!res.ok) continue;

      const data = await res.json();

      if (data.status === 'completed' && data.result) {
        return data.result;
      }
      if (data.status === 'failed') {
        throw new Error(data.error || 'Analysis failed on server');
      }
    } catch (err) {
      if (i === maxAttempts - 1) throw err;
    }
  }

  throw new Error('Analysis timed out');
}

// ─── Badge ───
function updateBadge(tabId, result) {
  const label = result.label || result.prediction || 'UNKNOWN';

  const badgeMap = {
    'SAFE':       { text: '✓', color: '#22c55e' },
    'SUSPICIOUS': { text: '?', color: '#f59e0b' },
    'FAKE_SCAM':  { text: '✗', color: '#ef4444' },
    'TOXIC':      { text: '✗', color: '#ef4444' },
  };

  const badge = badgeMap[label] || { text: '?', color: '#6b7280' };
  chrome.action.setBadgeText({ text: badge.text, tabId });
  chrome.action.setBadgeBackgroundColor({ color: badge.color, tabId });
}

// ─── Storage Helpers ───
function getStorage(keys) {
  return new Promise(resolve => chrome.storage.local.get(keys, resolve));
}

async function addRecentScan(record) {
  const data = await getStorage(['recentScans', 'totalScans', 'scamDetected']);
  const scans = data.recentScans || [];
  scans.unshift(record);
  if (scans.length > MAX_RECENT) scans.pop();

  const total = (data.totalScans || 0) + 1;
  const label = record.result?.label || record.result?.prediction || '';
  const scamCount = (data.scamDetected || 0) + (label === 'FAKE_SCAM' || label === 'TOXIC' ? 1 : 0);

  await chrome.storage.local.set({
    recentScans: scans,
    totalScans: total,
    scamDetected: scamCount,
  });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
