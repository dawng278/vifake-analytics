"""
ViFake Analytics - Video Analysis Pipeline Coordinator

Orchestrates parallel processing of TikTok videos:
- Audio extraction + transcription + text analysis
- Frame extraction + AI-generated detection
- Result fusion and cleanup
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Optional

# Add project root to path for AI engine imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .media_extractor import MediaExtractor
from .transcriber import Transcriber
from .frame_analyzer import FrameAnalyzer
from .audio_ai_detector import AudioAIDetector
from .face_ai_detector import FaceAIDetector
from .cleanup import cleanup_session

logger = logging.getLogger(__name__)

class VideoAnalysisPipeline:
    """Coordinates video analysis pipeline with parallel processing"""

    def __init__(self):
        self.transcriber = Transcriber()
        self.frame_analyzer = FrameAnalyzer()
        self.audio_ai_detector = AudioAIDetector()
        self.face_ai_detector = FaceAIDetector()
        logger.info("🎬 VideoAnalysisPipeline initialized with enhanced AI detection")

    async def run(self, video_url: str, description: str = "", author: str = "") -> Dict:
        """
        Run complete video analysis pipeline.
        
        Args:
            video_url: Direct TikTok video URL
            description: Video caption from DOM
            author: Video author/creator
            
        Returns:
            Dict with analysis results
        """
        extractor = MediaExtractor(video_url)
        
        try:
            logger.info(f"🎬 Starting video analysis: {video_url}")
            
            # ── Bước 1: Extract audio + frames SONG SONG ────────
            logger.info("📥 Phase 1: Extracting audio and frames...")
            audio_task = asyncio.create_task(extractor.extract_audio())
            frames_task = asyncio.create_task(extractor.extract_frames(num_frames=8))
            
            # Chờ cả 2 hoàn thành với exception handling
            audio_path, frame_paths = await asyncio.gather(
                audio_task, 
                frames_task,
                return_exceptions=True   # Không crash nếu 1 branch lỗi
            )

            # ── Bước 2: Transcribe + Frame Analysis SONG SONG ───
            logger.info("🔍 Phase 2: Running parallel analysis...")
            
            # Branch A: audio → transcription + AI voice detection
            async def branch_a():
                if isinstance(audio_path, Exception):
                    logger.warning(f"⚠️ Audio extraction failed: {audio_path}")
                    return {
                        "verdict": "UNKNOWN", 
                        "confidence": 0.0, 
                        "intents": {},
                        "transcript": "",
                        "audio_ai": {"is_ai_voice": False, "ai_confidence": 0.0},
                        "error": str(audio_path)
                    }
                
                try:
                    # Transcribe audio
                    transcript_result = await self.transcriber.transcribe(audio_path)
                    
                    # AI Voice Detection (NEW)
                    audio_ai_result = await self.audio_ai_detector.analyze_audio(audio_path)
                    
                    # Build analysis text from all sources
                    full_text = self.transcriber.build_analysis_text(
                        transcript_result["text"], description, author
                    )
                    
                    # Run text analysis using existing pipeline
                    text_result = await self._run_text_analysis(full_text)
                    text_result["transcript"] = transcript_result["text"]
                    text_result["audio_ai"] = audio_ai_result  # Add AI voice detection
                    
                    logger.info(f"📝 Text + Audio AI analysis completed: {text_result.get('verdict', 'UNKNOWN')}")
                    logger.info(f"🎤 AI Voice Detection: {audio_ai_result.get('is_ai_voice', False)} ({audio_ai_result.get('ai_confidence', 0.0):.3f})")
                    return text_result
                    
                except Exception as e:
                    logger.error(f"❌ Text + Audio AI analysis failed: {e}")
                    return {
                        "verdict": "UNKNOWN", 
                        "confidence": 0.0, 
                        "intents": {},
                        "transcript": transcript_result.get("text", ""),
                        "error": str(e)
                    }

            # Branch B: frames → AI face detection (NEW)
            async def branch_b():
                if isinstance(frame_paths, Exception) or not frame_paths:
                    logger.warning(f"⚠️ Frame extraction failed: {frame_paths}")
                    return {
                        "is_ai_generated": False, 
                        "confidence": 0.0,
                        "faces_detected": 0,
                        "error": str(frame_paths) if isinstance(frame_paths, Exception) else "No frames extracted"
                    }
                
                try:
                    # Run both CLIP and Face AI detection
                    clip_result = await self.frame_analyzer.analyze_frames(frame_paths)
                    face_ai_result = await self.face_ai_detector.analyze_frames(frame_paths)
                    
                    # Combine results - prioritize Face AI detection
                    combined_result = {
                        "is_ai_generated": face_ai_result.get('is_ai_face', clip_result.get('is_ai_generated', False)),
                        "confidence": max(
                            face_ai_result.get('ai_confidence', 0.0),
                            clip_result.get('confidence', 0.0)
                        ),
                        "faces_detected": face_ai_result.get('faces_detected', 0),
                        "frames_analyzed": len(frame_paths),
                        
                        # Include both analysis results
                        "clip_analysis": clip_result,
                        "face_ai_analysis": face_ai_result,
                        
                        # Use Face AI as primary if available
                        "primary_method": "face_ai" if face_ai_result.get('faces_detected', 0) > 0 else "clip"
                    }
                    
                    logger.info(f"🤖 Face AI detection completed: {face_ai_result.get('is_ai_face', False)} ({face_ai_result.get('ai_confidence', 0.0):.3f})")
                    logger.info(f"👥 Faces detected: {face_ai_result.get('faces_detected', 0)}")
                    return combined_result
                    
                except Exception as e:
                    logger.error(f"❌ Face AI analysis failed: {e}")
                    return {
                        "is_ai_generated": False, 
                        "confidence": 0.0,
                        "faces_detected": 0,
                        "frames_analyzed": len(frame_paths) if frame_paths else 0,
                        "error": str(e)
                    }

            # Run both branches in parallel
            text_result, vision_result = await asyncio.gather(
                branch_a(), branch_b()
            )

            # ── Bước 3: Tổng hợp kết quả ────────────────────────
            logger.info("🔀 Phase 3: Merging results...")
            final_result = self._merge_results(text_result, vision_result)
            
            logger.info(f"✅ Video analysis completed: {final_result['verdict']} "
                       f"(confidence: {final_result['confidence']:.3f})")
            return final_result

        finally:
            # ── Bước 4: XÓA FILE TẠM — luôn chạy dù có lỗi ────
            logger.info("🗑️ Phase 4: Cleaning up temporary files...")
            await cleanup_session(extractor.session_dir)

    async def _run_text_analysis(self, text: str) -> Dict:
        """
        Gọi lại pipeline PhoBERT/XGBoost hiện có với transcript.
        Tái sử dụng logic từ main.py để maintain consistency.
        """
        if not text or len(text.strip()) < 10:
            # Video không có lời hoặc transcription thất bại
            return {
                "verdict": "SAFE",  # Default to safe for empty content
                "confidence": 0.5,
                "intents": {},
                "note": "Không transcribe được nội dung audio"
            }
        
        try:
            # Import existing analysis functions from main.py
            # This reuses the exact same logic as text analysis
            from backend_services.api_gateway.main import (
                _run_nlp_analysis,
                _run_fusion,
            )

            # Run NLP analysis (sync function)
            nlp_result = _run_nlp_analysis(text)

            # Neutral vision placeholder — actual vision/frame analysis is
            # handled by branch_b in the calling pipeline; here we only need
            # the NLP + fusion pass on the transcript text.
            vision_placeholder = {
                "combined_risk_score": 0.5,
                "safety_score": 0.5,
                "is_ai_generated": False,
                "confidence": 0.0,
            }

            # Run fusion (sync function)
            fusion_result = _run_fusion(vision_placeholder, nlp_result, "tiktok")

            return {
                "verdict": fusion_result.get("prediction", "SAFE"),
                "confidence": fusion_result.get("confidence", 0.0),
                "intents": nlp_result.get("intent", {}),
                "risk_level": fusion_result.get("risk_level", "LOW"),
                "requires_review": fusion_result.get("requires_review", False),
                "fusion_method": fusion_result.get("fusion_method", "unknown")
            }
            
        except Exception as e:
            logger.error(f"❌ Text analysis pipeline failed: {e}")
            return {
                "verdict": "SAFE",
                "confidence": 0.5,
                "intents": {},
                "error": str(e)
            }

    def _merge_results(self, text_result: Dict, vision_result: Dict) -> Dict:
        """
        Merge text + vision results into final verdict.
        Logic: no evidence → SAFE; evidence proportional to confidence/intent hits.
        """
        text_verdict = text_result.get("verdict", "UNKNOWN")
        text_conf    = text_result.get("confidence", 0.0)

        # UNKNOWN means extraction/analysis failed entirely → default SAFE (avoid false positive)
        if text_verdict == "UNKNOWN":
            logger.warning("⚠️ Text analysis returned UNKNOWN — defaulting to SAFE")
            text_verdict = "SAFE"
            text_conf    = 0.3

        # ── AI generation scores ────────────────────────────────
        vision_ai_conf = vision_result.get("confidence", 0.0)
        audio_ai_conf  = text_result.get("audio_ai", {}).get("ai_confidence", 0.0)
        final_ai_score = 0.6 * vision_ai_conf + 0.4 * audio_ai_conf
        is_ai_generated = vision_result.get("is_ai_generated", False)
        high_confidence_ai = (vision_ai_conf > 0.85) or (audio_ai_conf > 0.85)
        if high_confidence_ai:
            is_ai_generated = True

        # ── Intent analysis ─────────────────────────────────────
        intents = text_result.get("intents", {})
        intent_count   = sum(1 for v in intents.values() if v > 0.25)
        max_intent     = max(intents.values()) if intents else 0.0
        primary_intent = max(intents, key=intents.get) if intents else "none"

        # Intent labels (Vietnamese)
        INTENT_LABELS = {
            "credential_harvest": "Thu thập thông tin đăng nhập",
            "money_transfer":     "Yêu cầu chuyển tiền",
            "urgency_pressure":   "Tạo áp lực khẩn cấp",
            "fake_reward":        "Phần thưởng giả mạo",
            "grooming_isolation": "Cô lập trẻ khỏi người lớn",
        }
        INTENT_RISK = {
            "credential_harvest": 0.9,
            "money_transfer":     0.95,
            "urgency_pressure":   0.7,
            "fake_reward":        0.85,
            "grooming_isolation": 1.0,
        }

        # ── Verdict decision ────────────────────────────────────
        # Priority: text NLP verdict is always primary
        # AI detection only upgrades (never downgrades) if there is real evidence
        final_verdict = text_verdict

        if text_verdict == "FAKE_SCAM":
            final_verdict = "FAKE_SCAM"
        elif text_verdict == "SUSPICIOUS":
            final_verdict = "SUSPICIOUS"
        elif text_verdict == "SAFE":
            # Only upgrade if AI confidence is genuinely high AND there is some
            # corroborating evidence (intent hits or audio anomaly)
            has_supporting_evidence = (intent_count > 0) or (audio_ai_conf > 0.6)
            if is_ai_generated and final_ai_score > 0.6 and has_supporting_evidence:
                final_verdict = "SUSPICIOUS"
            elif high_confidence_ai and final_ai_score > 0.7:
                final_verdict = "SUSPICIOUS"
            else:
                final_verdict = "SAFE"  # No evidence → stay SAFE

        # ── Build rich explanation ──────────────────────────────
        reasons = []

        # 1. NLP / text verdict reasons
        if text_verdict == "FAKE_SCAM":
            reasons.append("🚨 Văn bản phát hiện nội dung lừa đảo rõ ràng")
        elif text_verdict == "SUSPICIOUS":
            reasons.append("⚠️ Văn bản có một số từ ngữ đáng ngờ")

        # 2. Per-intent reasons (only those with meaningful score)
        active_intents = [(k, v) for k, v in intents.items() if v > 0.25]
        active_intents.sort(key=lambda x: -x[1])
        for intent_key, score in active_intents:
            label = INTENT_LABELS.get(intent_key, intent_key)
            pct   = round(score * 100)
            risk  = INTENT_RISK.get(intent_key, 0.5)
            if risk >= 0.95:
                icon = "🔴"
            elif risk >= 0.8:
                icon = "🟠"
            else:
                icon = "🟡"
            reasons.append(f"{icon} {label} ({pct}%)")

        # 3. AI voice / deepfake reasons
        if audio_ai_conf > 0.6:
            pct = round(audio_ai_conf * 100)
            if audio_ai_conf > 0.85:
                reasons.append(f"🤖 Giọng nói có khả năng cao là AI-cloned ({pct}%)")
            else:
                reasons.append(f"🎙 Giọng nói có dấu hiệu bất thường, có thể là AI ({pct}%)")

        if vision_ai_conf > 0.6:
            pct   = round(vision_ai_conf * 100)
            faces = vision_result.get("faces_detected", 0)
            if faces > 0:
                reasons.append(f"👤 Phát hiện {faces} khuôn mặt có khả năng AI-generated ({pct}%)")
            else:
                reasons.append(f"🖼 Hình ảnh có dấu hiệu AI-generated ({pct}%)")

        # 4. Positive signals when verdict is SAFE
        if final_verdict == "SAFE":
            if not active_intents and audio_ai_conf < 0.4 and vision_ai_conf < 0.4:
                reasons.append("✅ Không phát hiện từ khoá lừa đảo")
                reasons.append("✅ Giọng nói và hình ảnh bình thường")
            else:
                reasons.append("✅ Không đủ dấu hiệu để phân loại nguy hiểm")

        explanation = " · ".join(reasons) if reasons else "Không phát hiện dấu hiệu nguy hiểm"

        # ── Final confidence ────────────────────────────────────
        # For SAFE: confidence = 1 - max(text_conf_of_danger, ai_score, max_intent)
        # For FAKE_SCAM/SUSPICIOUS: use the positive danger confidence
        if final_verdict == "SAFE":
            danger_evidence = max(
                (text_conf if text_verdict != "SAFE" else 0.0),
                final_ai_score,
                max_intent * 0.5,
            )
            final_conf = max(0.5, 1.0 - danger_evidence)
        else:
            final_conf = max(text_conf, final_ai_score, max_intent)

        # Risk level
        if final_verdict == "FAKE_SCAM":
            risk_level = "HIGH"
        elif final_verdict == "SUSPICIOUS":
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "verdict":        final_verdict,
            "confidence":     round(final_conf, 3),
            "is_ai_generated": is_ai_generated,
            "ai_confidence":  round(final_ai_score, 3),
            "intents":        intents,
            "transcript":     text_result.get("transcript", ""),
            "explanation":    explanation,
            "risk_level":     risk_level,
            "requires_review": final_verdict != "SAFE",
            # debug
            "text_verdict":             text_verdict,
            "text_confidence":          text_conf,
            "ai_vision_confidence":     vision_ai_conf,
            "ai_audio_confidence":      audio_ai_conf,
            "vision_frames_analyzed":   vision_result.get("frames_analyzed", 0),
            "vision_faces_detected":    vision_result.get("faces_detected", 0),
            "audio_ai_detected":        text_result.get("audio_ai", {}).get("is_ai_voice", False),
        }

