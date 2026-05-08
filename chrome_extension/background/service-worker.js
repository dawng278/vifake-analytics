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

// ─── Notification helpers ───
function sendDangerNotification({ title, message, tabId, url }) {
  const notifId = `vifake-${Date.now()}`;
  chrome.notifications.create(notifId, {
    type: 'basic',
    iconUrl: chrome.runtime.getURL('icons/icon48.png'),
    title,
    message,
    priority: 2,
  });
  // Clicking notification focuses the tab
  chrome.notifications.onClicked.addListener(function handler(id) {
    if (id !== notifId) return;
    chrome.notifications.onClicked.removeListener(handler);
    if (tabId) chrome.tabs.update(tabId, { active: true });
  });
}

function maybeNotify(label, verdict, tabId, url) {
  const effective = verdict || label;
  if (effective === 'FAKE_SCAM') {
    sendDangerNotification({
      title: '🚨 ViFake: Phát hiện lừa đảo!',
      message: 'Nội dung này có dấu hiệu lừa đảo nhắm vào trẻ em. Nhấn để xem chi tiết.',
      tabId, url,
    });
  } else if (effective === 'SUSPICIOUS') {
    sendDangerNotification({
      title: '⚠️ ViFake: Nội dung đáng ngờ',
      message: 'Phát hiện nội dung có dấu hiệu đáng ngờ trên trang này.',
      tabId, url,
    });
  }
}

// ─── Message Handler ───
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'analyze') {
    handleAnalyze(msg.payload, sender.tab?.id)
      .then(sendResponse)
      .catch(err => sendResponse({ error: err.message }));
    return true; // async response
  }

  if (msg.action === 'analyze_video') {
    handleAnalyzeVideo(msg.payload, sender.tab?.id)
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

  if (msg.action === 'clearHistory') {
    chrome.storage.local.set({ recentScans: [], totalScans: 0, scamDetected: 0 }, () => {
      sendResponse({ ok: true });
    });
    return true;
  }
});

// ─── Core: Analyze ───
async function handleAnalyze(payload, tabId) {
  const { text, url, platform, images } = payload;  // P2-A: destructure images

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
        ...(images && images.length > 0 ? { images } : {}),  // P2-A: include images when present
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

    // Step 4: Update badge + notification
    if (tabId) {
      updateBadge(tabId, result);
    }
    maybeNotify(result.label, result.prediction, tabId, url);

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
// P2-C: adaptive delay — fast first polls (backend ~330ms), slower backoff after
async function pollForResult(baseUrl, token, jobId, maxAttempts = 25) {
  for (let i = 0; i < maxAttempts; i++) {
    // Adaptive delay: 200ms → 500ms → 800ms
    const delay = i === 0 ? 200 : i <= 3 ? 500 : 800;
    await sleep(delay);

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

// ─── Core: Analyze Video (TikTok) ───
async function handleAnalyzeVideo(payload, tabId) {
  const { video_url, description, author, page_url } = payload;

  if (!video_url) {
    return { error: 'Không lấy được URL video. Thử reload trang.' };
  }

  // Update badge to scanning
  if (tabId) {
    chrome.action.setBadgeText({ text: '...', tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#3b82f6', tabId });
  }

  try {
    // Step 1: Start video analysis job
    const response = await fetch(`${apiUrl}/api/v1/analyze/video`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        video_url,
        description,
        author,
        page_url,
      }),
    });

    if (!response.ok) {
      let errDetail = `HTTP ${response.status}`;
      try {
        const errBody = await response.json();
        // FastAPI wraps errors as {"detail": "..."}
        errDetail = errBody.detail || errBody.message || errDetail;
      } catch {
        errDetail = await response.text().catch(() => errDetail);
      }
      console.error(`[ViFake] Video API error ${response.status}:`, errDetail);
      // 5xx = server error → return friendly message, don't throw
      if (response.status >= 500) {
        return { error: `Lỗi máy chủ (${response.status}): ${errDetail}` };
      }
      throw new Error(errDetail);
    }

    const result = await response.json();

    // Step 2: Record scan
    const scanRecord = {
      url: page_url,
      platform: 'tiktok',
      result: {
        label: result.verdict,
        prediction: result.verdict,
        confidence: result.confidence,
        risk_level: result.risk_level || 'MEDIUM',
        analysis_details: {
          is_ai_generated: result.is_ai_generated,
          ai_confidence: result.ai_confidence,
          transcript: result.transcript,
          explanation: result.explanation,
          intents: result.intents,
        }
      },
      timestamp: Date.now(),
      platform: 'tiktok',
    };

    await addRecentScan(scanRecord);

    // Step 3: Update badge + notification
    if (tabId) {
      updateVideoBadge(tabId, result);
    }
    maybeNotify(result.verdict, null, tabId, page_url);
    if (tabId) {
    }

    return result;
  } catch (err) {
    console.error('[ViFake] Video analysis failed:', err);
    if (tabId) {
      chrome.action.setBadgeText({ text: '!', tabId });
      chrome.action.setBadgeBackgroundColor({ color: '#ef4444', tabId });
    }
    return { error: err.message };
  }
}

// ─── Video Badge Updates ───
function updateVideoBadge(tabId, result) {
  const verdict = result.verdict || 'UNKNOWN';

  const badgeMap = {
    'SAFE':       { text: '✓', color: '#22c55e' },
    'SUSPICIOUS': { text: '?', color: '#f59e0b' },
    'FAKE_SCAM':  { text: '✗', color: '#ef4444' },
  };

  const badge = badgeMap[verdict] || { text: '?', color: '#6b7280' };
  chrome.action.setBadgeText({ text: badge.text, tabId });
  chrome.action.setBadgeBackgroundColor({ color: badge.color, tabId });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
