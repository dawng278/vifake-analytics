#!/usr/bin/env python3
"""
Feature Engineering for ViFake Analytics
Expands 2-feature input → 14-feature vector with linguistic, metadata, and cross-modal signals.

Key insight: XGBoost with only vision_score + nlp_score is "blind" to context.
A scammer can use innocent images + normal-sounding text with embedded CTA.
14 features give XGBoost enough signal to catch these patterns.
"""

import re
import numpy as np
from typing import Dict, List, Optional


# === Group 1: AI Model Scores (4 features) ===

def extract_model_scores(vision_result: Dict, nlp_result: Dict, rag_result: Optional[Dict] = None) -> Dict:
    """Extract raw model confidence scores."""
    return {
        "vision_risk": vision_result.get("combined_risk_score", 0.5),
        "nlp_toxic_prob": 1.0 - nlp_result.get("confidence", 0.5),
        "rag_similarity": rag_result.get("max_similarity", 0.0) if rag_result else 0.0,
        "nlp_confidence": nlp_result.get("confidence", 0.5),
    }


# === Group 2: Linguistic Red Flags (4 features) ===

def compute_leetspeak_score(text: str) -> float:
    """
    Detect leetspeak/teencode character substitution.
    Vietnamese scam often uses: 0→o, 4→a, 3→e, @→a, $→s, v.v.
    Score 0.0-1.0 based on density of substituted characters.
    """
    LEET_MAP = {
        '0': 'o', '4': 'a', '3': 'e', '@': 'a', '$': 's',
        '1': 'i', '7': 't', '5': 's', '8': 'b', '9': 'g',
        '™': '', '®': '', '©': '',
    }
    
    if not text:
        return 0.0
    
    alpha_chars = sum(1 for c in text if c.isalpha())
    if alpha_chars == 0:
        return 0.0
    
    leet_count = sum(1 for c in text if c in LEET_MAP)
    return min(leet_count / max(alpha_chars, 1) * 5, 1.0)


def detect_urgency_language(text: str) -> float:
    """
    Score 0.0-1.0 based on density of time-pressure language.
    Scammers create false urgency to bypass critical thinking.
    """
    URGENCY_PATTERNS = [
        r'ngay\s*bây\s*giờ', r'khẩn\s*cấp', r'hết\s*hạn', r'giới\s*hạn',
        r'chỉ\s*còn', r'nhanh\s*lên', r'cuối\s*cùng', r'\bfree\b', r'miễn\s*phí',
        r'click\s*ngay', r'đăng\s*ký\s*ngay', r'nhận\s*ngay',
        r'số\s*lượng\s*có\s*hạn', r'duy\s*nhất\s*hôm\s*nay',
        r'cơ\s*hội\s*cuối', r'đừng\s*bỏ\s*lỡ', r'kẻo\s*hết',
        r'CHÚ\s*Ý!', r'QUAN\s*TRỌNG!', r'KHẨN\s*CẤP!',
        r'GẤP!', r'LẬP\s*TỨC!',
    ]
    
    text_lower = text.lower()
    hits = sum(1 for p in URGENCY_PATTERNS if re.search(p, text_lower))
    return min(hits / 5, 1.0)


def detect_call_to_action(text: str) -> float:
    """
    Detect scam-specific calls to action.
    Legitimate content rarely asks for passwords, OTPs, or money transfers.
    """
    CTA_PATTERNS = [
        r'click\s*vào\s*link', r'nhắn\s*tin\s*cho', r'chuyển\s*khoản',
        r'cung\s*cấp\s*mật\s*khẩu', r'xác\s*nhận\s*tài\s*khoản',
        r'nhập\s*otp', r'tải\s*về', r'cài\s*đặt\s*app',
        r'gửi\s*thông\s*tin', r'điền\s*form', r'ib\s*admin',
        r'inbox\s*admin', r'liên\s*hệ\s*admin', r'nhắn\s*tin\s*riêng',
        r'kết\s*bạn\s*với', r'theo\s*dõi\s*trang',
    ]
    
    text_lower = text.lower()
    hits = sum(1 for p in CTA_PATTERNS if re.search(p, text_lower))
    return min(hits / 3, 1.0)


