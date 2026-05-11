import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend_services.api_gateway.main import _vietnamese_scam_detector

sample_text = """
MONG MỌI NGƯỜI ĐÃ GIAO DỊCH VỚI MÌNH THÌ MÌNH XIN COMMENT VÀ LIKE NHA
🚚Dịch Vụ 
💰SELL ROBUX GP - THU BÁN MM2 
+GDTG , đổi tiền , gạch thẻ , có đủ all banking
+ Robux 120h , robux sạch , kor headless , gift gamepass mọi game có phần gift quà tặng
STK VÀ THÔNG TIN 
MB BANK: 26090968868386
GTF: 0921201882
ZALO: 0921201882
ROBLOX: GiaKiennnnnn name phụ Mhuyy
CẢM ƠN MỌI NGƯỜI ĐÃ ĐỌC HẾT , CHÚC CÁC BẠN 1 NGÀY VV❤️
"""

print("="*60)
print("🔬 CHẠY THỬ NGHIỆM GIAO DỊCH TRỰC TIẾP P2P")
print("="*60)

result = _vietnamese_scam_detector(sample_text)

print(f"PREDICTION: {result['prediction']}")
print(f"FLAGS: {result.get('flags', [])}")
print("="*60)
