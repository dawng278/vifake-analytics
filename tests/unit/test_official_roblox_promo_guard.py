"""Unit tests for official Roblox-VNG promotion guardrail."""

from backend_services.api_gateway.main import _run_nlp_analysis, _vietnamese_scam_detector


def test_official_roblox_vng_promo_marked_safe_when_no_hard_scam_signal():
    text = (
        "THONG BAO GIA HAN HOT DEAL! Uu dai nap Robux qua cong nap Roblox - VNG, "
        "thanh toan bang kenh the cao chinh thuc qua Webpay. "
        "Chuong trinh ap dung giao dich thanh cong qua Webpay, uu dai co the ket thuc som neu het ngan sach. "
        "Nhanh tay nhan uu dai, tag ban be de cung nhan."
    )
    result = _vietnamese_scam_detector(text)

    assert result.get("prediction") == "SAFE"
    assert any("OFFICIAL_ROBLOX_PROMO_CONTEXT" in str(f) for f in result.get("flags", []))
    assert any("SAFE_ROBLOX_SOURCE" in str(f) for f in result.get("flags", []))


def test_official_roblox_vng_promo_intent_is_synced_to_official_notice():
    text = (
        "Thong bao uu dai nap Robux qua cong nap Roblox - VNG, thanh toan qua Webpay "
        "va kenh the cao chinh thuc. Chuong trinh co the ket thuc som neu het ngan sach."
    )
    result = _run_nlp_analysis(text)

    assert result.get("prediction") == "SAFE"
    assert result.get("intent_label") == "Thông báo ưu đãi chính thức Roblox-VNG"


def test_official_promo_with_payfirst_or_otp_is_still_scam():
    text = (
        "Nap Robux qua cong nap Roblox - VNG va Webpay. "
        "De kich hoat uu dai, vui long chuyen khoan truoc va gui OTP cho admin."
    )
    result = _vietnamese_scam_detector(text)

    assert result.get("prediction") == "FAKE_SCAM"
    assert any("SAFE_SOURCE_CONTRADICTION" in str(f) or "pay_first_scheme" in str(f) for f in result.get("flags", []))
