#!/usr/bin/env python3
"""
Scam Intent Detector for ViFake Analytics
Detects WHAT the text is trying to DO to the reader, not just WHAT it says.

Key insight: Scammers don't reuse exact phrases — they change wording constantly.
But the UNDERLYING INTENT (credential harvest, money transfer, fake reward, etc.)
remains consistent. Intent detection catches patterns similarity search misses.
"""

import re
from typing import Dict, List


# === 7 Scam Intent Categories ===

SCAM_INTENTS = {
    "credential_harvest": {
        "label": "Thu thập thông tin đăng nhập",
        "risk_weight": 0.9,
        "patterns": [
            r'yêu\s*cầu\s*mật\s*khẩu', r'xác\s*minh\s*tài\s*khoản',
            r'đăng\s*nhập\s*để\s*nhận', r'nhập\s*thông\s*tin\s*để',
            r'verify\s*account', r'xác\s*thực\s*tài\s*khoản',
            r'cung\s*cấp\s*thông\s*tin\s*cá\s*nhân',
            r'điền\s*thông\s*tin\s*đăng\s*nhập',
            r'nhập\s*mật\s*khẩu', r'cho\s*biết\s*mật\s*khẩu',
            r'xác\s*minh\s*danh\s*tính', r'verify\s*identity',
            # Additional patterns
            r'nhập\s*otp', r'mã\s*xác\s*nhận', r'mã\s*xác\s*thực',
            r'nhập\s*số\s*điện\s*thoại', r'cung\s*cấp\s*email',
            r'đăng\s*nhập\s*tài\s*khoản', r'truy\s*cập\s*tài\s*khoản',
            r'confirm\s*your\s*account', r'account\s*verification',
            r'nhập\s*thông\s*tin\s*cá\s*nhân', r'thông\s*tin\s*ngân\s*hàng',
            r'số\s*cmnd', r'số\s*căn\s*cước', r'ngày\s*sinh\s*để\s*xác\s*minh',
            r'📱\s*nhập\s*mã', r'🔐\s*xác\s*minh',
        ],
    },
    "money_transfer": {
        "label": "Yêu cầu chuyển tiền",
        "risk_weight": 0.95,
        "patterns": [
            r'chuyển\s*khoản', r'nạp\s*tiền', r'phí\s*xử\s*lý',
            r'đặt\s*cọc', r'phí\s*vận\s*chuyển', r'thanh\s*toán\s*trước',
            r'nạp\s*thẻ', r'mua\s*thẻ', r'nạp\s*card',
            r'phí\s*dịch\s*vụ', r'lệ\s*phí', r'phí\s*đăng\s*ký',
            r'chuyển\s*tiền\s*qua', r'gửi\s*tiền\s*cho',
            r'transfer\s*money', r'send\s*money',
            # Additional patterns
            r'nạp\s*thẻ\s*cào', r'mua\s*thẻ\s*cào', r'thẻ\s*điện\s*thoại',
            r'momo\s*chuyển', r'zalopay', r'vnpay',
            r'số\s*tài\s*khoản\s*ngân\s*hàng',
            r'quét\s*mã\s*qr\s*để\s*thanh\s*toán', r'scan\s*qr\s*to\s*pay',
            r'phí\s*rút\s*tiền', r'phí\s*giải\s*ngân', r'phí\s*kích\s*hoạt',
            r'nộp\s*phí\s*trước', r'ứng\s*trước\s*tiền',
            r'💸\s*chuyển', r'💰\s*nạp', r'🏧\s*atm',
            r'banking\s*xác\s*nhận', r'internet\s*banking',
        ],
    },
    "urgency_pressure": {
        "label": "Tạo áp lực khẩn cấp",
        "risk_weight": 0.7,
        "patterns": [
            r'tài\s*khoản\s*bị\s*khóa', r'account\s*suspended',
            r'vi\s*phạm\s*chính\s*sách', r'bị\s*báo\s*cáo',
            r'xác\s*nhận\s*ngay', r'48\s*giờ', r'24\s*giờ',
            r'sẽ\s*bị\s*xóa', r'sẽ\s*bị\s*khóa', r'sẽ\s*bị\s*vô\s*hiệu',
            r'cảnh\s*cáo\s*cuối\s*cùng', r'final\s*warning',
            r'khóa\s*vĩnh\s*viễn', r'permanently\s*banned',
            # Additional patterns
            r'số\s*lượng\s*có\s*hạn', r'hết\s*slot', r'còn\s*\d+\s*suất',
            r'chỉ\s*còn\s*\d+\s*phút', r'hết\s*hạn\s*hôm\s*nay',
            r'hành\s*động\s*ngay', r'ngay\s*lập\s*tức',
            r'trước\s*\d+h', r'trong\s*vòng\s*\d+\s*phút',
            r'cảnh\s*báo\s*khẩn', r'thông\s*báo\s*khẩn\s*cấp',
            r'tài\s*khoản\s*sẽ\s*bị', r'bị\s*tạm\s*dừng',
            r'⚠️', r'🚨', r'❗', r'❌\s*tài\s*khoản',
            r'urgent', r'immediately', r'act\s*now',
        ],
    },
    "fake_reward": {
        "label": "Phần thưởng giả mạo",
        "risk_weight": 0.85,
        "patterns": [
            r'bạn\s*đã\s*trúng', r'được\s*chọn\s*ngẫu\s*nhiên',
            r'nhận\s*robux\s*miễn\s*phí', r'hack\s*robux',
            r'cheat\s*code', r'mod\s*menu\s*miễn\s*phí',
            r'giveaway', r'event\s*free', r'tặng\s*miễn\s*phí',
            r'quà\s*tặng\s*đặc\s*biệt', r'phần\s*thưởng\s*đặc\s*biệt',
            r'nhận\s*ngay\s*\d+k', r'nhận\s*ngay\s*\d+tr',
            r'free\s*fire\s*kim\s*cương', r'free\s*fire\s*diamond',
            r'nạp\s*\d+k\s*được\s*\d+k', r'nạp\s*\d+k\s*được\s*\d+tr',
            # Additional patterns
            r'trúng\s*thưởng', r'giải\s*thưởng\s*\d+',
            r'nhận\s*\d+\s*usdt', r'airdrop\s*free',
            r'spin\s*free', r'quay\s*thưởng\s*miễn\s*phí',
            r'lucky\s*draw', r'vòng\s*quay\s*may\s*mắn',
            r'gift\s*card\s*free', r'voucher\s*miễn\s*phí',
            r'phiếu\s*mua\s*hàng\s*miễn\s*phí',
            r'🎁\s*tặng', r'🎰\s*trúng', r'💎\s*nhận\s*ngay',
            r'nhận\s*tiền\s*miễn\s*phí', r'tiền\s*mặt\s*miễn\s*phí',
        ],
    },
    "grooming_isolation": {
        "label": "Cô lập trẻ khỏi người lớn",
        "risk_weight": 1.0,
        "patterns": [
            r'đừng\s*nói\s*với\s*bố\s*mẹ', r'bí\s*mật\s*nhé',
            r'chỉ\s*mình\s*mình\s*biết', r'người\s*lớn\s*không\s*hiểu',
            r'kết\s*bạn\s*riêng', r'nói\s*chuyện\s*riêng',
            r'đừng\s*kể\s*ai', r'giữ\s*bí\s*mật',
            r'không\s*cho\s*ai\s*biết', r'chỉ\s*2\s*đứa\s*mình',
            r'ba\s*mẹ\s*ko\s*biết\s*đâu', r'đừng\s*cho\s*phụ\s*huynh\s*biết',
            r'don\'?t\s*tell\s*your\s*parents', r'keep\s*this\s*secret',
            # Additional patterns
            r'nhắn\s*tin\s*riêng', r'zalo\s*riêng', r'telegram\s*riêng',
            r'chỉ\s*anh\s*em\s*mình\s*biết', r'mình\s*tao\s*mày\s*biết',
            r'đừng\s*share', r'đừng\s*đăng\s*lên',
            r'bố\s*mẹ\s*sẽ\s*không\s*hiểu', r'người\s*lớn\s*sẽ\s*ngăn',
            r'connect\s*zalo', r'thêm\s*zalo\s*riêng',
            r'private\s*message', r'dm\s*me',
        ],
    },
    "fake_job": {
        "label": "Việc làm giả mạo lương cao",
        "risk_weight": 0.8,
        "patterns": [
            r'việc\s*làm\s*online\s*lương\s*cao',
            r'làm\s*tại\s*nhà\s*\d+.*ngày', r'làm\s*tại\s*nhà\s*\d+.*tháng',
            r'thu\s*nhập\s*\d+.*ngày\s*không\s*cần\s*kinh\s*nghiệm',
            r'không\s*cần\s*kinh\s*nghiệm.*lương\s*cao',
            r'part\s*time\s*online\s*\d+k',
            r'tuyển\s*cộng\s*tác\s*viên\s*online',
            r'commission\s*\d+%\s*mỗi\s*đơn',
            r'kiếm\s*tiền\s*tại\s*nhà\s*\d+',
            r'việc\s*nhẹ\s*lương\s*cao', r'nhẹ\s*nhàng\s*lương\s*cao',
            r'chỉ\s*cần\s*điện\s*thoại\s*kiếm\s*tiền',
            r'nhân\s*viên\s*bán\s*hàng\s*online\s*không\s*cần',
            r'tuyển\s*gấp.*không\s*cần\s*bằng\s*cấp',
            r'affiliate.*\d+%', r'ctv\s*online',
            r'💼\s*tuyển\s*dụng', r'📢\s*tuyển\s*cộng\s*tác\s*viên',
        ],
    },
    "crypto_fraud": {
        "label": "Lừa đảo tiền điện tử / đầu tư giả",
        "risk_weight": 0.9,
        "patterns": [
            r'đầu\s*tư\s*bitcoin', r'đầu\s*tư\s*usdt',
            r'connect\s*ví\s*metamask', r'kết\s*nối\s*ví',
            r'airdrop\s*\d+\s*usdt', r'nhận\s*\d+\s*usdt\s*free',
            r'giveaway\s*\d+\s*usdt', r'\d+\s*usdt\s*miễn\s*phí',
            r'đầu\s*tư\s*sinh\s*lời\s*\d+%', r'lợi\s*nhuận\s*\d+%.*ngày',
            r'sàn\s*crypto', r'coin\s*listing',
            r'presale\s*token', r'ico\s*token',
            r'rug\s*pull', r'pump\s*and\s*dump',
            r'nạp\s*usdt\s*để\s*nhận', r'deposit\s*usdt',
            r'withdraw\s*usdt', r'rút\s*usdt',
            r'ví\s*crypto\s*của\s*bạn', r'seed\s*phrase',
            r'private\s*key', r'metamask\s*verify',
            r'💰\s*crypto', r'🪙\s*bitcoin', r'₿\s*btc',
            r'defi\s*farming', r'yield\s*farming\s*\d+%',
        ],
    },
}


