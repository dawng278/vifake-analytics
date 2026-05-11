/**
 * ViFake Analytics — Popup Logic
 */

document.addEventListener('DOMContentLoaded', init);

const PLATFORM_ICON = { facebook: '📘', youtube: '▶️', tiktok: '🎵', unknown: '🌐' };
const LABEL_META = {
  SAFE:       { cls: 'safe',    text: 'An toàn',        icon: '✅' },
  SUSPICIOUS: { cls: 'warn',    text: 'Đáng ngờ',       icon: '⚠️' },
  FAKE_SCAM:  { cls: 'danger',  text: 'Lừa đảo',        icon: '🚨' },
  TOXIC:      { cls: 'danger',  text: 'Độc hại',         icon: '🚨' },
  UNKNOWN:    { cls: 'neutral', text: 'Không xác định', icon: '❓' },
};

function init() {
  loadStatus();
  loadRecentScans();
  setupTabs();
  setupSettings();
  setupClearHistory();
}

// ─── Status & Stats ───
async function loadStatus() {
  try {
    const data = await sendMessage({ action: 'getStatus' });
    const totalScans  = data.totalScans  || 0;
    const scamDetected = data.scamDetected || 0;
    const safeCount   = Math.max(0, totalScans - scamDetected);

    document.getElementById('totalScans').textContent   = totalScans;
    document.getElementById('scamDetected').textContent = scamDetected;
    document.getElementById('safeCount').textContent    = safeCount;

    // Check API connection
    const apiUrl = data.apiUrl || 'https://vifake-analytics-api.onrender.com';

    try {
      const res = await fetch(`${apiUrl}/api/v1/health`, {
        signal: AbortSignal.timeout(5000),
      });
      const dot = document.getElementById('statusDot');
      if (res.ok) {
        dot.classList.add('online');
        dot.classList.remove('offline');
        dot.title = 'API đang hoạt động';
      } else {
        dot.classList.add('offline');
        dot.classList.remove('online');
        dot.title = `API lỗi: HTTP ${res.status}`;
      }
    } catch {
      const dot = document.getElementById('statusDot');
      dot.classList.add('offline');
      dot.classList.remove('online');
      dot.title = 'Không kết nối được API';
    }
  } catch (err) {
    console.error('[ViFake] Load status failed:', err);
  }
}

