"""Unit tests for teencode normalizer."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from ai_engine.nlp_worker.teencode_normalizer import normalize, contains_high_risk_teencode


@pytest.mark.unit
class TestTeencodeNormalize:
    def test_mk_replaced_with_mat_khau(self):
        result = normalize("cho mk đi")
        assert "mật khẩu" in result

    def test_tk_replaced_with_tai_khoan(self):
        result = normalize("mất tk rồi")
        assert "tài khoản" in result

    def test_acc_replaced_with_tai_khoan(self):
        result = normalize("bán acc game")
        assert "tài khoản" in result

    def test_free_replaced(self):
        result = normalize("free robux")
        assert "miễn phí" in result

    def test_no_change_on_clean_text(self):
        text = "hôm nay trời đẹp quá"
        assert normalize(text) == text

    def test_empty_string(self):
        assert normalize("") == ""

    def test_none_returns_none(self):
        assert normalize(None) is None

    def test_case_insensitive(self):
        result = normalize("MK của tôi bị lộ")
        assert "mật khẩu" in result.lower()


@pytest.mark.unit
class TestHighRiskTeencode:
    def test_mk_is_high_risk(self):
        assert contains_high_risk_teencode("cho mình mk đi")

    def test_pass_is_high_risk(self):
        assert contains_high_risk_teencode("share pass game")

    def test_mất_tk_is_high_risk(self):
        assert contains_high_risk_teencode("mất tk rồi")

    def test_clean_text_is_not_high_risk(self):
        assert not contains_high_risk_teencode("chơi game cùng bạn")

    def test_school_text_is_not_high_risk(self):
        assert not contains_high_risk_teencode("bài tập hôm nay khó quá")