def detect_scam_intent(text: str) -> Dict:
    """
    Detect scam intents in Vietnamese text.
    
    Returns dict with:
    - Per-intent scores (0.0-1.0)
    - max_intent_score: highest intent score
    - intent_count: number of intents with score > 0.3
    - primary_intent: the dominant intent
    - risk_weighted_score: intent scores weighted by risk severity
    """
    if not text:
        return {
            "intents": {},
            "max_intent_score": 0.0,
            "intent_count": 0,
            "primary_intent": "none",
            "risk_weighted_score": 0.0,
        }
    
    text_lower = text.lower()
    intent_scores = {}
    
    for intent_name, intent_config in SCAM_INTENTS.items():
        patterns = intent_config["patterns"]
        hits = sum(1 for p in patterns if re.search(p, text_lower))
        
        # Normalize: score based on pattern density
        max_possible = max(len(patterns) * 0.3, 1)
        score = min(hits / max_possible, 1.0)
        intent_scores[intent_name] = round(score, 3)
    
    # Find primary intent
    if intent_scores:
        primary_intent = max(intent_scores, key=intent_scores.get)
        max_score = intent_scores[primary_intent]
    else:
        primary_intent = "none"
        max_score = 0.0
    
    # Count active intents (score > 0.3)
    intent_count = sum(1 for v in intent_scores.values() if v > 0.3)
    
    # Risk-weighted score (grooming weighted higher than urgency)
    risk_weighted = sum(
        intent_scores[k] * SCAM_INTENTS[k]["risk_weight"]
        for k in intent_scores
    )
    risk_weighted = min(risk_weighted / 2.0, 1.0)  # Normalize
    
    return {
        "intents": intent_scores,
        "max_intent_score": max_score,
        "intent_count": intent_count,
        "primary_intent": primary_intent,
        "primary_intent_label": SCAM_INTENTS.get(primary_intent, {}).get("label", "Không xác định"),
        "risk_weighted_score": round(risk_weighted, 3),
    }


