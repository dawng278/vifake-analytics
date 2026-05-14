"""Unit tests for reference-data market rate anomaly detection."""

from ai_engine.nlp_worker.market_rate_analyzer import detect_market_price_anomalies


def test_realistic_robux_rate_not_flagged():
    text = "Bảng giá nạp robux: 50k = 140 robux, giao dịch qua cổng chính hãng"
    result = detect_market_price_anomalies(text)
    assert result["risk_score"] == 0.0
    assert result["hits"] == []


def test_overshoot_robux_rate_flagged_as_suspicious():
    text = "Rate robux hôm nay 50k = 300 robux"
    result = detect_market_price_anomalies(text)
    assert result["risk_score"] >= 0.24
    assert any(h["currency"] == "robux" and h["severity"] in ("suspicious", "scam") for h in result["hits"])


def test_extreme_robux_rate_flagged_as_scam():
    text = "BẢNG GIÁ ROBUX HÈ 2026: 50k = 7.000 robux, ib ngay"
    result = detect_market_price_anomalies(text)
    assert result["risk_score"] >= 0.60
    assert any(h["currency"] == "robux" and h["severity"] == "scam" for h in result["hits"])


def test_mid_high_quan_huy_rate_flagged_as_suspicious():
    text = "Rate quân huy hôm nay 10k = 350 quân huy"
    result = detect_market_price_anomalies(text)
    assert result["risk_score"] >= 0.24
    assert any(h["currency"] == "quan_huy" and h["severity"] in ("suspicious", "scam") for h in result["hits"])


def test_official_like_uc_rate_not_flagged():
    text = "Nạp UC chính hãng: Pack 60 UC giá 25k trên App Store"
    result = detect_market_price_anomalies(text)
    assert result["risk_score"] == 0.0
    assert result["hits"] == []


def test_official_like_quan_huy_rate_not_flagged():
    text = "Nạp quân huy: gói 111 quân huy giá 79k"
    result = detect_market_price_anomalies(text)
    assert result["risk_score"] == 0.0
    assert result["hits"] == []


def test_uc_rate_above_band_flagged():
    text = "Deal UC hôm nay: 20k nhận 150 UC"
    result = detect_market_price_anomalies(text)
    assert result["risk_score"] >= 0.24
    assert any(h["currency"] == "uc" and h["severity"] in ("suspicious", "scam") for h in result["hits"])


def test_quan_huy_rate_above_band_flagged():
    text = "Rate quân huy sốc: 20k = 70 quân huy"
    result = detect_market_price_anomalies(text)
    assert result["risk_score"] >= 0.24
    assert any(h["currency"] == "quan_huy" and h["severity"] in ("suspicious", "scam") for h in result["hits"])


def test_thousands_separator_is_parsed_correctly():
    text = "Deal sốc: chỉ 100k nhận 1.000.000 robux"
    result = detect_market_price_anomalies(text)
    assert any(h["currency"] == "robux" and h["severity"] == "scam" for h in result["hits"])
