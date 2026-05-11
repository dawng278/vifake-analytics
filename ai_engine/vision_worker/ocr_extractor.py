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

        results = reader.readtext(image_path, detail=1)
        # Each result: (bbox, text, confidence)
        accepted = [text for (_bbox, text, conf) in results if conf >= conf_threshold]
        extracted = " ".join(accepted).strip()
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
