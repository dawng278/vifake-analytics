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


# === 5 Scam Intent Categories ===

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
        "credential_harvest": "Kẻ lừa đảo đang cố lấy mật khẩu/thông tin đăng nhập của nạn nhân",
        "money_transfer": "Kẻ lừa đảo đang yêu cầu chuyển tiền dưới vỏ bọc phí dịch vụ/đặt cọc",
        "urgency_pressure": "Kẻ lừa đảo tạo áp lực thời gian để nạn nhân không kịp suy nghĩ",
        "fake_reward": "Kẻ lừa đảo dụ dỗ bằng phần thưởng ảo (robux, kim cương, quà tặng)",
        "grooming_isolation": "Kẻ lừa đảo cố tách trẻ khỏi sự bảo vệ của người lớn — CỰC KỲ NGUY HIỂM",
    }
    return explanations.get(intent_name, "Không xác định")


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