def count_suspicious_urls(text: str) -> float:
    """
    Count suspicious URLs: shortlinks, suspicious TLDs, IP-based URLs.
    Normalize to 0.0-1.0.
    """
    SUSPICIOUS_PATTERNS = [
        r'bit\.ly', r'bitly', r'shorturl\.at', r'tinyurl', r'cutt\.ly',
        r'\.click\b', r'\.xyz\b', r'\.top\b', r'\.tk\b', r'\.ml\b',
        r'\.ga\b', r'\.cf\b', r'\.gq\b',
        r'fb-verify', r'facebook.*verify', r'verify.*account',
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',  # IP-based URLs
    ]
    
    text_lower = text.lower()
    count = sum(1 for p in SUSPICIOUS_PATTERNS if re.search(p, text_lower))
    return min(count / 5, 1.0)


# === Group 3: Metadata Signals (4 features) ===

def compute_account_age_score(account_age_days: Optional[float]) -> float:
    """
    New accounts are more likely to be scam/bot accounts.
    Score 0.0 (old account) to 1.0 (brand new).
    """
    if account_age_days is None:
        return 0.5  # Unknown → neutral
    
    if account_age_days < 7:
        return 1.0
    elif account_age_days < 30:
        return 0.8
    elif account_age_days < 90:
        return 0.5
    elif account_age_days < 365:
        return 0.2
    else:
        return 0.0


def compute_follower_ratio_score(post_data: Dict) -> float:
    """
    Bot/spam accounts often follow many but have few followers.
    Ratio < 0.1 (follow 1000, follower 100) = suspicious.
    Returns 0.0 (normal) to 1.0 (suspicious).
    """
    followers = max(post_data.get("follower_count", 1), 1)
    following = max(post_data.get("following_count", 1), 1)
    ratio = followers / following
    
    if ratio < 0.05:
        return 1.0
    elif ratio < 0.1:
        return 0.8
    elif ratio < 0.3:
        return 0.5
    elif ratio < 0.5:
        return 0.2
    else:
        return 0.0


def compute_post_frequency_score(posts_per_day: Optional[float]) -> float:
    """
    Excessive posting frequency suggests automation/spam.
    """
    if posts_per_day is None:
        return 0.3
    
    if posts_per_day > 50:
        return 1.0
    elif posts_per_day > 20:
        return 0.7
    elif posts_per_day > 10:
        return 0.4
    elif posts_per_day > 5:
        return 0.2
    else:
        return 0.0


def compute_engagement_rate_score(post_data: Dict) -> float:
    """
    Abnormal engagement patterns (very high or very low) can indicate fake content.
    Returns 0.0 (normal) to 1.0 (suspicious).
    """
    likes = max(post_data.get("like_count", 0), 0)
    views = max(post_data.get("view_count", 1), 1)
    comments = max(post_data.get("comment_count", 0), 0)
    
    if views == 0:
        return 0.5
    
    engagement_rate = (likes + comments) / views
    
    # Very low engagement (bots pushing content) OR very high (bought engagement)
    if engagement_rate < 0.001:
        return 0.8
    elif engagement_rate > 0.5:
        return 0.7
    elif engagement_rate < 0.01:
        return 0.4
    else:
        return 0.0


# === Group 4: Cross-modal Consistency (2 features) ===

def compute_modal_conflict(vision_risk: float, nlp_toxic_prob: float) -> float:
    """
    KEY INSIGHT: Scam content often has innocent images but toxic text.
    High conflict between vision and NLP is a strong scam signal.
    """
    return abs(vision_risk - nlp_toxic_prob)


def compute_vision_nlp_product(vision_risk: float, nlp_toxic_prob: float) -> float:
    """
    Both vision AND NLP high = extremely dangerous content.
    Multiplicative interaction captures synergy.
    """
    return vision_risk * nlp_toxic_prob


# === Main Feature Builder ===

