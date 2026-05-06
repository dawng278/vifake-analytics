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
  const MIN_TEXT_LENGTH = 10;

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
      // Primary: all articles (will filter out messenger via post-checks below)
      '[role="article"]',
      // Fallback: posts with FB-specific data-pagelet attributes
      '[data-pagelet*="FeedUnit"]',
    ],
    tiktok: [
      // TikTok video containers - use data-e2e for stability
      '[data-e2e="browse-video-desc"]',
      '[data-e2e="video-player"]',
      // Fallback: video elements with TikTok CDN
      'video[src*="tiktokcdn"]',
      'video[src*="muscdn"]',
    ],
    youtube: [
      'ytd-rich-item-renderer',
      'ytd-video-renderer',
      'ytd-compact-video-renderer',
      '#comments ytd-comment-thread-renderer',
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
    const textParts = [];

    // Strategy 1: [dir="auto"] spans inside the post (older FB UI)
    postEl.querySelectorAll('[dir="auto"]').forEach(el => {
      const role = el.closest('[role="navigation"], [role="toolbar"], [role="banner"]');
      if (role) return;
      const text = el.innerText?.trim();
      if (text && text.length > 5) {
        textParts.push(text);
      }
    });

    // Strategy 2: data-ad-preview attribute (FB sponsored / regular posts)
    if (textParts.length === 0) {
      postEl.querySelectorAll('[data-ad-preview="message"], [data-ad-comet-preview="message"]').forEach(el => {
        const text = el.innerText?.trim();
        if (text) textParts.push(text);
      });
    }

    // Strategy 3: ALL spans with substantive text (modern FB UI)
    if (textParts.length === 0) {
      postEl.querySelectorAll('span').forEach(el => {
        // Skip if inside action bar / nav
        if (el.closest('[role="toolbar"], [role="navigation"], [role="banner"]')) return;
        // Skip if it has child spans (we want leaf text nodes)
        if (el.querySelector('span')) return;
        const text = el.innerText?.trim();
        if (text && text.length > 10 && text.length < 5000) {
          textParts.push(text);
        }
      });
    }

    // Strategy 4: Last resort - whole post innerText minus action bar
    if (textParts.length === 0) {
      const clone = postEl.cloneNode(true);
      clone.querySelectorAll('[role="toolbar"], [role="navigation"], [role="banner"], form, button').forEach(el => el.remove());
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
    const desc = postEl.querySelector('[data-e2e="browse-video-desc"], [data-e2e="video-desc"], [class*="DivDescription"]')?.innerText?.trim() || '';
    return desc;
  }

  // ─── TikTok Video URL Extractor ───
  function extractTikTokVideoInfo(postEl) {
    // Get video URL from video element
    const videoEl = postEl.querySelector('video[src*="tiktok"]')
      || postEl.querySelector('video[src*="tiktokcdn"]')
      || postEl.querySelector('video[src*="muscdn"]');

    if (!videoEl || !videoEl.src) return null;

    // Get additional metadata from DOM
    const descEl = postEl.querySelector('[data-e2e="browse-video-desc"]')
      || postEl.querySelector('[data-e2e="video-desc"]')
      || postEl.querySelector('[class*="DivDescription"]');

    const authorEl = postEl.querySelector('[data-e2e="browse-username"]')
      || postEl.querySelector('[class*="DivUsername"]');

    return {
      video_url: videoEl.src,
      description: descEl?.textContent?.trim() || '',
      author: authorEl?.textContent?.trim() || '',
      page_url: window.location.href,
    };
  }

  // ─── Handle TikTok Video Analysis ───
  async function handleTikTokVideoCheck(postEl, btn, container) {
    const videoInfo = extractTikTokVideoInfo(postEl);
    
    if (!videoInfo) {
      showResult(container, { error: 'Không lấy được URL video. Thử reload trang.' });
      return;
    }

    // Show scanning state with stages
    btn.disabled = true;
    btn.classList.add('vifake-scanning');
    btn.innerHTML = `
      <div class="vifake-spinner"></div>
      <span>Đang phân tích video...</span>
    `;

    // Remove old result
    container.querySelector(`.${RESULT_CLASS}`)?.remove();

    // Show multi-stage progress
    const stages = [
      { id: 'extract', label: 'Đang trích xuất audio & hình ảnh...', duration: 4000 },
      { id: 'transcribe', label: 'Đang nhận dạng giọng nói...', duration: 6000 },
      { id: 'analyze', label: 'AI đang phân tích nội dung...', duration: 5000 },
      { id: 'vision', label: 'Kiểm tra video AI-generated...', duration: 4000 },
    ];

    const progressContainer = document.createElement('div');
    progressContainer.className = 'vifake-tiktok-progress';
    progressContainer.innerHTML = `
      <div class="vifake-stage-list">
        ${stages.map(s => `
          <div class="vifake-stage" id="vf-stage-${s.id}">
            <div class="vifake-stage-dot"></div>
            <span>${s.label}</span>
          </div>
        `).join('')}
      </div>
      <div class="vifake-eta">Khoảng 10–20 giây...</div>
    `;
    container.appendChild(progressContainer);

    // Animate stages
    let cumulative = 0;
    stages.forEach(stage => {
      setTimeout(() => {
        document.querySelectorAll('.vifake-stage').forEach(el => {
          el.classList.remove('active');
        });
        document.getElementById(`vf-stage-${stage.id}`)
          ?.classList.add('active');
      }, cumulative);
      cumulative += stage.duration;
    });

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'analyze_video',
        payload: videoInfo,
      });

      progressContainer.remove();

      if (result.error) {
        showResult(container, { error: result.error });
      } else {
        showVideoResult(container, result);
        postEl.setAttribute(SCAN_ATTR, 'checked');
      }
    } catch (err) {
      progressContainer.remove();
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
    if (text.length < MIN_TEXT_LENGTH) {
      console.log('[ViFake] Skipping post (text too short):', text.length, 'chars');
      return;
    }
    console.log('[ViFake] Injecting button for post with', text.length, 'chars');

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
    if (PLATFORM === 'tiktok') {
      return handleTikTokVideoCheck(postEl, btn, container);
    }

    // Facebook/YouTube text analysis
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

  // ─── Show Video Result Panel (TikTok) ───
  function showVideoResult(container, result) {
    container.querySelector(`.${RESULT_CLASS}`)?.remove();

    const panel = document.createElement('div');
    panel.className = RESULT_CLASS;

    const verdict = result.verdict || 'UNKNOWN';
    const confidence = result.confidence || 0;
    const isAi = result.is_ai_generated || false;
    const aiConfidence = result.ai_confidence || 0;
    const transcript = result.transcript || '';
    const explanation = result.explanation || '';

    const riskClass = {
      'SAFE': 'vifake-risk-safe',
      'SUSPICIOUS': 'vifake-risk-warn',
      'FAKE_SCAM': 'vifake-risk-danger',
    }[verdict] || 'vifake-risk-warn';

    const riskIcon = {
      'SAFE': '✅',
      'SUSPICIOUS': '⚠️',
      'FAKE_SCAM': '🚨',
    }[verdict] || '❓';

    const riskText = {
      'SAFE': 'An toàn',
      'SUSPICIOUS': 'Đáng ngờ',
      'FAKE_SCAM': 'Lừa đảo',
    }[verdict] || verdict;

    const confPct = Math.round(confidence * 100);
    const aiPct = Math.round(aiConfidence * 100);

    panel.innerHTML = `
      <div class="vifake-result-header ${riskClass}">
        <span class="vifake-result-icon">${riskIcon}</span>
        <span class="vifake-result-label">${riskText}</span>
        <span class="vifake-result-confidence">${confPct}%</span>
      </div>
      <div class="vifake-result-body">
        ${explanation ? `<p class="vifake-explanation">${escapeHtml(explanation)}</p>` : ''}
        
        ${isAi ? `
          <div class="vifake-ai-section">
            <p><strong>🤖 Phát hiện AI-generated:</strong> ${aiPct}% confidence</p>
          </div>
        ` : ''}

        ${transcript ? `
          <div class="vifake-transcript-section">
            <p><strong>📝 Transcript:</strong></p>
            <div class="vifake-transcript">${escapeHtml(transcript)}</div>
          </div>
        ` : ''}

        ${verdict !== 'SAFE' ? `
          <div class="vifake-action-hint">
            <strong>💡 Gợi ý cho phụ huynh:</strong>
            ${verdict === 'FAKE_SCAM' ? 'Đây có thể là nội dung lừa đảo. Hãy nói chuyện với con về cách nhận biết lừa đảo trực tuyến.' : ''}
            ${verdict === 'SUSPICIOUS' ? 'Nội dung đáng ngờ. Hãy kiểm tra thêm trước khi cho con tương tác.' : ''}
          </div>
        ` : ''}
      </div>
    `;

    container.appendChild(panel);
  }

  // ─── MutationObserver: Watch for new posts (SPA navigation) ───
  let debounceTimer = null;

  // Determine if an "article" is really a feed post (not a chat message)
  function isLikelyFeedPost(post) {
    if (PLATFORM !== 'facebook') return true;

    // Reject if inside Messenger chat (chat overlay, messenger panel)
    const chatLabels = [
      '[aria-label*="chat" i]',
      '[aria-label*="Messenger" i]',
      '[aria-label*="tin nh\u1eafn" i]',   // Vietnamese: "tin nhắn"
    ].join(',');
    if (post.closest(chatLabels)) return false;

    // Size filter: chat messages are small (typically <120px).
    // Real feed posts are taller. Using 200 to be safe for posts with multiple lines.
    const rect = post.getBoundingClientRect();
    if (rect.height < 200) return false;

    // Width filter: feed posts span a reasonable width. Chat messages are narrow.
    if (rect.width < 300) return false;

    return true;
  }

  function scanForPosts() {
    // Skip chat/messenger contexts entirely (URL-based)
    if (PLATFORM === 'facebook' && isMessengerContext()) return;

    const selectors = POST_SELECTORS[PLATFORM] || [];
    const seen = new Set();
    let totalFound = 0, passedFilter = 0;
    for (const sel of selectors) {
      const posts = document.querySelectorAll(sel);
      posts.forEach(post => {
        if (seen.has(post)) return;
        seen.add(post);
        totalFound++;
        if (post.hasAttribute(SCAN_ATTR)) return;
        if (!isLikelyFeedPost(post)) return;
        passedFilter++;
        injectCheckButton(post);
      });
    }
    if (totalFound > 0) {
      console.log(`[ViFake] Scan: ${totalFound} candidates, ${passedFilter} passed filter`);
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

  // ─── Right-click Context Menu Support ───
  let lastRightClickedEl = null;

  document.addEventListener('contextmenu', (e) => {
    lastRightClickedEl = e.target;
  }, true);

  // Walk up DOM from clicked element to find post-like container
  function findPostContainer(startEl) {
    if (!startEl) return null;
    let current = startEl;
    let bestCandidate = null;
    let bestScore = 0;

    while (current && current !== document.body && current !== document.documentElement) {
      const rect = current.getBoundingClientRect();
      const text = (current.innerText || '').trim();

      // Skip if too small or too big
      if (rect.width < 300 || rect.height < 100 || rect.height > 5000) {
        current = current.parentElement;
        continue;
      }

      // Score this candidate
      let score = 0;
      // Has substantial text → likely a post
      if (text.length >= 30) score += 2;
      if (text.length >= 100) score += 2;
      // Reasonable size for a post
      if (rect.width >= 400 && rect.width <= 900) score += 2;
      if (rect.height >= 200 && rect.height <= 2000) score += 2;
      // Has images/videos → likely a post
      if (current.querySelector('img, video')) score += 1;
      // Has a role
      if (current.getAttribute('role') === 'article') score += 3;
      // Has FB post indicators
      if (current.querySelector('[data-ad-preview], [data-ad-rendering-role]')) score += 2;

      if (score > bestScore) {
        bestScore = score;
        bestCandidate = current;
      }

      current = current.parentElement;
    }

    return bestCandidate;
  }

  // Extract images and videos from a post
  function extractMediaUrls(postEl) {
    const images = [];
    const videos = [];
    postEl.querySelectorAll('img').forEach(img => {
      const src = img.src;
      if (!src || src.startsWith('data:')) return;
      // Filter out tiny icons (avatars are OK, emojis aren't)
      const rect = img.getBoundingClientRect();
      if (rect.width >= 50 && rect.height >= 50) {
        images.push(src);
      }
    });
    postEl.querySelectorAll('video').forEach(video => {
      if (video.src) videos.push(video.src);
      video.querySelectorAll('source').forEach(s => { if (s.src) videos.push(s.src); });
    });
    return { images: [...new Set(images)].slice(0, 5), videos: [...new Set(videos)].slice(0, 3) };
  }

  // Listen for context-menu scan request from background
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === 'scanFromContextMenu') {
      handleContextMenuScan(msg.selectionText || '');
      sendResponse({ ok: true });
      return false;
    }
  });

  async function handleContextMenuScan(selectionText) {
    let postEl = lastRightClickedEl;
    let text = '';

    // Priority 1: User explicitly selected text → use that
    if (selectionText && selectionText.length >= 10) {
      text = selectionText;
      postEl = lastRightClickedEl || document.body;
    } else {
      // Priority 2: Walk up from clicked element to find post container
      postEl = findPostContainer(lastRightClickedEl);
      if (!postEl) {
        showFloatingNotice('error', 'Không tìm thấy bài viết. Hãy bôi đen text hoặc click chuột phải vào trong bài.');
        return;
      }
      text = (postEl.innerText || '').trim();
    }

    if (text.length < 10) {
      showFloatingNotice('error', 'Nội dung quá ngắn để phân tích (cần ≥10 ký tự).');
      return;
    }

    // Limit text length
    if (text.length > 5000) text = text.substring(0, 5000);

    const media = postEl ? extractMediaUrls(postEl) : { images: [], videos: [] };
    const url = location.href;

    // Show scanning notice
    const noticeEl = showFloatingNotice('scanning', `Đang quét bài viết (${text.length} ký tự${media.images.length ? `, ${media.images.length} ảnh` : ''}${media.videos.length ? `, ${media.videos.length} video` : ''})...`);

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'analyze',
        payload: { text, url, platform: PLATFORM, images: media.images, videos: media.videos },
      });

      noticeEl?.remove();
      showFloatingResult(result, postEl);
    } catch (err) {
      noticeEl?.remove();
      showFloatingNotice('error', `Lỗi: ${err.message || 'Không thể kết nối API'}`);
    }
  }

  // Show floating notice (top-right corner)
  function showFloatingNotice(type, message) {
    const existing = document.querySelector('.vifake-floating-notice');
    existing?.remove();

    const notice = document.createElement('div');
    notice.className = `vifake-floating-notice vifake-notice-${type}`;
    notice.innerHTML = `
      <div class="vifake-notice-content">
        ${type === 'scanning' ? '<div class="vifake-spinner"></div>' : ''}
        <span>${escapeHtml(message)}</span>
      </div>
      <button class="vifake-notice-close" aria-label="Đóng">×</button>
    `;
    notice.querySelector('.vifake-notice-close').addEventListener('click', () => notice.remove());

    document.body.appendChild(notice);
    if (type === 'error') {
      setTimeout(() => notice.remove(), 6000);
    }
    return notice;
  }

  // Show full result panel (top-right, larger)
  function showFloatingResult(result, postEl) {
    const existing = document.querySelector('.vifake-floating-result');
    existing?.remove();

    const panel = document.createElement('div');
    panel.className = 'vifake-floating-result';

    if (result.error) {
      panel.classList.add('vifake-error');
      panel.innerHTML = `
        <div class="vifake-result-header vifake-risk-error">
          <span class="vifake-result-icon">⚠️</span>
          <span class="vifake-result-label">Lỗi</span>
          <button class="vifake-notice-close" aria-label="Đóng">×</button>
        </div>
        <div class="vifake-result-body"><p>${escapeHtml(result.error)}</p></div>
      `;
      panel.querySelector('.vifake-notice-close').addEventListener('click', () => panel.remove());
      document.body.appendChild(panel);
      return;
    }

    const label = result.label || result.prediction || 'UNKNOWN';
    const confidence = result.confidence || 0;
    const details = result.analysis_details || {};

    const riskClass = {
      'SAFE': 'vifake-risk-safe',
      'SUSPICIOUS': 'vifake-risk-warn',
      'FAKE_SCAM': 'vifake-risk-danger',
      'TOXIC': 'vifake-risk-danger',
    }[label] || 'vifake-risk-warn';

    const riskIcon = { 'SAFE': '✅', 'SUSPICIOUS': '⚠️', 'FAKE_SCAM': '🚨', 'TOXIC': '🚨' }[label] || '❓';
    const riskText = { 'SAFE': 'An toàn', 'SUSPICIOUS': 'Đáng ngờ', 'FAKE_SCAM': 'Lừa đảo', 'TOXIC': 'Độc hại' }[label] || label;
    const confPct = Math.round(confidence * 100);

    // Only show intent details when there's a real risk signal — hide for SAFE
    // to avoid contradictory UI ("SAFE" + scary intent label).
    const showIntent = label !== 'SAFE';

    panel.innerHTML = `
      <div class="vifake-result-header ${riskClass}">
        <span class="vifake-result-icon">${riskIcon}</span>
        <span class="vifake-result-label">${riskText}</span>
        <span class="vifake-result-confidence">${confPct}%</span>
        <button class="vifake-notice-close" aria-label="Đóng">×</button>
      </div>
      <div class="vifake-result-body">
        ${showIntent && details.intent_label ? `<p><strong>Ý định:</strong> ${escapeHtml(details.intent_label)}</p>` : ''}
        ${showIntent && details.intent_explanation ? `<p>${escapeHtml(details.intent_explanation)}</p>` : ''}
        ${label === 'SAFE' ? `<p class="vifake-safe-msg">Không phát hiện dấu hiệu lừa đảo trong nội dung này.</p>` : ''}
        ${label !== 'SAFE' ? `
          <div class="vifake-action-hint">
            <strong>💡 Gợi ý:</strong>
            ${label === 'FAKE_SCAM' ? 'Có dấu hiệu lừa đảo. Hãy cảnh giác!' : ''}
            ${label === 'SUSPICIOUS' ? 'Nội dung đáng ngờ, kiểm tra thêm trước khi tin.' : ''}
            ${label === 'TOXIC' ? 'Nội dung có thể độc hại với trẻ.' : ''}
          </div>
        ` : ''}
      </div>
    `;
    panel.querySelector('.vifake-notice-close').addEventListener('click', () => panel.remove());
    document.body.appendChild(panel);
  }

  // ─── Helpers ───
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  console.log(`[ViFake] Content script loaded for ${PLATFORM}. Right-click on any post → "Quét bài viết với ViFake"`);
})();
