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
      // TikTok video containers - more comprehensive selectors
      '[data-e2e="video-player"]',
      '[data-e2e="browse-video-desc"]',
      '[data-e2e="video-desc"]',
      '[data-e2e="recommend-list-item-container"]',
      'div[class*="DivVideoContainer"]',
      // Video elements with TikTok CDN
      'video[src*="tiktokcdn"]',
      'video[src*="muscdn"]',
      'video[src*="tiktok.com"]',
      // General video elements as fallback
      'video',
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

  // ─── P1-A: Noise filter — removes like counts, timestamps, emoji-only strings ───
  const NOISE_RE = /^(\d[\d,. ]*[KkMmTỷB]?|\d+\s*(giây|phút|giờ|ngày|tuần|tháng|năm)\s*(trước)?|just now|vừa xong|yesterday|\p{Emoji_Presentation}+)$/u;
  function isNoise(text) {
    if (!text || text.length === 0) return true;
    if (NOISE_RE.test(text)) return true;
    // Pure punctuation / single word reaction labels (Like, Love, Haha ≤8 chars, no Vietnamese tone)
    if (text.length <= 8 && /^[a-zA-Z ]+$/.test(text)) return true;
    return false;
  }

  // ─── P3-B: Fuzzy dedup — removes substrings of already-collected parts ───
  function fuzzyDedup(parts) {
    const norm = s => s.toLowerCase().replace(/\s+/g, ' ');
    const result = [];
    for (const p of parts) {
      const pn = norm(p);
      // Skip if this is a substring of something we already have
      if (result.some(r => norm(r).includes(pn))) continue;
      // Remove existing entries that are substrings of the new one
      const filtered = result.filter(r => !pn.includes(norm(r)));
      filtered.push(p);
      result.length = 0;
      result.push(...filtered);
    }
    return result;
  }

  function extractFacebookText(postEl) {
    const textParts = [];

    // Strategy 1: [dir="auto"] spans (older FB UI) — P1-B: prefix [POST]
    const s1Parts = [];
    postEl.querySelectorAll('[dir="auto"]').forEach(el => {
      const role = el.closest('[role="navigation"], [role="toolbar"], [role="banner"]');
      if (role) return;
      const text = el.innerText?.trim();
      if (text && text.length > 5 && !isNoise(text)) s1Parts.push(text);
    });
    if (s1Parts.length > 0) textParts.push('[POST] ' + s1Parts.join(' '));

    // Strategy 2: data-ad-preview (FB sponsored / regular posts)
    if (textParts.length === 0) {
      postEl.querySelectorAll('[data-ad-preview="message"], [data-ad-comet-preview="message"]').forEach(el => {
        const text = el.innerText?.trim();
        if (text && !isNoise(text)) textParts.push('[POST] ' + text);
      });
    }

    // Strategy 3: ALL leaf spans (modern FB UI) — P1-A noise filter applied
    if (textParts.length === 0) {
      postEl.querySelectorAll('span').forEach(el => {
        if (el.closest('[role="toolbar"], [role="navigation"], [role="banner"]')) return;
        if (el.querySelector('span')) return;
        const text = el.innerText?.trim();
        if (text && text.length > 10 && text.length < 5000 && !isNoise(text)) {
          textParts.push(text);
        }
      });
    }

    // Strategy 4: Last resort — clone, strip chrome, use innerText
    if (textParts.length === 0) {
      const clone = postEl.cloneNode(true);
      clone.querySelectorAll('[role="toolbar"], [role="navigation"], [role="banner"], form, button').forEach(el => el.remove());
      const text = clone.innerText?.trim();
      if (text) textParts.push(text);
    }

    // P3-B: fuzzy dedup then join
    return fuzzyDedup([...new Set(textParts)]).join('\n').trim();
  }

  function extractYouTubeText(postEl) {
    // P1-B: structured prefixes so NLP knows context
    const title = postEl.querySelector('#video-title, #title-wrapper, .title')?.innerText?.trim() || '';
    const desc = postEl.querySelector('#description, .description')?.innerText?.trim() || '';
    // P1-C: fix — #content-text lives inside ytd-comment-renderer, not at root
    const commentEl = postEl.querySelector('ytd-comment-renderer #content-text, #content-text');
    const comment = commentEl?.innerText?.trim() || '';
    const parts = [];
    if (title) parts.push('[TITLE] ' + title);
    if (desc)  parts.push('[DESC] '  + desc);
    if (comment) parts.push('[COMMENT] ' + comment);
    return parts.join('\n');
  }

  function extractTikTokText(postEl) {
    // P1-D: extract caption + pinned/first comments for scam link detection
    const desc = postEl.querySelector('[data-e2e="browse-video-desc"], [data-e2e="video-desc"], [class*="DivDescription"]')?.innerText?.trim() || '';
    const parts = [];
    if (desc) parts.push('[DESC] ' + desc);
    // Pinned comment & first visible comment often carry scam links
    const commentEls = postEl.querySelectorAll('[data-e2e="comment-level-1"], [data-e2e="browse-comment-item"], [data-e2e="comment-item"]');
    let commentCount = 0;
    commentEls.forEach(el => {
      if (commentCount >= 2) return;
      const text = el.innerText?.trim();
      if (text && text.length > 5 && !isNoise(text)) {
        parts.push('[COMMENT] ' + text);
        commentCount++;
      }
    });
    return parts.join('\n');
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

    // For TikTok: Check if this is the main video container
    if (PLATFORM === 'tiktok') {
      const mainContainer = findMainVideoContainer(postEl);
      const targetContainer = mainContainer || postEl;
      
      // Get unique video ID
      const videoId = getVideoId(targetContainer);
      
      // Check if we already processed this video
      if (window.vifakeProcessedVideos && window.vifakeProcessedVideos.has(videoId)) {
        console.log('[ViFake] Video already processed:', videoId);
        return;
      }
      
      // Check if main container already has button
      if (targetContainer.querySelector(`.${BTN_CLASS}`)) {
        console.log('[ViFake] Container already has button');
        return;
      }
      
      // Mark this video as processed
      if (!window.vifakeProcessedVideos) {
        window.vifakeProcessedVideos = new Set();
      }
      window.vifakeProcessedVideos.add(videoId);
      
      console.log('[ViFake] Injecting button for TikTok video:', videoId);
      injectButtonToElement(targetContainer);
      return;
    }

    // For other platforms: Check text length
    const text = extractPostText(postEl);
    if (text.length < MIN_TEXT_LENGTH) {
      console.log('[ViFake] Skipping post (text too short):', text.length, 'chars');
      return;
    }
    console.log('[ViFake] Injecting button for post with', text.length, 'chars');
    injectButtonToElement(postEl);
  }

  function findMainVideoContainer(element) {
    // Find the highest parent that contains a video element
    let current = element;
    let mainContainer = null;
    
    while (current && current !== document.body) {
      // Check if this container has a video element
      if (current.querySelector('video')) {
        mainContainer = current;
      }
      
      // Stop at known container boundaries
      if (current.classList.contains('css-6wvhtq-7937d88b--ArticleItemContainer') ||
          current.classList.contains('DivVideoContainer') ||
          current.tagName === 'ARTICLE') {
        break;
      }
      
      current = current.parentElement;
    }
    
    return mainContainer;
  }

  function getVideoId(container) {
    // Generate unique ID for video container to prevent duplicates
    const video = container.querySelector('video');
    if (video && video.src) {
      // Use video URL as unique identifier
      return video.src.split('?')[0]; // Remove query params
    }
    
    // Fallback: use container's position or class
    const position = container.getBoundingClientRect();
    return `${container.tagName}_${position.top}_${position.left}`;
  }

  function injectButtonToElement(targetEl) {
    // Mark as scanned to prevent duplicates
    targetEl.setAttribute(SCAN_ATTR, 'true');

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
      handleCheckClick(targetEl, btn, container);
    });

    container.appendChild(btn);

    // Insert into the post HEADER (next to author name / "..." button)
    if (PLATFORM === 'facebook') {
      container.classList.add('vifake-container--header');

      // Strategy 1: find the "..." more-options button and insert the badge before it
      const moreBtn =
        targetEl.querySelector('[aria-label*="More options" i]') ||
        targetEl.querySelector('[aria-label*="Tùy chọn khác" i]') ||
        targetEl.querySelector('[aria-label*="Thêm" i][role="button"]') ||
        targetEl.querySelector('[aria-label*="options" i][role="button"]');

      if (moreBtn) {
        const headerRow = moreBtn.parentElement;
        headerRow.insertBefore(container, moreBtn);
        return;
      }

      // Strategy 2: find the header row via the author link (timestamp <a> or author <a>)
      const authorLink =
        targetEl.querySelector('a[href*="/groups/"] strong, a[role="link"] strong, h4 a, h3 a') ||
        targetEl.querySelector('a[role="link"][tabindex="0"]');
      if (authorLink) {
        // Walk up until we find a row-like div that also contains an action button or the "..." button
        let row = authorLink.parentElement;
        for (let i = 0; i < 5 && row && row !== targetEl; i++) {
          const style = window.getComputedStyle(row);
          if (style.display === 'flex' || style.display === 'inline-flex') {
            row.appendChild(container);
            return;
          }
          row = row.parentElement;
        }
      }

      // Fallback: insert before the action bar (like/comment/share)
      const actionBar = targetEl.querySelector('[role="toolbar"]');
      if (actionBar?.parentElement) {
        actionBar.parentElement.insertBefore(container, actionBar);
      } else {
        targetEl.appendChild(container);
      }
    } else if (PLATFORM === 'tiktok') {
      // For TikTok, try to insert near video controls or description
      const descContainer = targetEl.querySelector('[data-e2e="browse-video-desc"]')
        || targetEl.querySelector('[data-e2e="video-desc"]')
        || targetEl.querySelector('div[class*="DivDescription"]');
      
      if (descContainer) {
        descContainer.parentElement?.insertBefore(container, descContainer.nextSibling);
      } else {
        // Fallback: append to target element
        targetEl.appendChild(container);
      }
    } else {
      targetEl.appendChild(container);
    }
    
    // Debug: log where button was injected
    console.log(`[ViFake] Button injected into:`, targetEl.tagName, targetEl.className, 
                `Container position:`, container.parentElement?.tagName);
  }

  // ─── P2-B: Client-side quick scam score — only skips trivially clean text ───
  const SCAM_TIER1_KW = ['robux','nạp thẻ','verify acc','seed phrase','metamask','airdrop','giveaway','usdt','private key','kim cương free','free robux','xác nhận acc','xác minh acc','hack acc','connect ví','trúng thưởng'];
  function quickScamScore(text) {
    const t = text.toLowerCase();
    // Never skip if any tier-1 keyword present
    if (SCAM_TIER1_KW.some(kw => t.includes(kw))) return { skip: false };
    // Skip only if text is very short AND completely clean
    if (text.length < 20) return { skip: true };
    return { skip: false };
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

    // P2-B: skip trivially clean short text
    const preCheck = quickScamScore(text);
    if (preCheck.skip) {
      showResult(container, { label: 'SAFE', prediction: 'SAFE', confidence: 0.95,
        analysis_details: { nlp_flags: [], intent_label: '' } });
      return;
    }

    // P2-A: collect images from the post for richer analysis
    const media = extractMediaUrls(postEl);

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
        payload: { text, url, platform: PLATFORM, images: media.images },  // P2-A: include images
      });

      progress.remove();

      if (result.error) {
        showResult(container, { error: result.error });
      } else {
        showResult(container, result);
        postEl.setAttribute(SCAN_ATTR, 'checked');
        // Highlight scam keywords in the original post text
        const label = result.label || result.prediction || 'UNKNOWN';
        if (label === 'FAKE_SCAM' || label === 'SUSPICIOUS') {
          highlightScamKeywords(postEl, result);
        }
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

  // ─── Shared helpers ───

  const RISK_META = {
    SAFE:       { cls: 'vifake-risk-safe',    icon: '✅', text: 'An toàn',         badge: 'safe' },
    SUSPICIOUS: { cls: 'vifake-risk-warn',    icon: '⚠️', text: 'Đáng ngờ',       badge: 'warn' },
    FAKE_SCAM:  { cls: 'vifake-risk-danger',  icon: '🚨', text: 'Lừa đảo',        badge: 'danger' },
    TOXIC:      { cls: 'vifake-risk-danger',  icon: '🚨', text: 'Độc hại',         badge: 'danger' },
    UNKNOWN:    { cls: 'vifake-risk-neutral', icon: '❓', text: 'Không xác định', badge: 'neutral' },
  };

  const RISK_LEVEL_META = {
    HIGH:   { cls: 'vifake-rl-high',   text: 'Nguy cơ cao' },
    MEDIUM: { cls: 'vifake-rl-medium', text: 'Nguy cơ vừa' },
    LOW:    { cls: 'vifake-rl-low',    text: 'Nguy cơ thấp' },
  };

  const INTENT_NAMES = {
    credential_harvest: 'Thu thập thông tin',
    money_transfer:     'Chuyển tiền / nạp thẻ',
    urgency_pressure:   'Tạo áp lực khẩn cấp',
    fake_reward:        'Phần thưởng giả mạo',
    grooming_isolation: 'Tiếp cận / cô lập trẻ em',
    fake_job:           'Việc làm giả mạo',
    crypto_fraud:       'Lừa đảo tiền số',
  };

  // Human-readable Vietnamese labels for API flag codes
  const FLAG_DISPLAY = {
    pay_first_scheme:   '💸 Bắt thanh toán trước',
    robux_phishing:     '🎮 Lừa đảo Robux/game',
    gift_card_scam:     '🎁 Lừa đảo thẻ nạp',
    crypto_fraud:       '🪙 Lừa đảo tiền số',
    credential_harvest: '🔑 Thu thập mật khẩu',
    fake_reward:        '🏆 Phần thưởng giả',
    urgency_pressure:   '⏰ Áp lực khẩn cấp',
    grooming:           '⚠️ Tiếp cận trẻ em',
    money_transfer:     '💰 Yêu cầu chuyển tiền',
    fake_job:           '💼 Việc làm giả mạo',
    financial_scam:     '💳 Lừa đảo tài chính',
    phishing:           '🎣 Giả mạo trang web',
  };

  // Confidence meter bar HTML
  function buildConfidenceBar(pct, label) {
    const color = label === 'SAFE' ? 'var(--vf-safe)'
                : label === 'SUSPICIOUS' ? 'var(--vf-warn)'
                : 'var(--vf-danger)';
    return `
      <div class="vifake-conf-row">
        <span class="vifake-conf-label">Độ tin cậy</span>
        <div class="vifake-conf-track">
          <div class="vifake-conf-fill" style="--conf-w:${pct}%;--conf-color:${color}"></div>
        </div>
        <span class="vifake-conf-pct">${pct}%</span>
      </div>
    `;
  }

  // Intent bars HTML
  function buildIntentBars(intentScores) {
    let html = '';
    for (const [key, name] of Object.entries(INTENT_NAMES)) {
      const score = intentScores[key] || 0;
      if (score <= 0.04) continue;
      const pct = Math.round(score * 100);
      const danger = pct >= 70 ? 'high' : pct >= 40 ? 'mid' : 'low';
      html += `
        <div class="vifake-intent-row">
          <span class="vifake-intent-name">${name}</span>
          <div class="vifake-intent-bar-bg">
            <div class="vifake-intent-bar vifake-intent-${danger}" style="--target-width:${pct}%"></div>
          </div>
          <span class="vifake-intent-pct">${pct}%</span>
        </div>`;
    }
    return html;
  }

  // Score breakdown (NLP + fusion) — shows exact numbers per analysis engine
  function buildScoreBreakdown(details) {
    const nlpPct    = Math.round((details.nlp_confidence || 0) * 100);
    const fusionPct = Math.round((details.fusion_score   || 0) * 100);
    if (!nlpPct && !fusionPct) return '';
    const method = details.nlp_method === 'vietnamese_scam_engine' ? 'Quy tắc + NLP' : 'PhoBERT AI';
    function barColor(p) {
      return p >= 70 ? 'var(--vf-danger)' : p >= 40 ? 'var(--vf-warn)' : 'var(--vf-safe)';
    }
    let rows = '';
    if (nlpPct) rows += `
      <div class="vifake-score-row">
        <span class="vifake-score-name">Văn bản (${escapeHtml(method)})</span>
        <div class="vifake-conf-track"><div class="vifake-conf-fill" style="--conf-w:${nlpPct}%;--conf-color:${barColor(nlpPct)}"></div></div>
        <span class="vifake-conf-pct">${nlpPct}%</span>
      </div>`;
    if (fusionPct) rows += `
      <div class="vifake-score-row">
        <span class="vifake-score-name">Tổng hợp (AI)</span>
        <div class="vifake-conf-track"><div class="vifake-conf-fill" style="--conf-w:${fusionPct}%;--conf-color:${barColor(fusionPct)}"></div></div>
        <span class="vifake-conf-pct">${fusionPct}%</span>
      </div>`;
    return `<div class="vifake-score-breakdown"><p class="vifake-section-title">Điểm chi tiết</p>${rows}</div>`;
  }

  // Flags with Vietnamese human-readable labels
  function buildFlagsHtml(flags) {
    if (!flags.length) return '';
    const tags = flags.map(f => {
      const rawKey = f.includes(':') ? f.split(':')[1] : f;
      const key = rawKey.toLowerCase();
      // Match against FLAG_DISPLAY by checking if any key is a substring
      const matchKey = Object.keys(FLAG_DISPLAY).find(k => key.includes(k) || k.includes(key));
      const label = matchKey ? FLAG_DISPLAY[matchKey] : rawKey.replace(/_/g, ' ');
      return `<span class="vifake-flag-tag">${escapeHtml(label)}</span>`;
    }).join('');
    return `<div class="vifake-flags-section"><p class="vifake-section-title">⚡ Dấu hiệu phát hiện</p><div class="vifake-flags">${tags}</div></div>`;
  }

  // Advisory text
  function buildAdvisory(label) {
    const tips = {
      FAKE_SCAM: 'Đây có thể là nội dung lừa đảo. Hãy nói chuyện với con về cách nhận biết lừa đảo trực tuyến và <strong>không bao giờ cung cấp thông tin cá nhân hay chuyển tiền</strong> theo yêu cầu trên mạng.',
      SUSPICIOUS: 'Nội dung có một số dấu hiệu đáng ngờ. Hãy <strong>kiểm tra thêm</strong> trước khi cho con tương tác và thảo luận về lý do tại sao nội dung này có thể không đáng tin.',
      TOXIC: 'Nội dung này có thể gây hại cho trẻ em. Hãy <strong>hạn chế trẻ tiếp cận</strong> và trao đổi với con về an toàn trực tuyến.',
    };
    const tip = tips[label];
    if (!tip) return '';
    return `<div class="vifake-action-hint"><span class="vifake-hint-icon">💡</span><span>${tip}</span></div>`;
  }

  // Attach close + auto-dismiss behaviour to a panel
  function attachPanelBehaviour(panel, label) {
    const closeBtn = panel.querySelector('.vifake-close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        panel.classList.add('vifake-dismiss');
        setTimeout(() => panel.remove(), 280);
      });
    }
    // Auto-dismiss SAFE results after 10 s
    if (label === 'SAFE') {
      const bar = panel.querySelector('.vifake-autodismiss-bar');
      if (bar) bar.style.animationDuration = '10s';
      setTimeout(() => {
        if (!panel.isConnected) return;
        panel.classList.add('vifake-dismiss');
        setTimeout(() => panel.remove(), 280);
      }, 10000);
    }
  }

  // ─── Highlight scam keywords in post DOM ───────────────────────────────
  /**
   * Walk text nodes inside postEl and wrap scam keyword matches with
   * <span class="vifake-hl" data-vifake-tip="⚠ Nghi ngờ lừa đảo">...</span>
   * Uses API-returned flags + a hardcoded keyword list so it works even when
   * flags are empty.
   */
  function highlightScamKeywords(postEl, result) {
    try {
      const details = result.analysis_details || {};
      const flags   = details.nlp_flags || [];

      // P3-A: Tiered keyword list \u2014 prevents false highlights on legitimate content
      // Tier-1: always highlight when verdict is FAKE_SCAM / SUSPICIOUS
      const TIER1 = [
        'free robux', 'verify acc', 'seed phrase', 'private key', 'connect v\u00ed',
        'x\u00e1c nh\u1eadn acc', 'x\u00e1c minh acc', 'hack acc', 'tool hack', 'kim c\u01b0\u01a1ng free',
        'skin free', 't\u00e0i kho\u1ea3n b\u1ecb kh\u00f3a', 'n\u1ea1p th\u1ebb', 'n\u1ea1p ti\u1ec1n', 'chuy\u1ec3n kho\u1ea3n',
        'giveaway', 'airdrop', 'usdt', 'metamask', 'robux', 'click v\u00e0o link',
        'bit.ly', 'cutt.ly', 'tinyurl', 'shorturl', 'link x\u00e1c nh\u1eadn',
      ];
      // Tier-2: only highlight when confidence \u226570%
      const confPctHL = Math.round((result.confidence || 0) * 100);
      const TIER2 = confPctHL >= 70 ? [
        'mi\u1ec5n ph\u00ed', 'kh\u1ea9n c\u1ea5p', 'tr\u00fang th\u01b0\u1edfng', 'tr\u00fang gi\u1ea3i', 'nh\u1eadn qu\u00e0', 'nh\u1eadn th\u01b0\u1edfng',
        'nhanh tay', 's\u1ed1 l\u01b0\u1ee3ng c\u00f3 h\u1ea1n', 'eth', 'free',
      ] : [];

      // Extract keyword strings from flags (e.g. "FINANCIAL_SCAM:robux_phishing" \u2192 "robux_phishing")
      const flagKeywords = flags
        .map(f => f.includes(':') ? f.split(':')[1].replace(/_/g, ' ') : null)
        .filter(Boolean);

      const allKeywords = [...new Set([...TIER1, ...TIER2, ...flagKeywords])]
        .sort((a, b) => b.length - a.length); // longest first to avoid partial matches

      if (allKeywords.length === 0) return;

      // Build one regex from all keywords
      const escapedParts = allKeywords.map(k =>
        k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      );
      const regex = new RegExp(`(${escapedParts.join('|')})`, 'gi');

      // Walk text nodes — skip script/style/our own injected nodes
      const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'INPUT']);
      const walker = document.createTreeWalker(postEl, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          if (!node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
          const p = node.parentElement;
          if (!p) return NodeFilter.FILTER_REJECT;
          if (SKIP_TAGS.has(p.tagName)) return NodeFilter.FILTER_REJECT;
          if (p.classList.contains('vifake-hl')) return NodeFilter.FILTER_REJECT;
          if (p.closest('.vifake-result-panel, .vifake-container')) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_ACCEPT;
        }
      });

      const nodesToProcess = [];
      let node;
      while ((node = walker.nextNode())) nodesToProcess.push(node);

      nodesToProcess.forEach(textNode => {
        const text = textNode.nodeValue;
        if (!regex.test(text)) return;
        regex.lastIndex = 0;

        const frag = document.createDocumentFragment();
        let last = 0;
        let match;
        while ((match = regex.exec(text)) !== null) {
          if (match.index > last) {
            frag.appendChild(document.createTextNode(text.slice(last, match.index)));
          }
          const span = document.createElement('span');
          span.className = 'vifake-hl';
          span.setAttribute('data-vifake-tip', '⚠ Nghi ngờ lừa đảo');
          span.textContent = match[0];
          frag.appendChild(span);
          last = regex.lastIndex;
        }
        if (last < text.length) {
          frag.appendChild(document.createTextNode(text.slice(last)));
        }
        textNode.parentNode.replaceChild(frag, textNode);
      });
    } catch (e) {
      // Never crash the page — highlighting is cosmetic only
      console.debug('[ViFake] highlight error:', e);
    }
  }

  // ─── Show Result Panel (Facebook / YouTube text posts) ───
  function showResult(container, result) {
    container.querySelector(`.${RESULT_CLASS}`)?.remove();

    const panel = document.createElement('div');
    panel.className = RESULT_CLASS;

    if (result.error) {
      panel.classList.add('vifake-error');
      panel.innerHTML = `
        <div class="vifake-result-header vifake-risk-error">
          <span class="vifake-result-icon">⚠️</span>
          <span class="vifake-result-label">Lỗi phân tích</span>
          <button class="vifake-close-btn" title="Đóng">×</button>
        </div>
        <div class="vifake-result-body">
          <p class="vifake-error-msg">${escapeHtml(result.error)}</p>
          <p class="vifake-error-hint">Kiểm tra kết nối API trong cài đặt extension.</p>
        </div>
      `;
      container.appendChild(panel);
      attachPanelBehaviour(panel, 'ERROR');
      return;
    }

    const label     = result.label || result.prediction || 'UNKNOWN';
    const confidence = result.confidence || 0;
    const riskLevel  = result.risk_level || '';
    const details    = result.analysis_details || {};
    const intentLabel = details.intent_label || '';
    const intentExpl  = details.intent_explanation || '';
    const meta       = RISK_META[label] || RISK_META.SUSPICIOUS;
    const confPct    = Math.round(confidence * 100);
    const rlMeta     = RISK_LEVEL_META[riskLevel] || null;

    // FIX: intent scores are nested under .intents, not at top level
    const intentScores = details.intent?.intents || {};
    const intentHtml   = buildIntentBars(intentScores);
    const flags        = details.nlp_flags || [];

    panel.innerHTML = `
      <div class="vifake-result-header ${meta.cls}">
        <span class="vifake-result-icon">${meta.icon}</span>
        <span class="vifake-result-label">${meta.text}</span>
        ${rlMeta ? `<span class="vifake-risk-level-badge ${rlMeta.cls}">${rlMeta.text}</span>` : ''}
        <button class="vifake-close-btn" title="Đóng">×</button>
      </div>
      ${label === 'SAFE' ? '<div class="vifake-autodismiss-bar"></div>' : ''}
      <div class="vifake-result-body">
        ${buildConfidenceBar(confPct, label)}
        ${buildScoreBreakdown(details)}
        ${intentLabel ? `<p class="vifake-intent-primary">🎯 <strong>Ý định phát hiện:</strong> ${escapeHtml(intentLabel)}</p>` : ''}
        ${intentExpl  ? `<p class="vifake-intent-expl">${escapeHtml(intentExpl)}</p>` : ''}
        ${intentHtml  ? `<div class="vifake-intent-section"><p class="vifake-section-title">Phân tích ý định</p>${intentHtml}</div>` : ''}
        ${buildFlagsHtml(flags)}
        ${label === 'SAFE' ? `<p class="vifake-safe-msg">✓ Không phát hiện dấu hiệu nguy hiểm. Kết quả này sẽ tự đóng sau 10 giây.</p>` : ''}
        ${buildAdvisory(label)}
      </div>
    `;

    container.appendChild(panel);
    attachPanelBehaviour(panel, label);
  }

  // ─── Show Video Result Panel (TikTok) ───
  function showVideoResult(container, result) {
    container.querySelector(`.${RESULT_CLASS}`)?.remove();

    const panel = document.createElement('div');
    panel.className = RESULT_CLASS;

    const verdict      = result.verdict || 'UNKNOWN';
    const confidence   = result.confidence || 0;
    const isAi         = result.is_ai_generated || false;
    const aiConfidence = result.ai_confidence || 0;
    const transcript   = result.transcript || '';
    const explanation  = result.explanation || '';
    const intents      = result.intents || {};
    const meta         = RISK_META[verdict] || RISK_META.SUSPICIOUS;
    const confPct      = Math.round(confidence * 100);
    const aiPct        = Math.round(aiConfidence * 100);

    const intentHtml = buildIntentBars(intents);
    const transcriptId = `vf-tr-${Date.now()}`;

    panel.innerHTML = `
      <div class="vifake-result-header ${meta.cls}">
        <span class="vifake-result-icon">${meta.icon}</span>
        <span class="vifake-result-label">${meta.text}</span>
        ${isAi ? `<span class="vifake-ai-badge" title="Video AI-generated (${aiPct}%)">🤖 AI ${aiPct}%</span>` : ''}
        <button class="vifake-close-btn" title="Đóng">×</button>
      </div>
      ${verdict === 'SAFE' ? '<div class="vifake-autodismiss-bar"></div>' : ''}
      <div class="vifake-result-body">
        ${buildConfidenceBar(confPct, verdict)}
        ${explanation ? `<p class="vifake-explanation">${escapeHtml(explanation)}</p>` : ''}

        ${isAi ? `
          <div class="vifake-ai-section">
            <div class="vifake-ai-row">
              <span>🤖 Video có thể được tạo bằng AI</span>
              <div class="vifake-ai-conf-track">
                <div class="vifake-ai-conf-fill" style="width:${aiPct}%"></div>
              </div>
              <span class="vifake-ai-pct">${aiPct}%</span>
            </div>
          </div>
        ` : ''}

        ${intentHtml ? `<div class="vifake-intent-section"><p class="vifake-section-title">Phân tích ý định</p>${intentHtml}</div>` : ''}

        ${transcript ? `
          <div class="vifake-transcript-section">
            <button class="vifake-transcript-toggle" data-target="${transcriptId}">
              📝 Transcript <span class="vifake-toggle-arrow">▶</span>
            </button>
            <div class="vifake-transcript vifake-transcript-collapsed" id="${transcriptId}">${escapeHtml(transcript)}</div>
          </div>
        ` : ''}

        ${buildAdvisory(verdict)}
      </div>
    `;

    // Wire transcript toggle
    const toggleBtn = panel.querySelector('.vifake-transcript-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const target = panel.querySelector(`#${transcriptId}`);
        const arrow  = toggleBtn.querySelector('.vifake-toggle-arrow');
        const isOpen = !target.classList.contains('vifake-transcript-collapsed');
        target.classList.toggle('vifake-transcript-collapsed', isOpen);
        arrow.textContent = isOpen ? '▶' : '▼';
      });
    }

    container.appendChild(panel);
    attachPanelBehaviour(panel, verdict);
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
    
    console.log(`[ViFake] Scanning ${PLATFORM} with ${selectors.length} selectors:`, selectors);
    
    for (const sel of selectors) {
      const posts = document.querySelectorAll(sel);
      console.log(`[ViFake] Selector "${sel}" found ${posts.length} elements`);
      
      posts.forEach(post => {
        if (seen.has(post)) return;
        seen.add(post);
        totalFound++;
        
        // For TikTok, be more permissive with filtering
        if (PLATFORM === 'tiktok') {
          console.log(`[ViFake] TikTok element found:`, post.tagName, post.className);
          if (post.hasAttribute(SCAN_ATTR)) {
            console.log(`[ViFake] Already scanned, but checking if button exists...`);
            const existingBtn = post.querySelector(`.${BTN_CLASS}`);
            if (!existingBtn) {
              console.log(`[ViFake] Button missing, re-injecting...`);
              post.removeAttribute(SCAN_ATTR); // Remove marker to force re-inject
            } else {
              console.log(`[ViFake] Button exists, skipping`);
              return;
            }
          }
          passedFilter++;
          injectCheckButton(post);
          return;
        }
        
        if (post.hasAttribute(SCAN_ATTR)) return;
        if (!isLikelyFeedPost(post)) return;
        passedFilter++;
        injectCheckButton(post);
      });
    }
    
    if (totalFound > 0) {
      console.log(`[ViFake] Scan: ${totalFound} candidates, ${passedFilter} passed filter`);
    } else {
      console.log(`[ViFake] No elements found with current selectors`);
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
  
  // Clear processed videos when page changes significantly
  if (PLATFORM === 'tiktok') {
    // Listen for navigation changes
    let lastUrl = location.href;
    setInterval(() => {
      if (location.href !== lastUrl) {
        console.log('[ViFake] Page changed, clearing video cache');
        window.vifakeProcessedVideos = new Set();
        lastUrl = location.href;
      }
    }, 1000);
  }

  // For TikTok, also scan every 3 seconds since content loads dynamically
  // Reduced frequency to prevent infinite loop
  if (PLATFORM === 'tiktok') {
    // Add debounce to prevent excessive scanning
    let lastScanTime = 0;
    const SCAN_INTERVAL = 3000; // 3 seconds
    const DEBOUNCE_TIME = 500; // 500ms debounce
    
    function debouncedScan() {
      const now = Date.now();
      if (now - lastScanTime > DEBOUNCE_TIME) {
        lastScanTime = now;
        scanForPosts();
      }
    }
    
    setInterval(debouncedScan, SCAN_INTERVAL);
    
    // Debug: Add command to clear all scan markers
    console.log('[ViFake] TikTok mode enabled. Run this in console to reset all buttons:');
    console.log('[ViFake] document.querySelectorAll("[data-vifake-scanned]").forEach(el => el.removeAttribute("data-vifake-scanned"))');
  }

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
