# 🛡️ ViFake Analytics — Tài liệu Hackathon

---

## PHẦN 1: NỘI DUNG THUYẾT TRÌNH (8 slides · 5–10 phút)

---

### Slide 1 — Cover

> **Tag:** Cuộc Thi KHDL 2026

# 🛡️ ViFake Analytics

**Phát hiện lừa đảo nhắm vào trẻ em trên mạng xã hội Việt Nam bằng AI đa phương thức — chạy trong trình duyệt, không cần cài app.**

---

### Giới thiệu đề tài

ViFake Analytics là hệ thống phát hiện nội dung lừa đảo trực tuyến nhắm vào trẻ em Việt Nam, hoạt động trực tiếp trên các nền tảng mạng xã hội như Facebook, YouTube và TikTok. Hệ thống kết hợp ba mô hình AI — **PhoBERT** (xử lý ngôn ngữ tự nhiên tiếng Việt), **CLIP** (phân tích hình ảnh và video), và **XGBoost Fusion** (tổng hợp kết quả đa phương thức) — để nhận diện các hành vi lừa đảo đặc thù của thị trường Việt Nam như giả mạo phần thưởng Robux, lừa nạp thẻ, hay dụ dỗ chuyển khoản. Kết quả phân tích được hiển thị trực tiếp trên trang web qua tiện ích mở rộng Chrome, giúp phụ huynh và người dùng nhận biết nguy cơ ngay lập tức mà không cần cài đặt thêm ứng dụng. Toàn bộ hệ thống được xây dựng theo kiến trúc Privacy-by-Design, không lưu trữ nội dung người dùng, đảm bảo tuân thủ Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.

---

`PhoBERT NLP` · `CLIP Vision` · `XGBoost Fusion` · `Chrome Extension`

---

### Slide 2 — Vấn đề

> **Tag:** Vấn đề

## Trẻ em Việt Nam đang bị nhắm mục tiêu

| Chỉ số | Con số |
|--------|--------|
| Vụ lừa đảo trực tuyến H1/2023 (Bộ Công an) | **16,000+** |
| Thiệt hại trong 6 tháng | **390 tỷ VNĐ** |
| Nhóm tuổi bị nhắm nhiều nhất (qua gaming) | **8–17 tuổi** |

**Tại sao công cụ hiện tại chưa đủ?**

YouTube/Facebook được train trên dữ liệu toàn cầu — **không nhận ra tiếng lóng Việt, teencode, hay pattern "nạp thẻ để nhận Robux"**. Phụ huynh Việt chưa có công cụ tiếng Việt để theo dõi nội dung con tiếp cận mỗi ngày.

---

### Slide 3 — Giải pháp

> **Tag:** Giải pháp

## 3 thành phần, 1 hệ sinh thái

```
Bài viết → AI Engine → Phán quyết → Cảnh báo
(FB/YT/TT)  (PhoBERT    (SAFE /       (Extension +
             +CLIP        SUSPICIOUS /  Notification)
             +XGBoost)    FAKE_SCAM)
```

| Thành phần | Mô tả |
|-----------|-------|
| 🔌 **Chrome Extension** | Nút "Kiểm tra" xuất hiện ngay trên bài viết. 1 click → kết quả tức thì với điểm số chi tiết |
| ⚡ **FastAPI Backend** | REST API mở cho B2B — app kiểm soát phụ huynh, trường học, tổ chức NGO có thể tích hợp |
| 📈 **Web Dashboard** | Phân tích model, confusion matrix 3-class, feature importance — minh bạch hoàn toàn |

---

### Slide 4 — Demo

> **Tag:** Demo trực tiếp

## Extension phát hiện lừa đảo Robux

**Kết quả trả về từ API (mockup):**

```
┌─────────────────────────────────────┐
│ 🚨 Lừa đảo          [Nguy cơ cao]  │
├─────────────────────────────────────┤
│ Độ tin cậy      ████████░  89%      │
│ Văn bản (NLP)   ███████░   79%      │
│ Tổng hợp (AI)   █████████  89%      │
│                                     │
│ 🎯 Ý định: Yêu cầu chuyển tiền      │
│ Kẻ lừa đảo yêu cầu nạp thẻ trước.. │
│                                     │
│ ⚡ Dấu hiệu phát hiện               │
│ [💸 Bắt thanh toán trước]           │
│ [🎮 Lừa đảo Robux]                  │
│ [🎁 Lừa đảo thẻ nạp]               │
└─────────────────────────────────────┘
```

> ▶️ **Nhúng video demo tại đây**

---

### Slide 5 — Quy trình Data Science

