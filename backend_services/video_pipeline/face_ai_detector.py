"""
ViFake Analytics - Face AI Detector

Detects AI-generated / deepfake faces using signal-based analysis:
- MediaPipe face detection (primary, CPU-friendly)
- OpenCV Haar cascade (fallback)
- Per-face deepfake signals: texture smoothness, symmetry, color uniformity
  (no trained model needed — these are geometry/statistics-based signals)
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

# ── Optional MediaPipe ──────────────────────────────────────────────────────
try:
    import mediapipe as mp
    # mp.solutions was removed in mediapipe 0.10.x — use new Tasks API if available
    if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
        _mp_face = mp.solutions.face_detection
        MEDIAPIPE_AVAILABLE = True
    else:
        # mediapipe 0.10+ Tasks API — not trivially replaceable; fall back to OpenCV
        _mp_face = None
        MEDIAPIPE_AVAILABLE = False
        logger.info("MediaPipe >= 0.10 detected (no mp.solutions) — falling back to OpenCV Haar cascade")
except (ImportError, AttributeError):
    _mp_face = None
    MEDIAPIPE_AVAILABLE = False
    logger.info("MediaPipe not available — falling back to OpenCV Haar cascade")

# ── OpenCV Haar cascade (always available) ──────────────────────────────────
_HAAR_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_haar_cascade = cv2.CascadeClassifier(_HAAR_PATH)


class FaceAIDetector:
    """
    Detect AI-generated / deepfake faces.

    Pipeline per frame:
      1. Detect faces (MediaPipe → Haar fallback)
      2. For each face crop, compute 4 deepfake signals
      3. Aggregate across all frames → is_ai_face + ai_confidence
    """

    MAX_FACES       = 3
    CONFIDENCE_THR  = 0.50

    def __init__(self):
        self._mp_detector = None
        if MEDIAPIPE_AVAILABLE:
            try:
                self._mp_detector = _mp_face.FaceDetection(
                    model_selection=0,      # 0 = short-range (closer faces), 1 = full-range
                    min_detection_confidence=0.4
                )
                logger.info("✅ MediaPipe face detector loaded")
            except Exception as e:
                logger.warning(f"⚠️ MediaPipe init failed: {e}")
                self._mp_detector = None

    # ─── Public ───────────────────────────────────────────────────────────────

    async def analyze_frames(self, frame_paths: List[str]) -> Dict:
        """Analyze list of frame images and return aggregate deepfake detection result."""
        if not frame_paths:
            return self._empty_result()
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._analyze_all, frame_paths)
        except Exception as e:
            logger.error(f"❌ Face AI analysis failed: {e}")
            return {**self._empty_result(), "error": str(e)}

    # ─── Core ─────────────────────────────────────────────────────────────────

    def _analyze_all(self, frame_paths: List[str]) -> Dict:
        all_face_scores: List[float] = []
        total_faces = 0

        for frame_path in frame_paths:
            img_bgr = cv2.imread(frame_path)
            if img_bgr is None:
                continue

            face_bboxes = self._detect_faces(img_bgr)
            total_faces += len(face_bboxes)

            for bbox in face_bboxes[:self.MAX_FACES]:
                crop = self._crop_face(img_bgr, bbox)
                if crop is not None:
                    score = self._deepfake_score(crop)
                    all_face_scores.append(score)

        if not all_face_scores:
            return self._empty_result(faces=total_faces)

        avg_score = float(np.mean(all_face_scores))
        max_score = float(np.max(all_face_scores))
        # Use max score: if any face is suspicious, flag it
        final_score = max(avg_score * 0.4 + max_score * 0.6, 0.0)

        return {
            "is_ai_face":       final_score > self.CONFIDENCE_THR,
            "ai_confidence":    round(final_score, 3),
            "faces_detected":   total_faces,
            "analysis_type":    "mediapipe" if self._mp_detector else "opencv_haar",
            "face_scores":      [round(s, 3) for s in all_face_scores],
        }

    # ─── Face detection ────────────────────────────────────────────────────────

    def _detect_faces(self, img_bgr: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Returns list of (x, y, w, h) bounding boxes."""
        if self._mp_detector is not None:
            return self._detect_mediapipe(img_bgr)
        return self._detect_haar(img_bgr)

    def _detect_mediapipe(self, img_bgr: np.ndarray) -> List[Tuple[int, int, int, int]]:
        try:
            h, w = img_bgr.shape[:2]
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            results = self._mp_detector.process(img_rgb)
            boxes = []
            if results.detections:
                for det in results.detections:
                    bb = det.location_data.relative_bounding_box
                    x = max(0, int(bb.xmin * w))
                    y = max(0, int(bb.ymin * h))
                    bw = min(int(bb.width * w), w - x)
                    bh = min(int(bb.height * h), h - y)
                    if bw > 30 and bh > 30:
                        boxes.append((x, y, bw, bh))
            return boxes
        except Exception as e:
            logger.debug(f"MediaPipe detection failed: {e}")
            return self._detect_haar(img_bgr)

    def _detect_haar(self, img_bgr: np.ndarray) -> List[Tuple[int, int, int, int]]:
        try:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            faces = _haar_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5,
                minSize=(48, 48), maxSize=(512, 512)
            )
            if len(faces) == 0:
                return []
            return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
        except Exception as e:
            logger.debug(f"Haar detection failed: {e}")
            return []

    def _crop_face(self, img_bgr: np.ndarray, bbox: Tuple) -> np.ndarray:
        """Crop face with 20% margin, resize to 128×128."""
        x, y, w, h = bbox
        margin = int(0.2 * min(w, h))
        H, W = img_bgr.shape[:2]
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(W, x + w + margin)
        y2 = min(H, y + h + margin)
        crop = img_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        return cv2.resize(crop, (128, 128))

    # ─── Deepfake signals ─────────────────────────────────────────────────────

    def _deepfake_score(self, face_bgr: np.ndarray) -> float:
        """
        Aggregate deepfake score from 4 signals (0 = real, 1 = likely AI).

        Signals:
          1. Texture smoothness  — AI faces are often too smooth (low Laplacian)
          2. Left-right symmetry — AI faces are hyper-symmetric
          3. Color uniformity    — AI skin tone is unusually uniform
          4. Frequency noise     — Real photos have natural sensor noise (high FFT energy)
        """
        s_texture  = self._signal_texture(face_bgr)
        s_symmetry = self._signal_symmetry(face_bgr)
        s_color    = self._signal_color_uniformity(face_bgr)
        s_freq     = self._signal_frequency_noise(face_bgr)

        # Weighted blend
        score = 0.35 * s_texture + 0.25 * s_symmetry + 0.20 * s_color + 0.20 * s_freq
        logger.debug(
            f"Face signals: texture={s_texture:.2f} sym={s_symmetry:.2f} "
            f"color={s_color:.2f} freq={s_freq:.2f} → {score:.2f}"
        )
        return float(np.clip(score, 0.0, 1.0))

    def _signal_texture(self, face: np.ndarray) -> float:
        """
        Low Laplacian variance → suspiciously smooth → higher AI probability.
        Empirical: real faces ~200–800 variance; AI faces ~20–150.
        """
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        # Score: 1.0 at var=0, 0.0 at var>=400
        return float(np.clip(1.0 - lap_var / 400.0, 0.0, 1.0))

    def _signal_symmetry(self, face: np.ndarray) -> float:
        """
        AI faces tend to be near-perfect horizontally symmetric.
        Compare left half vs horizontally-flipped right half.
        High similarity → suspicious.
        """
        h, w = face.shape[:2]
        mid = w // 2
        left  = face[:, :mid].astype(float)
        right = cv2.flip(face[:, mid:mid + mid], 1).astype(float)
        if left.shape != right.shape:
            return 0.0
        diff = np.abs(left - right).mean()
        # diff=0 → perfect symmetry (score 1), diff>60 → natural (score 0)
        return float(np.clip(1.0 - diff / 60.0, 0.0, 1.0))

    def _signal_color_uniformity(self, face: np.ndarray) -> float:
        """
        AI-generated skin has unnaturally uniform color distribution.
        Low std-dev of hue/saturation channels → suspicious.
        """
        hsv = cv2.cvtColor(face, cv2.COLOR_BGR2HSV).astype(float)
        h_std = hsv[:, :, 0].std()
        s_std = hsv[:, :, 1].std()
        combined_std = (h_std + s_std) / 2.0
        # Low std → high score (suspicious)
        return float(np.clip(1.0 - combined_std / 40.0, 0.0, 1.0))

    def _signal_frequency_noise(self, face: np.ndarray) -> float:
        """
        Real camera photos contain high-frequency sensor noise.
        AI images are often missing this noise (over-smooth frequency spectrum).
        Low high-freq energy → suspicious.
        """
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY).astype(float)
        fft  = np.fft.fft2(gray)
        fft_shift = np.fft.fftshift(fft)
        mag  = np.abs(fft_shift)

        h, w = mag.shape
        cy, cx = h // 2, w // 2
        # High-frequency band: outer 25% of spectrum
        y1, y2 = int(cy * 0.5), int(cy * 1.5)
        x1, x2 = int(cx * 0.5), int(cx * 1.5)
        low_energy  = mag[y1:y2, x1:x2].mean()
        total_energy = mag.mean() + 1e-8
        hf_ratio = 1.0 - (low_energy / total_energy)

        # Very low hf_ratio → missing noise → AI suspicious
        return float(np.clip(1.0 - hf_ratio * 2.0, 0.0, 1.0))

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _empty_result(faces: int = 0) -> Dict:
        return {
            "is_ai_face":     False,
            "ai_confidence":  0.0,
            "faces_detected": faces,
            "analysis_type":  "no_faces",
            "face_scores":    [],
        }