def get_intent_explanation(intent_name: str) -> str:
    """Get human-readable explanation of why an intent is dangerous."""
    explanations = {
        "credential_harvest": (
            "Kẻ lừa đảo đang cố thu thập mật khẩu hoặc thông tin đăng nhập của nạn nhân. "
            "Thường xuất hiện dưới dạng yêu cầu 'xác minh tài khoản', 'đăng nhập để nhận quà' "
            "hoặc 'nhập OTP để mở khóa'. Tuyệt đối không cung cấp thông tin cá nhân."
        ),
        "money_transfer": (
            "Kẻ lừa đảo đang yêu cầu chuyển tiền hoặc nạp thẻ, thường dưới vỏ bọc 'phí dịch vụ', "
            "'đặt cọc nhận thưởng', 'phí xác nhận', 'nạp tiền để rút tiền'. "
            "Đây là dấu hiệu lừa đảo phổ biến nhất — không bao giờ gửi tiền trước."
        ),
        "urgency_pressure": (
            "Nội dung tạo áp lực thời gian giả tạo để người xem không kịp suy nghĩ. "
            "Ví dụ: 'Chỉ còn 10 phút!', 'Tài khoản bị khóa ngay bây giờ!', 'Số lượng có hạn!'. "
            "Đây là kỹ thuật thao túng tâm lý điển hình của kẻ lừa đảo."
        ),
        "fake_reward": (
            "Nội dung hứa hẹn phần thưởng ảo như robux, kim cương, xu, quà tặng hoặc tiền thưởng miễn phí. "
            "Thông thường yêu cầu 'click link', 'xác minh tài khoản' hoặc 'chia sẻ để nhận'. "
            "Không có phần thưởng nào là miễn phí — đây là bẫy thu thập thông tin hoặc tiền."
        ),
        "grooming_isolation": (
            "CỰC KỲ NGUY HIỂM: Nội dung cố ý tách trẻ em khỏi sự giám sát của người lớn. "
            "Dấu hiệu: 'đừng nói với bố mẹ', 'chỉ mình mình biết thôi', 'nhắn tin riêng cho anh/chị'. "
            "Đây có thể là hành vi grooming — cần báo cáo ngay lập tức."
        ),
        "fake_job": (
            "Quảng cáo việc làm giả mạo với lời hứa 'lương cao không cần kinh nghiệm', 'làm tại nhà 5tr/ngày'. "
            "Thường yêu cầu nộp phí đào tạo, phí đăng ký hoặc mua sản phẩm trước khi làm việc. "
            "Việc làm hợp pháp KHÔNG BAO GIỜ yêu cầu bạn trả tiền trước."
        ),
        "crypto_fraud": (
            "Lừa đảo liên quan đến tiền điện tử: hứa 'lợi nhuận X% mỗi ngày', 'airdrop USDT miễn phí', "
            "'connect ví MetaMask để nhận thưởng'. Thực chất là chiếm đoạt ví hoặc tài sản crypto. "
            "Không bao giờ kết nối ví hoặc cung cấp seed phrase cho bất kỳ ai."
        ),
    }
    return explanations.get(intent_name, "Dấu hiệu bất thường được phát hiện trong nội dung")