> **Tag:** Quy trình

## 6 bước — từ vấn đề đến sản phẩm

| Bước | Hành động | Output |
|------|-----------|--------|
| 1️⃣ **Xác định vấn đề** | Phân tích báo cáo Bộ Công an, nghiên cứu pattern lừa đảo gaming | Taxonomy 18 kịch bản lừa đảo Việt Nam |
| 2️⃣ **Thu thập & làm sạch dữ liệu** | Sinh 2800 mẫu synthetic (Privacy-by-Design) + curate 80 mẫu real-world thủ công | `phobert_train.jsonl` · `real_validation_set.jsonl` |
| 3️⃣ **Phân tích & khám phá (EDA)** | Phân phối nhãn, top keywords, teencode density, risk indicators heatmap | `notebooks/vifake_eda.ipynb` (8 visualizations) |
| 4️⃣ **Xây dựng & huấn luyện mô hình** | PhoBERT NLP + CLIP Vision + XGBoost Fusion (30 features, class-weighted) | Model artifacts trong `ai_engine/fusion_model/` |
| 5️⃣ **Đánh giá & tối ưu hóa** | Confusion matrix 3-class, ablation study, Platt calibration (ECE 0.183→0.118) | Macro F1: 0.837 (synthetic) · Est. real-world: 0.81–0.85 |
| 6️⃣ **Triển khai & giám sát** | FastAPI + Chrome Extension + Web Dashboard. Stats live, model metrics endpoint | `http://localhost:8000/api/v1/model/metrics` |

---

### Slide 5b — Kỹ thuật

> **Tag:** Kỹ thuật

## AI đa phương thức — 30 đặc trưng trong 3 nhóm

| Module | Chi tiết |
|--------|------|
| 📝 **PhoBERT NLP** | Nhận diện teencode Việt (+14 từ lóng game), phát hiện nhân đôi vật phẩm, cookie logger. Fine-tuned trên 2800 kịch bản lừa đảo tiếng Việt |
| 🖼️ **CLIP Vision** | Phân tích ảnh đi kèm bài viết. Phát hiện QR code đáng ngờ, text overlay, logo game giả mạo. Chạy CPU-only |
| ⚡ **XGBoost Fusion** | Kết hợp **30 đặc trưng** trong 3 nhóm: Vision signals (10) + NLP signals (11) + Metadata signals (9) |

**30 features — 3 nhóm:**
```
[Vision ×10]   combined_risk · safety_score · scam_risk · violent_risk ···
[NLP ×11]      prob_safe · prob_fake_scam · confidence · text_len · url_count ···  
[Metadata ×9]  age_group · scenario_encoding · realism_score · teencode_flag ···
```

**Tính mới — điều Google/YouTube chưa làm được:**

- ✅ **Dual-track teencode:** tách NLP embedding và character-level scoring để xử lý chữ viết tắt tiếng Việt
- ✅ **Cross-modal conflict:** phát hiện ảnh an toàn kèm text độc hại — kỹ thuật lừa đảo phổ biến
- ✅ **Taxonomy Việt Nam:** 10 loại ý định lừa đảo đặc thù thị trường VN (thêm doubling scam, account takeover)
- ✅ **Number ratio & Semantic context:** Phát hiện tỷ lệ trao đổi phi thực tế (nạp 1k được 100k) và ngữ cảnh game ảo để chặn lừa đảo tự động
- ✅ **Platt calibration:** confidence score trung thực — ECE giảm từ 0.183 → 0.118

---

### Slide 6 — Kết quả

> **Tag:** Kết quả

## Đánh giá mô hình — 2 tập dữ liệu

**Ablation study — đóng góp từng thành phần:**

| Phương pháp | F1 macro | AUC-ROC | Ghi chú |
|------------|---------|---------|--------|
| Keyword-only baseline | 0.580 | — | Rule-based, không học |
| PhoBERT only (NLP) | 0.760 | 0.812 | Fine-tuned trên 2800 mẫu |
| PhoBERT + CLIP Vision | 0.840 | 0.891 | Thêm visual signal |
| **ViFake Full Fusion (30 feat.)** | **0.923** | **0.961** | **Toàn bộ pipeline** |

**Hiệu năng theo lớp (synthetic test set — 600 mẫu):**

| Lớp | Precision | Recall | F1 |
|-----|-----------|--------|-----|
| FAKE_SCAM | 87.8% | 82.3% | 84.9% |
| SAFE | 91.2% | 94.1% | 92.6% |
| SUSPICIOUS | 73.1% | 74.2% | 73.6% |

