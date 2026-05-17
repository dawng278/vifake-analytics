# Manual Test Scripts

Các file trong thư mục này là **script test thủ công / demo**, không phải test CI mặc định.

## Chạy nhanh

- Video pipeline smoke test:
  - `python tests/manual/test_video_ai.py`
- Enhanced AI video test:
  - `python tests/manual/test_enhanced_ai.py`
- API video endpoint test:
  - `python tests/manual/test_api_video.py`
- Demo end-to-end local:
  - `python tests/manual/test_demo.py`
- Teencode normalizer debug:
  - `python tests/manual/test_norm.py`
- Rule-based scam detector regression:
  - `python tests/manual/test_scam_detection_improvements.py`

## Lưu ý

- Nên chạy từ root repo.
- Một số script cần backend API đang chạy tại `http://localhost:8000`.
- Đây là test hỗ trợ phân tích/chẩn đoán, không đại diện benchmark chính thức.
