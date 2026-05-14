"""
ViFake Analytics - Frame Analyzer for AI-Generated Detection

Uses CLIP model + QR detection + OCR to detect AI-generated content,
scam visuals, and on-screen text in video frames.
"""

import asyncio
import logging
from typing import List, Dict
import sys
from pathlib import Path

# Add project root to path for AI engine imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

try:
    import easyocr
    _ocr_reader = None  # Lazy-loaded on first use
    EASYOCR_AVAILABLE = True
except Exception as _e:
    logging.getLogger(__name__).warning(f"⚠️ EasyOCR not available ({_e}). OCR analysis will be skipped.")
    easyocr = None
    _ocr_reader = None
    EASYOCR_AVAILABLE = False

try:
    from ai_engine.vision_worker.clip_inference import CLIPVisionWorker, VisionConfig
    CLIP_AVAILABLE = True
except ImportError as _e:
    logging.getLogger(__name__).warning(f"⚠️  CLIP not available ({_e}). Frame analysis will be skipped.")
    CLIP_AVAILABLE = False
    CLIPVisionWorker = None
    VisionConfig = None

# Suspicious URL TLDs/domains for QR content check
_SUSPICIOUS_URL_PATTERNS = [
    "bit.ly", "tinyurl", "cutt.ly", "shorturl", "short.link",
    ".xyz", ".top", ".tk", ".click", ".ml", ".ga", ".cf",
    "fb-verify", "facebook-verify", "account-verify", "claim-prize",
    "free-robux", "gift-card", "robux-free", "usdt-free",
]

logger = logging.getLogger(__name__)


def _get_ocr_reader():
    """Lazy-load EasyOCR reader (downloads model on first call)."""
    global _ocr_reader
    if _ocr_reader is None and EASYOCR_AVAILABLE:
        try:
            _ocr_reader = easyocr.Reader(['vi', 'en'], gpu=False, verbose=False)
            logger.info("✅ EasyOCR reader loaded (vi+en)")
        except Exception as e:
            logger.warning(f"⚠️ EasyOCR load failed: {e}")
    return _ocr_reader


def _is_suspicious_url(url: str) -> bool:
    """Check if a URL extracted from QR code is suspicious."""
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in _SUSPICIOUS_URL_PATTERNS)


