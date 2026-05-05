# ViFake Analytics Web Interface

Giao diện web kiểm thử local cho hệ thống ViFake Analytics trước khi phát triển extension.

## 🚀 Khởi động

### Bước 1: Khởi động API Gateway
```bash
cd backend_services/api_gateway
python3 main.py
```

### Bước 2: Mở giao diện web
Mở file `index.html` trong trình duyệt:
```bash
# Mở trực tiếp
open web_interface/index.html

# Hoặc khởi động server web đơn giản
cd web_interface
python3 -m http.server 8080
# Sau đó mở http://localhost:8080
```

## 🎯 Tính năng

### 📊 Bảng điều khiển chính
- **Phân tích nội dung**: Nhập URL để kiểm tra lừa đảo
- **Trạng thái hệ thống**: Kiểm tra kết nối các thành phần
- **Kết quả real-time**: Xem tiến trình phân tích trực tiếp
- **Test mẫu**: Các URL mẫu để kiểm tra nhanh

### 🔍 Các nền tảng hỗ trợ
- **YouTube**: Phân tích video và comments
- **Facebook**: Kiểm tra posts và links
- **TikTok**: Quét nội dung video ngắn

### 🤖 Công nghệ AI
- **PhoBERT**: Phân tích văn bản tiếng Việt
- **CLIP**: Phân tích hình ảnh đa ngôn ngữ
- **XGBoost**: Hợp nhất kết quả multi-modal
- **Neo4j**: Phân tích mạng lưới botnet

## 📱 Giao diện

### 🎨 Thiết kế
- **Responsive**: Tương thích mobile và desktop
- **Modern UI**: Bootstrap 5 + Font Awesome
- **Vietnamese**: Giao diện tiếng Việt đầy đủ
- **Real-time**: Cập nhật tiến trình live

### 📈 Các phần chính
1. **Header**: Thông tin hệ thống và trạng thái kết nối
2. **Form phân tích**: Input URL và cấu hình
3. **Status cards**: Trạng thái các service
4. **Progress tracking**: 6 giai đoạn phân tích
5. **Results display**: Kết quả chi tiết với metrics

## 🔧 API Integration

### Authentication
```javascript
const AUTH_TOKEN = '$AUTH_TOKEN';
const headers = {
    'Authorization': `Bearer ${AUTH_TOKEN}`,
    'Content-Type': 'application/json'
};
```

### Endpoints
- `GET /api/v1/health` - Kiểm tra sức khỏe hệ thống
- `POST /api/v1/analyze` - Bắt đầu phân tích
- `GET /api/v1/job/{job_id}` - Kiểm tra tiến trình
- `GET /api/v1/result/{job_id}` - Lấy kết quả
- `GET /api/v1/stats` - Thống kê hệ thống

## 🧪 Testing

### Test mẫu có sẵn
- **Nội dung an toàn**: `https://youtube.com/watch?v=safe123`
- **Nội dung lừa đảo**: `https://youtube.com/watch?v=scam456`
- **Nội dung TikTok**: `https://tiktok.com/@user/test789`

### Test thủ công
1. Nhập URL thực tế
2. Chọn nền tảng phù hợp
3. Click "Bắt đầu phân tích"
4. Theo dõi tiến trình real-time
5. Xem kết quả chi tiết

## 📊 Kết quả phân tích

### Metrics hiển thị
- **Phân loại**: SAFE / FAKE_SCAM / FAKE_TOXIC / FAKE_MISINFO
- **Mức độ rủi ro**: LOW / MEDIUM / HIGH
- **Độ tin cậy**: 0-100%
- **Thời gian xử lý**: Giây
- **Chi tiết AI**: Vision + NLP + Fusion scores

### Color coding
- 🟢 **Xanh**: An toàn / Low risk
- 🟡 **Vàng**: Cảnh báo / Medium risk  
- 🔴 **Đỏ**: Nguy hiểm / High risk

## 🔄 Real-time Updates

### Progress stages
1. 🔍 Tìm kiếm metadata
2. 🛡️ Kiểm tra an toàn
3. 🖼️ Phân tích hình ảnh (CLIP)
4. 📝 Phân tích văn bản (PhoBERT)
5. 🧠 Hợp nhất kết quả (XGBoost)
6. 🕸️ Cập nhật đồ thị Neo4j

### Auto-refresh
- **System status**: Cập nhật 30 giây/lần
- **Job progress**: Cập nhật 1 giây/lần
- **Connection status**: Real-time

## 🛠️ Troubleshooting

### Common issues
1. **API không phản hồi**: Kiểm tra API Gateway đang chạy
2. **Authentication failed**: Verify token `$AUTH_TOKEN`
3. **CORS errors**: API Gateway cần cấu hình CORS
4. **Timeout**: Tăng timeout cho request lớn

### Debug mode
Mở browser console (F12) để xem:
- Network requests
- JavaScript errors
- API responses

## 📝 Development Notes

### File structure
```
web_interface/
├── index.html          # Main interface
├── README.md           # Documentation
└── assets/            # Static assets (CSS, JS, images)
```

### Customization
- **Colors**: Modify CSS variables in `:root`
- **API endpoints**: Update `API_BASE` constant
- **Authentication**: Change `AUTH_TOKEN`
- **Languages**: Add i18n support

## 🚀 Extension Development

Giao diện này là foundation cho:
- **Chrome Extension**: Content script injection
- **Firefox Extension**: WebExtensions API
- **Mobile App**: React Native components
- **Desktop App**: Electron wrapper

### Next steps
1. Convert to React/Vue components
2. Add browser extension APIs
3. Implement background processing
4. Add storage and persistence
5. Create deployment package

## 🔒 Security & Privacy

### Features
- **Zero-trust processing**: Không lưu trữ dữ liệu nhạy cảm
- **Local-only**: Chạy hoàn toàn local
- **Synthetic training**: 100% dữ liệu synthetic
- **Ethical AI**: Tuân thủ principles AI ethics

### Compliance
- **Privacy-by-Design**: Kiến thiết bảo vệ privacy
- **GDPR ready**: Sẵn sàng cho GDPR
- **Child safety**: Bảo vệ trẻ em trực tuyến
- **Vietnamese context**: Hiểu biết văn hóa Việt Nam

---

**ViFake Analytics - Bảo vệ trẻ em Việt Nam trực tuyến** 🛡️
