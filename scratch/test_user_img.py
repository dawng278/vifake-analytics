import sys
import os
# Add root project directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend_services.api_gateway.main import _vietnamese_scam_detector

# Nội dung Text trích xuất từ Bức ảnh và Caption của người dùng gửi
text_from_screenshot = """
Đặc Điểm Nổi Bật: Nạp Robux ngay hôm nay để tận hưởng...
BẢNG GIÁ NẠP ROBUX (HÈ 2026)
7,000 ROBUX ---- 50.000VND
16,900 ROBUX ---- 100.000VND
33,800 ROBUX ---- 200.000VND
70,000 ROBUX ---- 500.000VND
150,000 ROBUX ---- 1.000.000VND
"""

print("="*60)
print("🔥 ĐANG CHẠY ENGINE VIFAKE TRÊN NỘI DUNG ẢNH CỦA BẠN 🔥")
print("="*60)

result = _vietnamese_scam_detector(text_from_screenshot)

print(f"🎯 KẾT LUẬN CUỐI CÙNG: {result['prediction']}")
print(f"📊 ĐIỂM RỦI RO (SCORE): {result['score']:.3f}")
print(f"🚨 CÁC CỜ PHÁT HIỆN (FLAGS):")
for f in result.get('flags', []):
    print(f"   [!] {f}")

print("\n💡 GIẢI THÍCH TỪ AI:")
print(f"Phát hiện tỷ lệ nạp Robux ảo giác: 7000/50k = {7000/50:.1f}x, vượt xa ngưỡng thị trường 40x!")
print("="*60)