class FrameAnalyzer:
    """Analyze video frames to detect AI-generated content, QR scams, and on-screen text."""

    def __init__(self):
        self.worker = None
        if not CLIP_AVAILABLE:
            logger.warning("⚠️ CLIP unavailable — frame analysis disabled")
            return
        self.config = VisionConfig(
            device="cpu",
            dtype=None,
            batch_size=1
        )
        self._load_model()

    def _load_model(self):
        try:
            self.worker = CLIPVisionWorker(self.config)
            logger.info("✅ CLIP model loaded for AI detection")
        except Exception as e:
            logger.error(f"❌ Failed to load CLIP model: {e}")
            self.worker = None

    # ─── Public entry point ───────────────────────────────────────────────────

    async def analyze_frames(self, frame_paths: List[str]) -> Dict:
        """
        Analyze video frames. Returns:
        - AI-generated detection (CLIP)
        - QR code detection + URL risk
        - OCR on-screen text + intent scores
        """
        if not frame_paths:
            return {"is_ai_generated": False, "confidence": 0.0,
                    "frames_analyzed": 0, "frames_flagged": 0}

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._run_full_analysis, frame_paths)
            return result
        except Exception as e:
            logger.error(f"❌ Frame analysis failed: {e}")
            return {
                "is_ai_generated": False, "confidence": 0.0,
                "frames_analyzed": len(frame_paths), "frames_flagged": 0,
                "error": str(e),
            }

    # ─── Core analysis (runs in executor thread) ──────────────────────────────

    def _run_full_analysis(self, frame_paths: List[str]) -> Dict:
        ai_scores = []
        qr_codes_found = []
        suspicious_qr_count = 0
        ocr_texts = []
        ocr_intent_hits = 0
        ocr_keyword_hits = 0

        for i, frame_path in enumerate(frame_paths):
            try:
                # 1. Load image
                img_pil = Image.open(frame_path).convert("RGB") if Image else None
                img_bgr = cv2.imread(frame_path) if CV2_AVAILABLE else None

                # 2. AI-generated score via CLIP
                ai_prob = self._score_ai_generated(img_pil, img_bgr) if img_pil else 0.0
                ai_scores.append(ai_prob)

                # 3. QR code detection
                if CV2_AVAILABLE and img_bgr is not None:
                    qr_data = self._detect_qr(img_bgr)
                    if qr_data:
                        qr_codes_found.extend(qr_data)
                        for url in qr_data:
                            if _is_suspicious_url(url):
                                suspicious_qr_count += 1

                # 4. OCR on-screen text (only every 3rd frame to save time)
                if EASYOCR_AVAILABLE and img_bgr is not None and i % 3 == 0:
                    text = self._ocr_frame(img_bgr)
                    if text:
                        ocr_texts.append(text)
                        hits = self._count_intent_hits(text)
                        ocr_intent_hits += hits
                        ocr_keyword_hits += self._count_scam_keywords(text)

            except Exception as e:
                logger.warning(f"⚠️ Frame {i} analysis failed: {e}")
                ai_scores.append(0.0)

        # ── Aggregate ──────────────────────────────────────────────────────
        avg_confidence = sum(ai_scores) / len(ai_scores) if ai_scores else 0.0
        flagged = sum(1 for s in ai_scores if s > 0.5)
        is_ai = flagged / len(ai_scores) > 0.3 if ai_scores else False

        # QR risk boost
        qr_risk_boost = min(suspicious_qr_count * 0.15, 0.4)
        # OCR scam-text boost (Robux price boards, fake gifts, payment prompts)
        ocr_risk_score = min(ocr_intent_hits * 0.12 + ocr_keyword_hits * 0.08, 0.75)
        ocr_risk_boost = min(ocr_risk_score, 0.5)

        final_confidence = min(avg_confidence + qr_risk_boost + ocr_risk_boost, 1.0)
        if qr_risk_boost > 0 or ocr_risk_boost > 0.1:
            is_ai = True  # Scam visuals detected even if deepfake score is low

        result = {
            "is_ai_generated":     is_ai,
            "confidence":          round(final_confidence, 3),
            "frames_analyzed":     len(frame_paths),
            "frames_flagged":      flagged,
            "frame_scores":        [round(s, 3) for s in ai_scores],
            # QR
            "qr_codes_found":      qr_codes_found,
            "suspicious_qr_count": suspicious_qr_count,
            # OCR
            "ocr_texts":           ocr_texts[:5],  # Cap at 5 to avoid huge response
            "ocr_intent_hits":     ocr_intent_hits,
            "ocr_keyword_hits":    ocr_keyword_hits,
            "ocr_risk_score":      round(ocr_risk_score, 3),
        }
        logger.info(f"🤖 AI={is_ai} conf={final_confidence:.3f} | "
                    f"QR={len(qr_codes_found)}(sus={suspicious_qr_count}) | "
                    f"OCR intents={ocr_intent_hits} keywords={ocr_keyword_hits} risk={ocr_risk_score:.3f}")
        return result

    # ─── AI-generated scoring ─────────────────────────────────────────────────

    def _score_ai_generated(self, img_pil, img_bgr) -> float:
        """Return 0.0 (real) → 1.0 (AI/scam). Uses CLIP if available, else texture analysis."""
        clip_score = self._clip_deepfake_score(img_pil) if (self.worker and img_pil) else None
        texture_score = self._texture_score(img_bgr) if (NUMPY_AVAILABLE and img_bgr is not None) else 0.0

        if clip_score is not None:
            # Blend: 70% CLIP, 30% texture
            return round(0.7 * clip_score + 0.3 * texture_score, 3)
        return round(texture_score, 3)

    def _clip_deepfake_score(self, img_pil) -> float:
        """Use CLIP to score: 'deepfake synthetic video' vs 'real authentic video'."""
        try:
            import torch
            processor = self.worker.processor
            model     = self.worker.model
            labels = [
                "deepfake AI-generated synthetic face video",
                "real authentic natural video footage",
            ]
            inputs = processor(text=labels, images=img_pil, return_tensors="pt", padding=True)
            inputs = {k: v.to(self.config.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=-1).cpu().numpy().flatten()
            return float(probs[0])  # probability of "deepfake"
        except Exception as e:
            logger.debug(f"CLIP deepfake score failed: {e}")
            return 0.0

    def _texture_score(self, img_bgr) -> float:
        """
        Lightweight deepfake signal: real photos have natural texture noise.
        AI-generated images are often too smooth (low Laplacian variance).
        Returns 0.0 (natural) → 1.0 (suspiciously smooth / AI-like).
        """
        try:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            # Real images: high variance. AI-generated: often low variance.
            # Normalize: variance < 50 → suspicious (score → 1), variance > 500 → real (score → 0)
            score = max(0.0, 1.0 - (lap_var / 300.0))
            return min(score, 1.0)
        except Exception:
            return 0.0

    # ─── QR code detection ────────────────────────────────────────────────────

    def _detect_qr(self, img_bgr) -> List[str]:
        """Detect and decode QR codes. Returns list of decoded strings."""
        found = []
        try:
            detector = cv2.QRCodeDetector()
            data, _, _ = detector.detectAndDecode(img_bgr)
            if data:
                found.append(data)
        except Exception as e:
            logger.debug(f"QR detection failed: {e}")
        return found

    # ─── OCR ─────────────────────────────────────────────────────────────────

    def _ocr_frame(self, img_bgr) -> str:
        """Extract text from frame using EasyOCR."""
        try:
            reader = _get_ocr_reader()
            if reader is None:
                return ""
            # EasyOCR expects RGB
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            results = reader.readtext(img_rgb, detail=0, paragraph=True)
            return " ".join(results).strip()
        except Exception as e:
            logger.debug(f"OCR failed: {e}")
            return ""

    def _count_intent_hits(self, text: str) -> int:
        """Count how many scam intent patterns fire on OCR text."""
        try:
            from ai_engine.nlp_worker.intent_detector import detect_scam_intent
            result = detect_scam_intent(text)
            return result.get("intent_count", 0)
        except Exception:
            return 0

    def _count_scam_keywords(self, text: str) -> int:
        """Fast visual scam lexicon for OCR-heavy gaming scam frames."""
        t = (text or "").lower()
        keywords = [
            "robux", "roblox", "nạp robux", "bảng giá", "vnđ", "vnd",
            "nạp thẻ", "nạp thả ga", "uy tín", "tốc độ", "an toàn",
            "free robux", "giftcode", "gift code", "quà", "tặng",
            "kim cương", "quân huy", "v-bucks", "vbucks",
            "chuyển khoản", "momo", "zalopay", "bank",
        ]
        return sum(1 for kw in keywords if kw in t)