def build_feature_vector(
    post_data: Dict,
    vision_result: Dict,
    nlp_result: Dict,
    rag_result: Optional[Dict] = None,
) -> np.ndarray:
    """
    Build 14-feature vector from all available signals.
    
    Group 1: AI Model Scores (4)
    Group 2: Linguistic Red Flags (4)
    Group 3: Metadata Signals (4)
    Group 4: Cross-modal Consistency (2)
    
    Returns: np.ndarray of shape (1, 14)
    """
    text = post_data.get("content", "") or post_data.get("description", "") + " " + post_data.get("title", "")
    
    # Group 1: Model scores
    model_scores = extract_model_scores(vision_result, nlp_result, rag_result)
    f1 = model_scores["vision_risk"]
    f2 = model_scores["nlp_toxic_prob"]
    f3 = model_scores["rag_similarity"]
    f4 = model_scores["nlp_confidence"]
    
    # Group 2: Linguistic red flags
    f5 = compute_leetspeak_score(text)
    f6 = detect_urgency_language(text)
    f7 = detect_call_to_action(text)
    f8 = count_suspicious_urls(text)
    
    # Group 3: Metadata signals
    f9 = compute_account_age_score(post_data.get("account_age_days"))
    f10 = compute_follower_ratio_score(post_data)
    f11 = compute_post_frequency_score(post_data.get("posts_per_day"))
    f12 = compute_engagement_rate_score(post_data)
    
    # Group 4: Cross-modal consistency
    f13 = compute_modal_conflict(f1, f2)
    f14 = compute_vision_nlp_product(f1, f2)
    
    feature_vector = np.array([[
        f1, f2, f3, f4,
        f5, f6, f7, f8,
        f9, f10, f11, f12,
        f13, f14,
    ]], dtype=np.float32)
    
    return feature_vector


def get_feature_names() -> List[str]:
    """Return human-readable feature names for explainability."""
    return [
        # Group 1
        "vision_risk_score",
        "nlp_toxic_probability",
        "rag_max_similarity",
        "nlp_confidence",
        # Group 2
        "leetspeak_score",
        "urgency_language_score",
        "call_to_action_score",
        "suspicious_url_count",
        # Group 3
        "account_age_risk",
        "follower_ratio_risk",
        "post_frequency_risk",
        "engagement_rate_risk",
        # Group 4
        "modal_conflict_score",
        "vision_nlp_product",
    ]


def get_feature_descriptions() -> Dict[str, str]:
    """Return descriptions explaining WHY each feature matters."""
    return {
        "vision_risk_score": "CLIP-based image risk (0=safe, 1=dangerous)",
        "nlp_toxic_probability": "PhoBERT toxicity probability (inverse of confidence)",
        "rag_max_similarity": "Max similarity to known scam patterns in ChromaDB",
        "nlp_confidence": "How confident PhoBERT is (low = model is guessing)",
        "leetspeak_score": "Density of character substitution (0→o, @→a) — evasion tactic",
        "urgency_language_score": "Time-pressure words ('ngay bay gio', 'khan cap') — bypass critical thinking",
        "call_to_action_score": "Requests for passwords, OTPs, money transfers — never legitimate",
        "suspicious_url_count": "Shortlinks + suspicious TLDs (.xyz, .click) — phishing infrastructure",
        "account_age_risk": "New accounts more likely scam (brand new = 1.0, old = 0.0)",
        "follower_ratio_risk": "Follows many / few followers = bot pattern",
        "post_frequency_risk": "Excessive posting = automation/spam",
        "engagement_rate_risk": "Abnormal like/view ratio = fake engagement",
        "modal_conflict_score": "|vision_risk - nlp_toxic| — high conflict = scam with innocent image",
        "vision_nlp_product": "vision_risk × nlp_toxic — both high = extremely dangerous",
    }


if __name__ == "__main__":
    # Test feature engineering
    test_post = {
        "content": "ae minh ơi! admin roblox đang event free robux nè! click vào link bit.ly/robux-free verify acc ngay, số lượng có hạn!",
        "account_age_days": 3,
        "follower_count": 10,
        "following_count": 500,
        "posts_per_day": 45,
        "like_count": 2,
        "view_count": 1000,
        "comment_count": 0,
    }
    
    test_vision = {"combined_risk_score": 0.15}  # Innocent image
    test_nlp = {"confidence": 0.25, "prediction": "FAKE_SCAM"}  # Toxic text
    test_rag = {"max_similarity": 0.82}
    
    features = build_feature_vector(test_post, test_vision, test_nlp, test_rag)
    
    print("Feature vector shape:", features.shape)
    print("Features:")
    for name, value in zip(get_feature_names(), features[0]):
        print(f"  {name}: {value:.4f}")
    print(f"\n  → modal_conflict = {features[0][12]:.4f} (high = scam with innocent image detected!)")
