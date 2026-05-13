"""Market exchange-rate anomaly detection for game currencies.

This module compares detected in-post rates against an internal reference table
and returns structured anomaly hits for scam scoring.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_NUM_TOKEN = r"(?:\d{1,3}(?:[\.,]\d{3})+|\d+(?:[\.,]\d+)?)"
_PRICE_RE = re.compile(rf"({_NUM_TOKEN})\s*(k|vnd|đ|đồng)\b", re.IGNORECASE)
logger = logging.getLogger(__name__)

_FALLBACK_REFERENCE: Dict[str, Any] = {
    "version": "embedded-fallback-2026-05-13",
    "unit": "currency_per_1000_vnd",
    "source": "embedded_fallback",
    "notes": "Used only when external market reference file is unavailable.",
    "currencies": {
        "robux": {
            "aliases": ["robux", "rbx", "rb", "robux card"],
            "safe_min": 5,
            "safe_max": 16,
            "suspicious_high": 24,
            "scam_high": 40,
        },
        "quan_huy": {
            "aliases": ["quân huy", "quan huy", "qh"],
            "safe_min": 4,
            "safe_max": 18,
            "suspicious_high": 28,
            "scam_high": 50,
        },
        "uc": {
            "aliases": ["uc"],
            "safe_min": 3,
            "safe_max": 18,
            "suspicious_high": 30,
            "scam_high": 50,
        },
        "kim_cuong": {
            "aliases": ["kim cương", "kim cuong", "diamond", "kc"],
            "safe_min": 6,
            "safe_max": 35,
            "suspicious_high": 60,
            "scam_high": 100,
        },
        "vbucks": {
            "aliases": ["vbucks", "v-bucks"],
            "safe_min": 4,
            "safe_max": 20,
            "suspicious_high": 35,
            "scam_high": 60,
        },
    },
}


@lru_cache(maxsize=1)
def _load_market_reference() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / "data" / "real_validation" / "game_currency_market_reference_2026.json",
        Path("/app/data/real_validation/game_currency_market_reference_2026.json"),
    ]

    for ref_path in candidates:
        try:
            if ref_path.exists():
                with ref_path.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as exc:
            logger.warning("Market rate reference read failed at %s: %s", ref_path, exc)

    logger.warning("Market rate reference file not found. Using embedded fallback table.")
    return _FALLBACK_REFERENCE


def _parse_number(raw: str) -> Optional[float]:
    s = raw.strip().replace(" ", "")
    if not s:
        return None

    if "." in s and "," in s:
        # Use right-most separator as decimal mark; the other as thousands separator.
        decimal_sep = "." if s.rfind(".") > s.rfind(",") else ","
        thousand_sep = "," if decimal_sep == "." else "."
        s = s.replace(thousand_sep, "")
        s = s.replace(decimal_sep, ".")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            s = "".join(parts)
    elif "," in s:
        parts = s.split(",")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            s = "".join(parts)
        else:
            s = ".".join(parts)

    try:
        return float(s)
    except ValueError:
        return None


def _build_alias_map(ref: Dict[str, Any]) -> Dict[str, str]:
    alias_to_key: Dict[str, str] = {}
    for key, cfg in ref.get("currencies", {}).items():
        for alias in cfg.get("aliases", []):
            alias_to_key[alias.lower().strip()] = key
    return alias_to_key


def _build_item_pattern(aliases: List[str]) -> re.Pattern[str]:
    escaped = sorted((re.escape(a) for a in aliases), key=len, reverse=True)
    union = "|".join(escaped)
    return re.compile(rf"({_NUM_TOKEN})\s*({union})\b", re.IGNORECASE)


def detect_market_price_anomalies(text: str, proximity_chars: int = 90) -> Dict[str, Any]:
    """Detect unrealistic game-currency exchange rates in free-form text.

    Returns:
        {
            "hits": [ ... ],
            "risk_score": float,
            "reference_version": str,
        }
    """
    lowered = (text or "").lower()
    ref = _load_market_reference()
    alias_map = _build_alias_map(ref)
    item_re = _build_item_pattern(list(alias_map.keys()))

    price_matches = list(_PRICE_RE.finditer(lowered))
    item_matches = list(item_re.finditer(lowered))

    hits: List[Dict[str, Any]] = []
    max_risk = 0.0

    if not price_matches or not item_matches:
        return {
            "hits": hits,
            "risk_score": 0.0,
            "reference_version": ref.get("version", "unknown"),
        }

    for p in price_matches:
        p_val = _parse_number(p.group(1))
        p_unit = p.group(2).lower()
        if p_val is None or p_val <= 0:
            continue
        price_vnd = p_val * 1000.0 if p_unit == "k" else p_val
        if price_vnd <= 0:
            continue

        for i in item_matches:
            if abs(p.start() - i.start()) > proximity_chars:
                continue

            i_val = _parse_number(i.group(1))
            alias = i.group(2).lower().strip()
            currency_key = alias_map.get(alias)
            if i_val is None or i_val <= 0 or not currency_key:
                continue

            cfg = ref["currencies"].get(currency_key, {})
            safe_max = float(cfg.get("safe_max", 0.0) or 0.0)
            suspicious_high = float(cfg.get("suspicious_high", 0.0) or 0.0)
            scam_high = float(cfg.get("scam_high", 0.0) or 0.0)

            ratio = i_val / (price_vnd / 1000.0)

            severity = None
            risk = 0.0
            if scam_high and ratio >= scam_high:
                severity = "scam"
                risk = 0.60
            elif suspicious_high and ratio >= suspicious_high:
                severity = "suspicious"
                risk = 0.24

            if not severity:
                continue

            over_safe = (ratio / safe_max) if safe_max else None
            hit = {
                "currency": currency_key,
                "alias": alias,
                "price_vnd": round(price_vnd, 2),
                "amount": round(i_val, 2),
                "ratio_per_1000_vnd": round(ratio, 2),
                "safe_max": safe_max,
                "suspicious_high": suspicious_high,
                "scam_high": scam_high,
                "ratio_over_safe_max": round(over_safe, 2) if over_safe else None,
                "severity": severity,
                "risk_score": risk,
            }
            hits.append(hit)
            if risk > max_risk:
                max_risk = risk

    return {
        "hits": hits,
        "risk_score": max_risk,
        "reference_version": ref.get("version", "unknown"),
    }
