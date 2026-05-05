/**
 * ViFake Analytics — Popup Logic
 */

document.addEventListener('DOMContentLoaded', init);

function init() {
  loadStatus();
  loadRecentScans();
  setupTabs();
  setupSettings();
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
function setupSettings() {
  // Load current settings
  chrome.storage.local.get(['apiUrl', 'authToken', 'autoScan'], (data) => {
    document.getElementById('apiUrlInput').value = data.apiUrl || '';
    document.getElementById('authTokenInput').value = data.authToken || '';
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
