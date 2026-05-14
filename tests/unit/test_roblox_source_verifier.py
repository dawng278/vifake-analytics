from ai_engine.nlp_worker.roblox_source_verifier import evaluate_roblox_safe_source


def test_detects_official_channels_without_risky_prompt():
    text = (
        "Nap Roblox VN qua App Store https://apps.apple.com/vn/app/roblox-vn/id6474715805 "
        "hoac Google Play com.roblox.client.vnggames de an toan."
    )
    result = evaluate_roblox_safe_source(text)
    assert result["trusted_hit_count"] >= 1
    assert result["is_safe_reference"] is True
    assert result["has_risky_prompt"] is False
    assert result["safety_discount"] > 0


def test_official_mention_with_risky_prompt_not_marked_safe():
    text = (
        "Shop nao cung duoc, ib minh de nap Roblox VN, chuyen khoan truoc va gui OTP "
        "de kich hoat nhanh."
    )
    result = evaluate_roblox_safe_source(text)
    assert result["has_risky_prompt"] is True
    assert result["is_safe_reference"] is False