// ─── Recent Scans ───
async function loadRecentScans() {
  try {
    const scans  = await sendMessage({ action: 'getRecentScans' });
    const listEl = document.getElementById('recentList');
    const countEl = document.getElementById('recentCount');

    if (!scans || scans.length === 0) {
      if (countEl) countEl.textContent = '';
      listEl.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🛡️</div>
          <p>Chưa có kết quả quét nào.</p>
          <p class="hint">Mở Facebook, YouTube hoặc TikTok và nhấn nút <strong>Kiểm tra ViFake</strong> dưới bài đăng.</p>
        </div>`;
      return;
    }

    if (countEl) countEl.textContent = `${scans.length} kết quả`;

    listEl.innerHTML = scans.map(scan => {
      const result  = scan.result || {};
      const label   = result.label || result.prediction || 'UNKNOWN';
      const meta    = LABEL_META[label] || { cls: 'warn', text: label, icon: '❓' };
      const conf    = result.confidence || 0;
      const confPct = Math.round(conf * 100);
      const platform = scan.platform || 'unknown';
      const platIcon = PLATFORM_ICON[platform] || PLATFORM_ICON.unknown;
      const time     = formatTime(scan.timestamp);

      // Intent summary (top intent only)
      const details = result.analysis_details || {};
      const intents = details.intent || result.intents || {};
      const intentNames = {
        credential_harvest: 'Thu thập thông tin',
        money_transfer:     'Chuyển tiền',
        urgency_pressure:   'Áp lực khẩn cấp',
        fake_reward:        'Phần thưởng giả',
        grooming_isolation: 'Tiếp cận trẻ em',
      };
      let topIntent = '';
      let topScore  = 0;
      for (const [k, v] of Object.entries(intents)) {
        if (typeof v === 'number' && v > topScore) { topScore = v; topIntent = intentNames[k] || k; }
      }

      // Transcript excerpt for TikTok
      const transcript = details.transcript || result.transcript || '';
      const transcriptExcerpt = transcript.length > 80
        ? transcript.substring(0, 80) + '…'
        : transcript;

      const confColor = label === 'SAFE' ? '#22c55e' : label === 'SUSPICIOUS' ? '#f59e0b' : '#ef4444';

      return `
        <div class="scan-item">
          <div class="scan-item-header">
            <span class="scan-platform" title="${platform}">${platIcon}</span>
            <span class="scan-label ${meta.cls}">${meta.icon} ${meta.text}</span>
            <span class="scan-time">${time}</span>
          </div>
          <div class="scan-conf-row">
            <div class="scan-conf-track">
              <div class="scan-conf-fill" style="width:${confPct}%;background:${confColor}"></div>
            </div>
            <span class="scan-conf-pct">${confPct}%</span>
          </div>
          ${scan.text ? `<div class="scan-text">${escapeHtml(scan.text)}</div>` : ''}
          ${transcriptExcerpt ? `<div class="scan-transcript">🎙 ${escapeHtml(transcriptExcerpt)}</div>` : ''}
          ${topIntent && topScore > 0.1 ? `<div class="scan-intent">🎯 ${escapeHtml(topIntent)} (${Math.round(topScore * 100)}%)</div>` : ''}
        </div>`;
    }).join('');
  } catch (err) {
    console.error('[ViFake] Load recent scans failed:', err);
  }
}

// ─── Clear History ───
function setupClearHistory() {
  const btn = document.getElementById('clearHistory');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    if (!confirm('Xóa toàn bộ lịch sử quét?')) return;
    await sendMessage({ action: 'clearHistory' });
    await loadStatus();
    await loadRecentScans();
  });
}

// ─── Tabs ───
function setupTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
    });
  });
}

// ─── Settings (constants defined once below in setupSettings section) ───

function setupSettings() {
  chrome.storage.local.get(['apiUrl', 'authToken', 'autoScan'], (data) => {
    document.getElementById('apiUrlInput').value    = data.apiUrl    || DEFAULT_API_URL;
    document.getElementById('authTokenInput').value = data.authToken || DEFAULT_AUTH_TOKEN;
    document.getElementById('autoScanToggle').checked = data.autoScan || false;
  });

  document.getElementById('saveSettings').addEventListener('click', () => {
    const settings = {
      apiUrl:    document.getElementById('apiUrlInput').value.trim(),
      authToken: document.getElementById('authTokenInput').value.trim(),
      autoScan:  document.getElementById('autoScanToggle').checked,
    };
    chrome.runtime.sendMessage({ action: 'updateSettings', settings }, () => {
      const el = document.getElementById('settingsStatus');
      el.textContent  = '✓ Đã lưu cài đặt';
      el.className    = 'settings-status success';
      setTimeout(() => { el.textContent = ''; }, 2500);
    });
  });

  document.getElementById('testConnection').addEventListener('click', async () => {
    const statusEl = document.getElementById('settingsStatus');
    const apiUrl   = document.getElementById('apiUrlInput').value.trim() || DEFAULT_API_URL;
    statusEl.textContent = '⏳ Đang kiểm tra...';
    statusEl.className   = 'settings-status';
    try {
      const res  = await fetch(`${apiUrl}/api/v1/health`, { signal: AbortSignal.timeout(10000) });
      if (res.ok) {
        const data = await res.json();
        statusEl.textContent = `✓ Kết nối thành công — ${data.status || 'healthy'}`;
        statusEl.className   = 'settings-status success';
      } else {
        statusEl.textContent = `✗ Lỗi: HTTP ${res.status}`;
        statusEl.className   = 'settings-status error';
      }
    } catch (err) {
      statusEl.textContent = `✗ Không kết nối: ${err.message}`;
      statusEl.className   = 'settings-status error';
    }
  });

  document.getElementById('privacyLink').addEventListener('click', (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: chrome.runtime.getURL('privacy-policy.html') });
  });
}

// ─── Helpers ───
function sendMessage(msg) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (response) => {
      if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
      else resolve(response);
    });
  });
}

function formatTime(ts) {
  if (!ts) return '';
  const diff = Date.now() - ts;
  if (diff < 60000)    return 'Vừa xong';
  if (diff < 3600000)  return `${Math.floor(diff / 60000)} phút trước`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} giờ trước`;
  return new Date(ts).toLocaleDateString('vi-VN');
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ─── Status & Stats ───
async function loadStatus() {
  try {
    const data = await sendMessage({ action: 'getStatus' });
    const totalScans = data.totalScans || 0;
    const scamDetected = data.scamDetected || 0;
    const safeCount = Math.max(0, totalScans - scamDetected);

    document.getElementById('totalScans').textContent = totalScans;
    document.getElementById('scamDetected').textContent = scamDetected;
    document.getElementById('safeCount').textContent = safeCount;

    // Check API connection
    const apiUrl = data.apiUrl || 'https://vifake-analytics-api.onrender.com';
    const token = data.authToken || 'demo-token-123';

    try {
      const res = await fetch(`${apiUrl}/api/v1/health`, {
        signal: AbortSignal.timeout(5000),
      });
      const dot = document.getElementById('statusDot');
      if (res.ok) {
        dot.classList.add('online');
        dot.classList.remove('offline');
        dot.title = 'API đang hoạt động';
      } else {
        dot.classList.add('offline');
        dot.classList.remove('online');
        dot.title = 'API không phản hồi';
      }
    } catch {
      const dot = document.getElementById('statusDot');
      dot.classList.add('offline');
      dot.classList.remove('online');
      dot.title = 'Không kết nối được API';
    }
  } catch (err) {
    console.error('[ViFake] Load status failed:', err);
  }
}

// ─── Recent Scans ───
async function loadRecentScans() {
  try {
    const scans = await sendMessage({ action: 'getRecentScans' });
    const listEl = document.getElementById('recentList');

    if (!scans || scans.length === 0) {
      listEl.innerHTML = `
        <div class="empty-state">
          <p>Chưa có kết quả quét nào.</p>
          <p class="hint">Mở Facebook và nhấn nút "Kiểm tra ViFake" dưới bài đăng.</p>
        </div>
      `;
      return;
    }

    listEl.innerHTML = scans.map(scan => {
      const result = scan.result || {};
      const label = result.label || result.prediction || 'UNKNOWN';
      const labelClass = {
        'SAFE': 'safe',
        'SUSPICIOUS': 'warn',
        'FAKE_SCAM': 'danger',
        'TOXIC': 'danger',
      }[label] || 'warn';

      const labelText = {
        'SAFE': 'An toàn',
        'SUSPICIOUS': 'Đáng ngờ',
        'FAKE_SCAM': 'Lừa đảo',
        'TOXIC': 'Độc hại',
      }[label] || label;

      const time = formatTime(scan.timestamp);

      return `
        <div class="scan-item">
          <div class="scan-item-header">
            <span class="scan-label ${labelClass}">${labelText}</span>
            <span class="scan-time">${time}</span>
          </div>
          <div class="scan-text">${escapeHtml(scan.text || '')}</div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('[ViFake] Load recent scans failed:', err);
  }
}

// ─── Tabs ───
function setupTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
    });
  });
}

// ─── Settings ───
const DEFAULT_API_URL = 'http://localhost:8000';
const DEFAULT_AUTH_TOKEN = 'demo-token-123';

function setupSettings() {
  // Load current settings (fallback to defaults)
  chrome.storage.local.get(['apiUrl', 'authToken', 'autoScan'], (data) => {
    document.getElementById('apiUrlInput').value = data.apiUrl || DEFAULT_API_URL;
    document.getElementById('authTokenInput').value = data.authToken || DEFAULT_AUTH_TOKEN;
    document.getElementById('autoScanToggle').checked = data.autoScan || false;
  });

  // Save
  document.getElementById('saveSettings').addEventListener('click', () => {
    const settings = {
      apiUrl: document.getElementById('apiUrlInput').value.trim(),
      authToken: document.getElementById('authTokenInput').value.trim(),
      autoScan: document.getElementById('autoScanToggle').checked,
    };

    chrome.runtime.sendMessage({ action: 'updateSettings', settings }, (res) => {
      const statusEl = document.getElementById('settingsStatus');
      statusEl.textContent = '✓ Đã lưu';
      statusEl.className = 'settings-status success';
      setTimeout(() => { statusEl.textContent = ''; }, 2000);
    });
  });

  // Test connection
  document.getElementById('testConnection').addEventListener('click', async () => {
    const statusEl = document.getElementById('settingsStatus');
    const apiUrl = document.getElementById('apiUrlInput').value.trim() || 'https://vifake-analytics-api.onrender.com';

    statusEl.textContent = 'Đang kiểm tra...';
    statusEl.className = 'settings-status';

    try {
      const res = await fetch(`${apiUrl}/api/v1/health`, {
        signal: AbortSignal.timeout(10000),
      });

      if (res.ok) {
        const data = await res.json();
        statusEl.textContent = `✓ Kết nối thành công — ${data.status || 'healthy'}`;
        statusEl.className = 'settings-status success';
      } else {
        statusEl.textContent = `✗ Lỗi: HTTP ${res.status}`;
        statusEl.className = 'settings-status error';
      }
    } catch (err) {
      statusEl.textContent = `✗ Không kết nối được: ${err.message}`;
      statusEl.className = 'settings-status error';
    }
  });

  // Privacy link
  document.getElementById('privacyLink').addEventListener('click', (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: chrome.runtime.getURL('privacy-policy.html') });
  });
}

// ─── Helpers ───
function sendMessage(msg) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(response);
      }
    });
  });
}

function formatTime(ts) {
  if (!ts) return '';
  const diff = Date.now() - ts;
  if (diff < 60000) return 'Vừa xong';
  if (diff < 3600000) return `${Math.floor(diff / 60000)} phút trước`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} giờ trước`;
  return new Date(ts).toLocaleDateString('vi-VN');
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