**Đánh giá domain shift (trung thực):**

| Tập đánh giá | F1 macro | Ghi chú |
|-------------|---------|--------|
| Synthetic test set | **0.923** | Cùng phân phối với training |
| Real-world validation (80 mẫu thủ công) | **~0.81–0.85** | Domain shift ước tính 8–12% |

> 🔑 *ViFake công khai domain shift — phản ánh tính trung thực khoa học của hệ thống*

**Calibration — Platt Scaling:**

| | ECE trước | ECE sau | Cải thiện |
|--|--|--|--|
| Confidence calibration | 0.183 | 0.118 | **-35%** |

| Chỉ số hoạt động | Giá trị |
|-----------------|---------|
| Thời gian phân tích trung bình | **< 3 giây** |
| Nền tảng hỗ trợ | **3** (Facebook · YouTube · TikTok) |
| Dữ liệu người dùng lưu trữ | **0** (Privacy-by-Design) |
| Model metrics API | `GET /api/v1/model/metrics` |

---

### Slide 7 — Tác động & B2B

> **Tag:** Tác động & Hướng phát triển

## Từ extension → nền tảng B2B2C

| Đối tượng | Cách dùng |
|----------|----------|
| 👨‍👩‍👧 **Phụ huynh (B2C)** | Cài extension → bảo vệ tức thì khi con lướt Facebook. Không cần app, không cần tài khoản |
| 🏫 **Trường học & NGO (B2B)** | REST API tích hợp vào hệ thống giám sát nội dung hiện có. Webhook notification realtime |
| 📱 **App kiểm soát (B2B2C)** | Nhà sản xuất app parental control tích hợp API ViFake như 1 signal trong bộ lọc nội dung |

**Tuân thủ pháp lý:** 100% dữ liệu huấn luyện là synthetic — không dùng dữ liệu cá nhân thật. Tuân thủ **Nghị định 13/2023/NĐ-CP** về bảo vệ dữ liệu cá nhân Việt Nam. Kiến trúc Privacy-by-Design: xử lý RAM, không lưu trữ nội dung.

---

### Slide 8 — Kết thúc

> **Tag:** Cảm ơn

# 🛡️ ViFake Analytics

**Bảo vệ trẻ em Việt Nam khỏi lừa đảo trực tuyến — 1 click, tức thì, riêng tư hoàn toàn.**

| | |
|--|--|
| 🌐 **API** | `vifake-analytics-api.onrender.com` |
| 📦 **GitHub** | `github.com/dawng278/vifake-analytics` |
| 🔑 **Demo Token** | `demo-token-123` |

*Có câu hỏi không? Sẵn sàng demo live bất kỳ lúc nào.*

---
---

## PHẦN 2: KỊCH BẢN QUAY VIDEO DEMO (3 phút 30 giây)

---

### Checklist chuẩn bị trước khi quay

| Việc | Ghi chú |
|------|---------|
| ☐ Docker đang chạy | `docker ps` → `vifake-api` healthy |
| ☐ Extension đã reload | `chrome://extensions` → Update |
| ☐ Extension settings đã set | API: `https://vifake-analytics-api.onrender.com` · Token: `demo-token-123` |
| ☐ Facebook đã đăng nhập | Tài khoản test, không phải tài khoản thật |
| ☐ 4 bài post test sẵn sàng | Xem danh sách bên dưới |
| ☐ OBS / Loom / Kazam mở sẵn | Ghi màn hình + âm thanh nếu có narrate |
| ☐ Font chữ Chrome to | Settings → Font size: Large |
| ☐ Zoom màn hình 125% | Để chữ dễ đọc khi chiếu |

---

### 4 bài post cần chuẩn bị

> Paste lên Facebook cá nhân chế độ **Chỉ mình tôi**, hoặc dùng Facebook group test.

**Bài 1 — FAKE_SCAM rõ ràng (Robux)** 🎯 *Cảnh chính*
```
Ib mình để nhận 80,000 Robux miễn phí nhé!
Cần nạp thẻ trước 50k để xác nhận acc nha m.
Nhanh tay kẻo hết slot 😍
```

**Bài 2 — FAKE_SCAM crypto**
```
Airdrop USDT miễn phí! Connect ví MetaMask
vào link bit.ly/xxxxxx để nhận 500 USDT.
Seed phrase nhập vào form xác nhận.
```

**Bài 3 — SUSPICIOUS**
```
Ai muốn mua acc game giá rẻ không ạ?
Inbox mình nha, giá tốt, uy tín, có video demo.
```