def get_safe_explanation() -> str:
    """Return explanation string for safe content."""
    return (
        "Không phát hiện từ khoá hoặc mẫu hành vi lừa đảo trong nội dung. "
        "Giọng nói và hình ảnh không có dấu hiệu AI-generated bất thường. "
        "Nội dung được đánh giá là an toàn theo phân tích hiện tại."
    )


if __name__ == "__main__":
    # Test intent detection
    test_texts = [
        "ae minh ơi, admin roblox đang event free robux nè! click vào link này verify acc thôi, số lượng có hạn!",
        "CHÚ Ý! Tài khoản Facebook của bạn sẽ bị khóa trong 24h! Xác minh danh tính ngay!",
        "GIVEAWAY 1000 USDT! Connect ví MetaMask và xác nhận giao dịch!",
        "Chào các bạn, hôm nay mình chia sẻ cách học tiếng Anh hiệu quả cho các bé.",
        "đừng nói với bố mẹ nhé, chỉ 2 đứa mình biết thôi, kết bạn riêng với anh nè",
    ]
    
    for i, text in enumerate(test_texts):
        result = detect_scam_intent(text)
        print(f"\nTest {i+1}: {text[:60]}...")
        print(f"  Primary intent: {result['primary_intent_label']}")
        print(f"  Max score: {result['max_intent_score']:.3f}")
        print(f"  Active intents: {result['intent_count']}")
        print(f"  Risk-weighted: {result['risk_weighted_score']:.3f}")
        if result['intent_count'] > 0:
            print(f"  Explanation: {get_intent_explanation(result['primary_intent'])}")
