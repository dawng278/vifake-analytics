"""Unit tests for rule-based NLP scam detector (phobert_inference mock mode)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from ai_engine.nlp_worker.phobert_inference import PhoBERTInference


@pytest.fixture(scope="module")
def nlp():
    return PhoBERTInference()


@pytest.mark.unit
class TestRuleBasedNLP:
    """Tests for _rule_based_predict via .predict() in mock mode."""

    SCAM_TEXTS = [
        "Unlock robux free miễn phí nhanh tay!",
        "free robux generator 2024 no human verification",
        "nạp thẻ trước để nhận 500k ngay hôm nay",
        "connect wallet MetaMask nhận airdrop ngay",
        "free vbucks generator fortnite 2024",
        "coin generator unlimited free gems hack",
    ]
    SAFE_TEXTS = [
        "Hôm nay học bài toán cùng thầy giáo",
        "Chia sẻ công thức nấu phở ngon",
        "Bài tập về nhà môn lịch sử lớp 8",
        "Bộ Giáo dục thông báo lịch nghỉ hè 2024",
    ]

    def _run(self, nlp, text):
        """Call predict (falls back to rule-based in mock mode)."""
        return nlp.predict(text)

    @pytest.mark.parametrize("text", SCAM_TEXTS)
    def test_scam_text_detected(self, nlp, text):
        result = self._run(nlp, text)
        assert result["prediction"] in ("FAKE_SCAM", "SUSPICIOUS"), (
            f"Expected FAKE_SCAM/SUSPICIOUS for: {text!r}, got {result['prediction']}"
        )

    @pytest.mark.parametrize("text", SAFE_TEXTS)
    def test_safe_text_not_flagged(self, nlp, text):
        result = self._run(nlp, text)
        assert result["prediction"] == "SAFE", (
            f"Expected SAFE for: {text!r}, got {result['prediction']}"
        )

    def test_probabilities_sum_to_one(self, nlp):
        result = self._run(nlp, "miễn phí robux hôm nay")
        probs = result.get("probabilities", {})
        total = sum(probs.values())
        assert abs(total - 1.0) < 0.05, f"Probs don't sum to 1: {probs}"

    def test_high_risk_teencode_escalates(self, nlp):
        """'mk' = mật khẩu (password) — a high-risk teen-code term."""
        result = self._run(nlp, "cho mk tài khoản roblox đi")
        # After teencode normalization: 'mk' → 'mật khẩu'
        # Should be at least SUSPICIOUS (password request)
        assert result["prediction"] in ("FAKE_SCAM", "SUSPICIOUS")

    def test_result_has_required_keys(self, nlp):
        result = self._run(nlp, "xin chào bạn")
        for key in ("prediction", "confidence", "probabilities", "risk_level", "is_safe"):
            assert key in result, f"Missing key: {key}"
