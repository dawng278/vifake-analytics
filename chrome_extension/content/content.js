/**
 * ViFake Analytics — Content Script (Facebook)
 *
 * Key design decisions:
 * 1. MutationObserver instead of DOMContentLoaded (Facebook is SPA)
 * 2. Target aria-label / data-* / DOM structure, NOT minified class names
 * 3. CSS-only animations, no JS animation library
 * 4. RAM-only processing — no content stored
 */

(() => {
  'use strict';

  // ─── Constants ───
  const SCAN_ATTR = 'data-vifake-scanned';
  const BTN_CLASS = 'vifake-check-btn';
  const RESULT_CLASS = 'vifake-result-panel';
  const DEBOUNCE_MS = 500;
  const MIN_TEXT_LENGTH = 15;

  // ─── Platform Detection ───
  function detectPlatform() {
    const host = location.hostname;
    if (host.includes('facebook.com')) return 'facebook';
    if (host.includes('youtube.com')) return 'youtube';
    if (host.includes('tiktok.com')) return 'tiktok';
    return 'unknown';
  }

  const PLATFORM = detectPlatform();

  // ─── Skip Messenger / Chat contexts ───
  function isMessengerContext() {
    const path = location.pathname;
    // Messenger paths on facebook.com
    if (/^\/messages(\/|$)/i.test(path)) return true;
    if (/^\/t\//i.test(path)) return true;
    if (/^\/chat(\/|$)/i.test(path)) return true;
    // Messenger.com domain
    if (location.hostname.includes('messenger.com')) return true;
    return false;
  }

  // ─── Post Finders (resilient to class name changes) ───
  const POST_SELECTORS = {
    facebook: [
      // Primary: feed posts inside [role="feed"] (most stable, excludes messenger)
      '[role="feed"] [role="article"]',
      // Fallback: posts with FB-specific data-pagelet attributes
      '[data-pagelet*="FeedUnit"]',
      '[data-pagelet*="ProfileTimeline"]',
      '[data-pagelet*="GroupFeed"]',
    ],
    youtube: [
      'ytd-rich-item-renderer',
      'ytd-video-renderer',
      'ytd-compact-video-renderer',
      '#comments ytd-comment-thread-renderer',
    ],
    tiktok: [
      '[data-e2e="recommend-list-item-container"]',
      '[class*="DivItemContainer"]',
    ],
  };

  // ─── Text Extractors ───
  function extractPostText(postEl) {
    if (PLATFORM === 'facebook') return extractFacebookText(postEl);
    if (PLATFORM === 'youtube') return extractYouTubeText(postEl);
    if (PLATFORM === 'tiktok') return extractTikTokText(postEl);
    return '';
  }

  function extractFacebookText(postEl) {
    // Strategy: find the main text container using data-ad-preview or dir="auto"
    const textParts = [];

    // 1. Primary: [dir="auto"] spans inside the post (FB wraps text in these)
    const dirAutoEls = postEl.querySelectorAll('[dir="auto"]');
    dirAutoEls.forEach(el => {
      // Skip navigation / action bar text
      const role = el.closest('[role="navigation"], [role="toolbar"], [role="banner"]');
      if (role) return;
      // Skip tiny fragments (button labels, etc.)
      const text = el.innerText?.trim();
      if (text && text.length > 5) {
        textParts.push(text);
      }
    });

    // 2. Fallback: all visible text minus action bar
    if (textParts.length === 0) {
      const clone = postEl.cloneNode(true);
      // Remove action buttons, comments section
      clone.querySelectorAll('[role="toolbar"], [role="navigation"], form').forEach(el => el.remove());
      const text = clone.innerText?.trim();
      if (text) textParts.push(text);
    }

    // Deduplicate and join
    const unique = [...new Set(textParts)];
    return unique.join('\n').trim();
  }

  function extractYouTubeText(postEl) {
    const title = postEl.querySelector('#video-title, #title-wrapper, .title')?.innerText?.trim() || '';
    const desc = postEl.querySelector('#description, .description')?.innerText?.trim() || '';
    const comment = postEl.querySelector('#content-text')?.innerText?.trim() || '';
    return [title, desc, comment].filter(Boolean).join('\n');
  }

  function extractTikTokText(postEl) {
    const desc = postEl.querySelector('[data-e2e="video-desc"], [class*="DivDescription"]')?.innerText?.trim() || '';
    return desc;
  }

  // ─── Post URL Extractor ───
  function extractPostUrl(postEl) {
    if (PLATFORM === 'facebook') {
      // FB post links are typically timestamps that link to the post
      const link = postEl.querySelector('a[href*="/posts/"], a[href*="/photo"], a[href*="story_fbid"], a[role="link"][href*="/permalink/"]');
      if (link) return link.href;
      // Fallback: any link with a timestamp pattern
      const timeLink = postEl.querySelector('a[href*="?__cft__"], a[role="link"][tabindex="0"]');
      if (timeLink) return timeLink.href;
    }
    return location.href;
  }

  // ─── UI: Inject Check Button ───
  function injectCheckButton(postEl) {
    if (postEl.querySelector(`.${BTN_CLASS}`)) return;

    const text = extractPostText(postEl);
    if (text.length < MIN_TEXT_LENGTH) return;

    // Create button container
    const container = document.createElement('div');
    container.className = 'vifake-container';

    const btn = document.createElement('button');
    btn.className = BTN_CLASS;
    btn.innerHTML = `
      <svg class="vifake-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
      <span>Kiểm tra ViFake</span>
    `;
    btn.title = 'Kiểm tra nội dung bài đăng này';

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      e.preventDefault();
      handleCheckClick(postEl, btn, container);
    });

    container.appendChild(btn);
    postEl.setAttribute(SCAN_ATTR, 'injected');

    // Insert after the post text, before the action bar
    if (PLATFORM === 'facebook') {
      // Try to find the action bar (like/comment/share) and insert before it
      const actionBar = postEl.querySelector('[role="toolbar"]')
        || postEl.querySelector('[aria-label*="Like" i], [aria-label*="Thích" i]')?.closest('div:not([role])');
      if (actionBar?.parentElement) {
        actionBar.parentElement.insertBefore(container, actionBar);
      } else {
        postEl.appendChild(container);
      }
    } else {
      postEl.appendChild(container);
    }
  }

  // ─── Handle Check Button Click ───
  async function handleCheckClick(postEl, btn, container) {
    const text = extractPostText(postEl);
    const url = extractPostUrl(postEl);

    if (text.length < MIN_TEXT_LENGTH) {
      showResult(container, { error: 'Nội dung quá ngắn để phân tích' });
      return;
    }

    // Show scanning state
    btn.disabled = true;
    btn.classList.add('vifake-scanning');
    btn.innerHTML = `
      <div class="vifake-spinner"></div>
      <span>Đang quét...</span>
    `;

    // Remove old result
    container.querySelector(`.${RESULT_CLASS}`)?.remove();

    // Show progress bar
    const progress = document.createElement('div');
    progress.className = 'vifake-progress';
    progress.innerHTML = '<div class="vifake-progress-bar"></div>';
    container.appendChild(progress);

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'analyze',
        payload: { text, url, platform: PLATFORM },
      });

      progress.remove();

      if (result.error) {
        showResult(container, { error: result.error });
      } else {
        showResult(container, result);
        postEl.setAttribute(SCAN_ATTR, 'checked');
      }
    } catch (err) {
      progress.remove();
      showResult(container, { error: err.message || 'Lỗi kết nối' });
    }

    // Reset button
    btn.disabled = false;
    btn.classList.remove('vifake-scanning');
    btn.innerHTML = `
      <svg class="vifake-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
      <span>Kiểm tra lại</span>
    `;
  }

  // ─── Show Result Panel ───
  function showResult(container, result) {
    container.querySelector(`.${RESULT_CLASS}`)?.remove();

    const panel = document.createElement('div');
    panel.className = RESULT_CLASS;

    if (result.error) {
      panel.classList.add('vifake-error');
      panel.innerHTML = `
        <div class="vifake-result-header vifake-risk-error">
          <span class="vifake-result-icon">⚠️</span>
          <span class="vifake-result-label">Lỗi</span>
        </div>
        <div class="vifake-result-body">
          <p>${escapeHtml(result.error)}</p>
        </div>
      `;
      container.appendChild(panel);
      return;
    }

    const label = result.label || result.prediction || 'UNKNOWN';
    const confidence = result.confidence || 0;
    const riskLevel = result.risk_level || 'UNKNOWN';
    const details = result.analysis_details || {};
    const intentLabel = details.intent_label || '';
    const intentExpl = details.intent_explanation || '';

    const riskClass = {
      'SAFE': 'vifake-risk-safe',
      'SUSPICIOUS': 'vifake-risk-warn',
      'FAKE_SCAM': 'vifake-risk-danger',
      'TOXIC': 'vifake-risk-danger',
    }[label] || 'vifake-risk-warn';

    const riskIcon = {
      'SAFE': '✅',
      'SUSPICIOUS': '⚠️',
      'FAKE_SCAM': '🚨',
      'TOXIC': '🚨',
    }[label] || '❓';

    const riskText = {
      'SAFE': 'An toàn',
      'SUSPICIOUS': 'Đáng ngờ',
      'FAKE_SCAM': 'Lừa đảo',
      'TOXIC': 'Độc hại',
    }[label] || label;

    const confPct = Math.round(confidence * 100);

    // Build intent bars HTML
    let intentHtml = '';
    const intentScores = details.intent || {};
    const intentNames = {
      'credential_harvest': 'Thu thập thông tin',
      'money_transfer': 'Chuyển tiền',
      'urgency_pressure': 'Tạo áp lực',
      'fake_reward': 'Phần thưởng giả',
      'grooming_isolation': 'Tiếp cận trẻ em',
    };

    for (const [key, name] of Object.entries(intentNames)) {
      const score = intentScores[key] || 0;
      if (score > 0.05) {
        const pct = Math.round(score * 100);
        intentHtml += `
          <div class="vifake-intent-row">
            <span class="vifake-intent-name">${name}</span>
            <div class="vifake-intent-bar-bg">
              <div class="vifake-intent-bar" style="--target-width: ${pct}%"></div>
            </div>
            <span class="vifake-intent-pct">${pct}%</span>
          </div>
        `;
      }
    }

    // Build flags HTML
    let flagsHtml = '';
    const flags = details.nlp_flags || [];
    if (flags.length > 0) {
      flagsHtml = `
        <div class="vifake-flags">
          ${flags.map(f => `<span class="vifake-flag-tag">${escapeHtml(f)}</span>`).join('')}
        </div>
      `;
    }

    panel.innerHTML = `
      <div class="vifake-result-header ${riskClass}">
        <span class="vifake-result-icon">${riskIcon}</span>
        <span class="vifake-result-label">${riskText}</span>
        <span class="vifake-result-confidence">${confPct}%</span>
      </div>
      <div class="vifake-result-body">
        ${intentLabel ? `<p class="vifake-intent-primary"><strong>Ý định:</strong> ${escapeHtml(intentLabel)}</p>` : ''}
        ${intentExpl ? `<p class="vifake-intent-expl">${escapeHtml(intentExpl)}</p>` : ''}
        ${intentHtml ? `<div class="vifake-intent-section">${intentHtml}</div>` : ''}
        ${flagsHtml}
        ${label !== 'SAFE' ? `
          <div class="vifake-action-hint">
            <strong>💡 Gợi ý cho phụ huynh:</strong>
            ${label === 'FAKE_SCAM' ? 'Đây có thể là nội dung lừa đảo. Hãy nói chuyện với con về cách nhận biết lừa đảo trực tuyến.' : ''}
            ${label === 'SUSPICIOUS' ? 'Nội dung đáng ngờ. Hãy kiểm tra thêm trước khi cho con tương tác.' : ''}
            ${label === 'TOXIC' ? 'Nội dung có thể độc hại. Cân nhắc hạn chế trẻ tiếp cận.' : ''}
          </div>
        ` : ''}
      </div>
    `;

    container.appendChild(panel);
  }

  // ─── MutationObserver: Watch for new posts (SPA navigation) ───
  let debounceTimer = null;

  function scanForPosts() {
    // Skip chat/messenger contexts entirely
    if (PLATFORM === 'facebook' && isMessengerContext()) return;

    const selectors = POST_SELECTORS[PLATFORM] || [];
    for (const sel of selectors) {
      const posts = document.querySelectorAll(sel);
      posts.forEach(post => {
        // Extra safety: skip if the element is inside a chat/dialog context
        if (PLATFORM === 'facebook') {
          if (post.closest('[role="dialog"]')) return;  // Modal chat popup
          if (post.closest('[aria-label*="chat" i], [aria-label*="message" i], [aria-label*="Messenger" i]')) return;
        }
        if (!post.hasAttribute(SCAN_ATTR)) {
          injectCheckButton(post);
        }
      });
    }
  }

  const observer = new MutationObserver((mutations) => {
    // Debounce: Facebook fires many mutations per scroll
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(scanForPosts, DEBOUNCE_MS);
  });

  // Start observing
  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });

  // Initial scan
  scanForPosts();

  // ─── Helpers ───
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  console.log(`[ViFake] Content script loaded for ${PLATFORM}`);
})();
