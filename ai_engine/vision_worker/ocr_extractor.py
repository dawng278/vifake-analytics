"""
OCR Extractor for ViFake Analytics.

Uses EasyOCR (CPU mode) to extract text from thumbnail/screenshot images.
Supports Vietnamese and English (most common in VN social media scams).

Design constraints:
- CPU only — VRAM is reserved for CLIP (RTX 2050 4GB)
- Confidence threshold: 0.60
- Languages: ['vi', 'en']
- Returns plain string (joined detected text blocks)
"""
import logging
import os
from typing import Optional
import tempfile

logger = logging.getLogger(__name__)

try:
    import easyocr
    _EASYOCR_AVAILABLE = True
except ImportError:
    logger.warning("easyocr not installed. OCR extraction will be skipped.")
    _EASYOCR_AVAILABLE = False

# Module-level reader singleton (lazy init, CPU-only)
_reader: Optional[object] = None


def _get_reader():
    """Lazy-init EasyOCR reader — CPU only, vi + en."""
    global _reader
    if _reader is None and _EASYOCR_AVAILABLE:
        logger.info("🔤 Initializing EasyOCR (CPU, vi+en) — first-time load may take ~10s...")
        _reader = easyocr.Reader(["vi", "en"], gpu=False)
        logger.info("✅ EasyOCR ready")
    return _reader


def extract_text_from_image(
    image_path: str,
    conf_threshold: float = 0.60,
    max_chars: int = 1000,
) -> str:
    """Extract text from an image file using EasyOCR.

    Args:
        image_path: Absolute path to the image (jpg/png/webp).
        conf_threshold: Minimum EasyOCR confidence to accept a text block.
        max_chars: Truncate result to this many characters.

    Returns:
        Extracted text joined by spaces, or empty string on failure.
    """
    if not _EASYOCR_AVAILABLE:
        return ""
    if not os.path.isfile(image_path):
        logger.warning(f"OCR: file not found: {image_path}")
        return ""

    try:
        reader = _get_reader()
        if reader is None:
            return ""

        def _dedupe_text(text: str) -> str:
            seen = set()
            out = []
            for part in (text or "").split():
                key = part.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(part)
            return " ".join(out).strip()

        def _extract_pass(path: str, threshold: float) -> str:
            results = reader.readtext(path, detail=1)
            accepted = [text for (_bbox, text, conf) in results if conf >= threshold]
            if not accepted and threshold > 0.09:
                accepted = [text for (_bbox, text, conf) in results if conf >= 0.05 and len(str(text).strip()) >= 2]
            return " ".join(accepted).strip()

        extracted = _extract_pass(image_path, conf_threshold)

        # Fallback passes for stylized social banners: crop text-heavy zones,
        # boost contrast, sharpen, and upscale. This helps colorful Robux/shop images.
        if len(extracted) < 80:
            try:
                from PIL import Image, ImageOps, ImageEnhance, ImageFilter
                with Image.open(image_path).convert("RGB") as im:
                    w, h = im.size
                    if w < 280 or h < 280:
                        im = im.resize((max(280, w * 4), max(280, h * 4)), Image.Resampling.LANCZOS)
                        w, h = im.size
                    boxes = [
                        (0, 0, w, h),
                        (int(w * 0.18), int(h * 0.25), int(w * 0.84), int(h * 0.78)),
                        (int(w * 0.18), int(h * 0.40), int(w * 0.82), int(h * 0.74)),
                        (int(w * 0.10), int(h * 0.65), int(w * 0.90), int(h * 0.92)),
                    ]
                    variants = []
                    for box in boxes:
                        crop = im.crop(box)
                        for scale in (2, 3):
                            resized = crop.resize(
                                (max(1, crop.width * scale), max(1, crop.height * scale)),
                                Image.Resampling.LANCZOS,
                            )
                            gray = ImageOps.grayscale(resized)
                            boosted = ImageOps.autocontrast(gray)
                            boosted = ImageEnhance.Contrast(boosted).enhance(1.9)
                            variants.append(boosted)
                            sharp = boosted.filter(ImageFilter.SHARPEN)
                            variants.append(sharp)

                    texts = [extracted]
                    for variant in variants:
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                            tmp_path = tmp.name
                        try:
                            variant.save(tmp_path, "PNG")
                            alt = _extract_pass(tmp_path, max(0.08, conf_threshold - 0.32))
                            if alt:
                                texts.append(alt)
                        finally:
                            if os.path.isfile(tmp_path):
                                os.unlink(tmp_path)
                    extracted = _dedupe_text(" ".join(texts))
            except Exception as _e:
                logger.debug(f"OCR fallback preprocessing skipped: {_e}")

        if extracted:
            logger.info(f"🔤 OCR extracted {len(extracted)} chars from {os.path.basename(image_path)}")
        return extracted[:max_chars]

    except Exception as e:
        logger.warning(f"OCR failed for {image_path}: {e}")
        return ""


def extract_text_from_url_image(
    image_url: str,
    conf_threshold: float = 0.60,
    max_chars: int = 1000,
    timeout: int = 10,
) -> str:
    """Download image from URL and run OCR.

    Args:
        image_url: HTTP/HTTPS URL of the image.
        conf_threshold: Minimum confidence threshold.
        max_chars: Truncate result.
        timeout: HTTP download timeout in seconds.

    Returns:
        Extracted text or empty string.
    """
    if not _EASYOCR_AVAILABLE:
        return ""

    import tempfile
    import requests

    try:
        response = requests.get(image_url, timeout=timeout, stream=True)
        response.raise_for_status()

        # Write to a temp file and run OCR
        suffix = ".jpg"
        content_type = response.headers.get("Content-Type", "")
        if "png" in content_type:
            suffix = ".png"
        elif "webp" in content_type:
            suffix = ".webp"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
            tmp_path = tmp.name

        result = extract_text_from_image(tmp_path, conf_threshold, max_chars)
        os.unlink(tmp_path)
        return result

    except Exception as e:
        logger.warning(f"OCR URL fetch failed ({image_url[:80]}): {e}")
        return ""
