"""Trusted-source verifier for Roblox recharge safety signals.

The goal is to detect whether a text references official Roblox/VNG channels
and provide structured confirmation hints for UI + rule engine.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_FALLBACK_REFERENCE: Dict[str, Any] = {
    "version": "embedded-safe-source-2026-05-14",
    "trusted_channels": [
        {
            "id": "roblox_vng_app_store_vn",
            "name": "Roblox VN (App Store Vietnam)",
            "url": "https://apps.apple.com/vn/app/roblox-vn/id6474715805",
            "indicators": [
                "apps.apple.com/vn/app/roblox-vn/id6474715805",
                "roblox vn",
                "vnggames co., ltd",
            ],
        },
        {
            "id": "roblox_vng_google_play_vn",
            "name": "Roblox VNG (Google Play Vietnam)",
            "url": "https://play.google.com/store/apps/details?id=com.roblox.client.vnggames",
            "indicators": [
                "play.google.com/store/apps/details?id=com.roblox.client.vnggames",
                "com.roblox.client.vnggames",
                "vnggames co., ltd",
            ],
        },
        {
            "id": "vng_webshop_roblox_vn",
            "name": "VNGGames Shop - Roblox VN",
            "url": "https://shop.vnggames.com/vn/game/roblox",
            "indicators": [
                "shop.vnggames.com/vn/game/roblox",
                "shop.vnggames.com",
                "robloxsupport@vnggames.com",
                "hotroroblox.vnggames.com",
            ],
        },
        {
            "id": "roblox_help_vng_faq",
            "name": "Roblox Help - FAQ Roblox VNG Official Launch",
            "url": "https://en.help.roblox.com/hc/en-us/articles/27349697955220-FAQ-Roblox-VNG-Official-Launch",
            "indicators": ["en.help.roblox.com", "faq roblox vng official launch", "roblox help"],
        },
    ],
    "verification_methods": [
        "Chi tin domain chinh thong: apps.apple.com, play.google.com, shop.vnggames.com, en.help.roblox.com",
        "Doi chieu package/app id: com.roblox.client.vnggames va id6474715805",
        "Khong cung cap OTP, mat khau, cookie de nap Robux",
    ],
    "hard_block_signals": [
        "chuyen khoan truoc",
        "otp",
        "mat khau",
        "verify acc",
        "ib de nhan",
    ],
}


@lru_cache(maxsize=1)
def _load_reference() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / "data" / "real_validation" / "roblox_safe_recharge_reference_2026.json",
        Path("/app/data/real_validation/roblox_safe_recharge_reference_2026.json"),
    ]

    for ref_path in candidates:
        try:
            if ref_path.exists():
                with ref_path.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as exc:
            logger.warning("Roblox safe-source reference read failed at %s: %s", ref_path, exc)

    logger.warning("Roblox safe-source reference file not found. Using embedded fallback.")
    return _FALLBACK_REFERENCE


def _norm(text: str) -> str:
    t = (text or "").strip().lower()
    t = t.replace("\n", " ")
    return t


def _looks_like_risky_prompt(t: str, extra_signals: List[str]) -> bool:
    explicit_safety_patterns = [
        r"kh[oô]ng\s+(?:đưa|gửi|nhập|cung\s*cấp).{0,20}(?:otp|m[aậ]t\s*kh[aẩ]u|password|pass)",
        r"đừng\s+(?:đưa|gửi|nhập|cung\s*cấp).{0,20}(?:otp|m[aậ]t\s*kh[aẩ]u|password|pass)",
    ]
    has_explicit_safety_credential_warning = any(re.search(p, t) for p in explicit_safety_patterns)

    risky_patterns = [
        r"chuy\s*e?n\s*kho[aả]n\s*tr[uư][oớ]c",
        r"n[aạ]p\s*tr[uư][oớ]c",
        r"(?:g[uử]i|đưa|nh[aậ]p|xin|l[aấ]y).{0,12}(?:m[aã]\s*)?otp",
        r"(?:g[uử]i|đưa|nh[aậ]p|cho).{0,20}(?:m[aậ]t\s*kh[aẩ]u|password|pass)",
        r"verify\s*acc",
        r"nh[aậ]p\s*(user|pass|password)",
        r"\bib\b",
        r"inbox",
        r"r[uú]t\s*g[oọ]n",
        r"bit\.ly",
        r"tinyurl",
        r"c[oọ]c\s*tr[uư][oớ]c",
    ]
    for p in risky_patterns:
        if re.search(p, t):
            if has_explicit_safety_credential_warning and (
                "otp" in p or "m[aậ]t\\s*kh[aẩ]u" in p or "pass" in p
            ):
                continue
            return True
    for s in extra_signals:
        ns = _norm(s)
        if not ns or len(ns) < 5:
            continue
        if has_explicit_safety_credential_warning and ("otp" in ns or "mật khẩu" in ns):
            continue
        if ns in t:
            return True
    return False


def evaluate_roblox_safe_source(text: str) -> Dict[str, Any]:
    """Evaluate trusted Roblox recharge channel mentions in free-form text."""
    t = _norm(text)
    ref = _load_reference()

    matched_channels: List[Dict[str, Any]] = []
    for channel in ref.get("trusted_channels", []):
        indicators = channel.get("indicators", [])
        matched = [ind for ind in indicators if _norm(ind) and _norm(ind) in t]
        if matched:
            matched_channels.append(
                {
                    "id": channel.get("id", "unknown"),
                    "name": channel.get("name", "unknown"),
                    "url": channel.get("url", ""),
                    "matched_indicators": matched[:4],
                }
            )

    hard_block_signals = ref.get("hard_block_signals", [])
    has_risky_prompt = _looks_like_risky_prompt(t, hard_block_signals)

    trusted_hit_count = len(matched_channels)
    is_safe_reference = trusted_hit_count > 0 and not has_risky_prompt

    discount = 0.0
    if is_safe_reference:
        discount = min(0.10 + (trusted_hit_count * 0.05), 0.28)

    return {
        "trusted_hit_count": trusted_hit_count,
        "matched_channels": matched_channels,
        "is_safe_reference": is_safe_reference,
        "has_risky_prompt": has_risky_prompt,
        "safety_discount": round(discount, 3),
        "verification_methods": ref.get("verification_methods", [])[:5],
        "reference_version": ref.get("version", "unknown"),
    }
