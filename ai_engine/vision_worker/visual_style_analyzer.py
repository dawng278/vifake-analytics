"""
Visual Style Analyzer for ViFake Analytics.

Uses Pillow + numpy to detect visual patterns common in scam content:
- High color excitement (oversaturated reds/yellows used in clickbait)
- Red/yellow dominance (warning colors exploited by scammers)
- High contrast ratio (shock thumbnails)
- Text-heavy thumbnails (many bright white/yellow text overlays)

No ML model — pure image statistics, CPU only, <10ms per image.
"""
import logging
from typing import Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    logger.warning("Pillow not installed. Visual style analysis will return defaults.")
    _PIL_AVAILABLE = False


def analyze_visual_style(image_path: str) -> Dict[str, float]:
    """Analyze visual style features of an image for scam detection.

    Returns a dict with:
      color_excitement_score  — 0-1, high = oversaturated (scam bait)
      red_yellow_ratio        — 0-1, fraction of pixels that are vivid red/yellow
      contrast_score          — 0-1, stddev of luminance (high = shocking thumbnail)
      brightness_score        — 0-1, mean brightness (very bright = clickbait)
      combined_visual_risk    — 0-1, weighted combination
    """
    defaults = {
        "color_excitement_score": 0.0,
        "red_yellow_ratio": 0.0,
        "contrast_score": 0.0,
        "brightness_score": 0.0,
        "combined_visual_risk": 0.0,
    }

    if not _PIL_AVAILABLE:
        return defaults

    import os
    if not os.path.isfile(image_path):
        logger.warning(f"visual_style: file not found: {image_path}")
        return defaults

    try:
        img = Image.open(image_path).convert("RGB")
        # Resize to 128×128 for fast computation
        img = img.resize((128, 128), Image.Resampling.LANCZOS)
        arr = np.asarray(img, dtype=np.float32)  # shape (128,128,3), range 0-255

        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

        # ── Color excitement (saturation proxy) ─────────────────────────────
        max_c = arr.max(axis=2)
        min_c = arr.min(axis=2)
        saturation = np.where(max_c > 0, (max_c - min_c) / (max_c + 1e-6), 0.0)
        color_excitement = float(saturation.mean())  # 0-1

        # ── Red/Yellow ratio ─────────────────────────────────────────────────
        # Vivid red: R > 180 AND G < 100 AND B < 100
        vivid_red   = ((r > 180) & (g < 100) & (b < 100)).sum()
        # Vivid yellow: R > 200 AND G > 180 AND B < 80
        vivid_yellow = ((r > 200) & (g > 180) & (b < 80)).sum()
        total_pixels = arr.shape[0] * arr.shape[1]
        red_yellow_ratio = float((vivid_red + vivid_yellow) / total_pixels)

        # ── Contrast score (luminance stddev) ───────────────────────────────
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        contrast = float(lum.std() / 128.0)  # normalize 0-2 → 0-1

        # ── Brightness score ─────────────────────────────────────────────────
        brightness = float(lum.mean() / 255.0)

        # ── Combined visual risk ─────────────────────────────────────────────
        # Scam thumbnails tend to be: high saturation, lots of red/yellow, high contrast
        combined = min(1.0, (
            0.35 * min(1.0, color_excitement * 1.5) +
            0.35 * min(1.0, red_yellow_ratio * 10.0) +
            0.20 * min(1.0, contrast * 1.2) +
            0.10 * min(1.0, brightness * 1.2)
        ))

        result = {
            "color_excitement_score": round(color_excitement, 3),
            "red_yellow_ratio":       round(red_yellow_ratio, 3),
            "contrast_score":         round(contrast, 3),
            "brightness_score":       round(brightness, 3),
            "combined_visual_risk":   round(combined, 3),
        }
        logger.debug(f"Visual style: {result}")
        return result

    except Exception as e:
        logger.warning(f"Visual style analysis failed for {image_path}: {e}")
        return defaults


def analyze_visual_style_from_url(
    image_url: str,
    timeout: int = 8,
) -> Dict[str, float]:
    """Download image from URL and analyze visual style."""
    defaults = {
        "color_excitement_score": 0.0,
        "red_yellow_ratio": 0.0,
        "contrast_score": 0.0,
        "brightness_score": 0.0,
        "combined_visual_risk": 0.0,
    }
    if not _PIL_AVAILABLE:
        return defaults

    import tempfile, os, requests

    try:
        resp = requests.get(image_url, timeout=timeout, stream=True)
        resp.raise_for_status()
        suffix = ".jpg"
        ct = resp.headers.get("Content-Type", "")
        if "png" in ct:
            suffix = ".png"
        elif "webp" in ct:
            suffix = ".webp"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in resp.iter_content(8192):
                tmp.write(chunk)
            tmp_path = tmp.name
        result = analyze_visual_style(tmp_path)
        os.unlink(tmp_path)
        return result
    except Exception as e:
        logger.warning(f"Visual style URL fetch failed ({image_url[:80]}): {e}")
        return defaults