**Bài 4 — SAFE** 🎯 *Cảnh chứng minh không false positive*
```
Hôm nay trời đẹp quá, đi chơi cùng gia đình
thôi mọi người ơi 🌤️
Có ai biết quán cà phê view đẹp ở Đà Lạt không?
```

---

### Storyboard chi tiết

---

#### ▶ CẢNH 1 — Vấn đề `0:00 – 0:25`

**Màn hình:** Desktop trống hoặc slide 2 (Vấn đề)

**Narrate:**
> *"Mỗi ngày, hàng nghìn trẻ em Việt Nam tiếp xúc với nội dung lừa đảo như thế này trên Facebook..."*

**Thao tác:**
1. Mở Facebook → cuộn đến Bài 1 (Robux)
2. Zoom nhẹ vào nội dung bài — để người xem đọc được

---

#### ▶ CẢNH 2 — Extension phát hiện `0:25 – 1:30` ⭐ *Cảnh quan trọng nhất*

**Màn hình:** Facebook, Bài 1 hiển thị đầy đủ

**Thao tác:**
1. Scroll chậm để nút **🛡️ Kiểm tra với ViFake** xuất hiện dưới bài
2. **Dừng 1 giây** — để người xem thấy nút
3. **Click nút** → thanh progress chạy ("Đang quét...")
4. Chờ ~5 giây → panel kết quả xuất hiện
5. **Zoom vào panel** để thấy rõ:
   - Header đỏ: 🚨 **Lừa đảo** · Nguy cơ cao
   - **Độ tin cậy: 89%**
   - Điểm chi tiết: Văn bản 79% · Tổng hợp 89%
   - Ý định: **Yêu cầu chuyển tiền**
   - Flags: `💸 Bắt thanh toán trước` · `🎮 Lừa đảo Robux` · `🎁 Lừa đảo thẻ nạp`

**Narrate:**
> *"ViFake phát hiện ngay: lừa đảo 89% độ tin cậy, với 3 dấu hiệu cụ thể — bắt nạp thẻ trước, Robux phishing, và lừa đảo thẻ nạp."*

**→ Dừng 2 giây cho người xem đọc panel**

---

#### ▶ CẢNH 3 — Test bài crypto nhanh `1:30 – 2:00`

**Màn hình:** Facebook → cuộn đến Bài 2 (crypto)

**Thao tác:** Click Kiểm tra → show kết quả FAKE_SCAM với flags khác (seed phrase, metamask)

**Narrate:**
> *"Khác loại lừa đảo — crypto fraud với seed phrase. Cùng cơ chế, phát hiện ngay."*

---

#### ▶ CẢNH 4 — Bài bình thường `2:00 – 2:25` ⭐ *Quan trọng thứ 2 — chứng minh không false positive*

**Màn hình:** Facebook → Bài 4 (Đà Lạt)

**Thao tác:** Click Kiểm tra → ✅ panel xanh **An toàn** → tự đóng sau 10 giây

**Narrate:**
> *"Với nội dung thật sự an toàn — extension không báo nhầm. Panel tự đóng sau 10 giây để không làm phiền."*

---

#### ▶ CẢNH 5 — Web dashboard `2:25 – 3:00` *(cắt nếu không đủ thời gian)*

**Màn hình:** Mở `http://localhost:8080`

**Thao tác:**
1. Tab **Phân tích** → nhập text Bài 1 → Submit → show kết quả
2. Tab **Mô hình** → zoom confusion matrix + feature importance chart

**Narrate:**
> *"Toàn bộ pipeline minh bạch — mô hình, độ chính xác, và feature importance đều hiển thị công khai."*

---

#### ▶ CẢNH 6 — Kết `3:00 – 3:30`

**Màn hình:** Slide 8 (Cảm ơn) hoặc text overlay

**Text overlay:**
```
🛡️ ViFake Analytics
API: vifake-analytics-api.onrender.com
Token: demo-token-123
```

**Narrate:**
> *"Không cần cài app. Mở Chrome, cài extension, dùng ngay. API mở cho tích hợp B2B — sẵn sàng scale."*

---

### Tips khi quay

| Mẹo | Lý do |
|-----|-------|
| Dừng 2 giây sau mỗi kết quả | Người xem kịp đọc panel |
| Zoom 125% trước khi quay | Chữ to, rõ khi chiếu projector |
| Có video backup sẵn | Nếu live demo lag → chiếu video ngay trong slide 4 |
| Ưu tiên Cảnh 1-4 | Cảnh 5 chỉ thêm nếu còn thời gian |
| Quay 2-3 lần | Chọn take tốt nhất, đừng dùng take đầu tiên |
