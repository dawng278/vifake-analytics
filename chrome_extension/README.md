# ViFake Chrome Extension

Phát hiện nội dung lừa đảo nhắm vào trẻ em Việt Nam — tích hợp 1-click vào Facebook, YouTube, TikTok.

## 🎯 Tính năng

- **1-Click Check**: Nút "Kiểm tra ViFake" xuất hiện dưới mỗi bài đăng Facebook
- **Kết quả tức thì**: Animation scanning → SAFE / SUSPICIOUS / FAKE_SCAM
- **Popup thông minh**: 5 intent categories, confidence score, gợi ý cho phụ huynh
- **Badge icon**: Đổi màu theo mức độ rủi ro (xanh/vàng/đỏ)

## 🔧 Cài đặt (Dev Mode)

### Bước 1: Deploy Cloud API (bắt buộc)
Extension không thể gọi `localhost`. Deploy API lên Render.com:

```bash
# Từ thư mục gốc project
git push origin main
# Vào render.com → New Web Service → Connect GitHub → chọn repo
# Render tự detect Dockerfile và deploy
```

### Bước 2: Load Extension vào Chrome

1. Mở `chrome://extensions/`
2. Bật **Developer mode** (góc phải trên)
3. Nhấn **Load unpacked**
4. Chọn thư mục `chrome_extension/`
5. Extension xuất hiện trên thanh toolbar

### Bước 3: Cấu hình
1. Click icon ViFake trên toolbar
2. Vào tab **Cài đặt**
3. Nhập API URL (ví dụ: `https://vifake-api.onrender.com`)
4. Nhập Auth Token
5. Nhấn **Kiểm tra kết nối** để verify

## 🏗️ Kiến trúc

```
chrome_extension/
├── manifest.json              # Manifest V3
├── background/
│   └── service-worker.js      # API calls, state, badge updates
├── content/
│   ├── content.js             # MutationObserver, button injection, UI
│   └── content.css            # CSS-only animations (<8KB)
├── popup/
│   ├── popup.html             # Popup UI
│   ├── popup.css              # Dark theme styles
│   └── popup.js               # Stats, recent scans, settings
├── icons/                     # 16x16, 48x48, 128x128
├── privacy-policy.html        # Chrome Web Store requirement
└── README.md
```

## ⚡ Điểm kỹ thuật quan trọng

### Facebook SPA
- Dùng `MutationObserver` thay vì `DOMContentLoaded` vì Facebook không reload khi scroll
- Debounce 500ms để tránh scan quá nhiều mutation

### DOM Targeting (bền vững)
- Target `[role="article"]`, `[dir="auto"]`, `aria-label` thay vì class names
- Facebook thay đổi minified class (x1abc) thường xuyên — aria/data attributes ổn định hơn

### Performance
- CSS-only animations (`@keyframes`, `transition`) — không dùng JS animation library
- Total extension size < 200KB
- Không block main thread — tất cả API calls qua service worker

### Privacy-by-Design
- Chỉ đọc text khi user nhấn nút (không auto-scan mặc định)
- RAM-only processing — không lưu nội dung bài đăng
- Privacy Policy rõ ràng cho Chrome Web Store review

## 📋 Phase Plan

| Phase | Nội dung | Thời gian |
|-------|----------|-----------|
| Phase 0 | Deploy Cloud API (Render.com) | Ưu tiên #1 |
| Phase 1 | Extension MVP — inject button + popup | 2 tuần |
| Phase 2 | UX nâng cao — animation, sidebar, auto-scan | 1 tuần |
| Phase 3 | Publish Chrome Web Store + Firefox Add-on | 1 tuần |
