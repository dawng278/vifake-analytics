"""Unit tests for context-rate-query guardrail in Vietnamese scam detector."""

from backend_services.api_gateway.main import _vietnamese_scam_detector


def test_question_about_rate_is_not_forced_fake_scam():
    text = "Mọi người cho hỏi bảng giá 20k = 150 UC có đáng tin không hay là scam?"
    result = _vietnamese_scam_detector(text)

    assert any("CONTEXT_RATE_QUERY" in str(f) for f in result.get("flags", []))
    assert result.get("prediction") in ("SAFE", "SUSPICIOUS")


def test_question_with_pay_first_still_detected_as_scam():
    text = "Cho hỏi bảng giá 20k = 150 UC có thật không? Chuyển khoản trước để nhận ngay."
    result = _vietnamese_scam_detector(text)

    assert any("CONTEXT_RATE_QUERY" in str(f) for f in result.get("flags", []))
    assert result.get("prediction") == "FAKE_SCAM"
