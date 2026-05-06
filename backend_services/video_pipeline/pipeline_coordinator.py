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
from .cleanup import cleanup_session

logger = logging.getLogger(__name__)

class VideoAnalysisPipeline:
    """Coordinates video analysis pipeline with parallel processing"""

    def __init__(self):
        self.transcriber = Transcriber()
        self.frame_analyzer = FrameAnalyzer()
        logger.info("🎬 VideoAnalysisPipeline initialized")

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
            
            # Branch A: audio → text → PhoBERT
            async def branch_a():
                if isinstance(audio_path, Exception):
                    logger.warning(f"⚠️ Audio extraction failed: {audio_path}")
                    return {
                        "verdict": "UNKNOWN", 
                        "confidence": 0.0, 
                        "intents": {},
                        "transcript": "",
                        "error": str(audio_path)
                    }
                
                try:
                    # Transcribe audio
                    transcript_result = await self.transcriber.transcribe(audio_path)
                    
                    # Build analysis text from all sources
                    full_text = self.transcriber.build_analysis_text(
                        transcript_result["text"], description, author
                    )
                    
                    # Run text analysis using existing pipeline
                    text_result = await self._run_text_analysis(full_text)
                    text_result["transcript"] = transcript_result["text"]
                    
                    logger.info(f"📝 Text analysis completed: {text_result.get('verdict', 'UNKNOWN')}")
                    return text_result
                    
                except Exception as e:
                    logger.error(f"❌ Text analysis failed: {e}")
                    return {
                        "verdict": "UNKNOWN", 
                        "confidence": 0.0, 
                        "intents": {},
                        "transcript": transcript_result.get("text", ""),
                        "error": str(e)
                    }

            # Branch B: frames → AI detection
            async def branch_b():
                if isinstance(frame_paths, Exception) or not frame_paths:
                    logger.warning(f"⚠️ Frame extraction failed: {frame_paths}")
                    return {
                        "is_ai_generated": False, 
                        "confidence": 0.0,
                        "frames_analyzed": 0,
                        "error": str(frame_paths) if isinstance(frame_paths, Exception) else "No frames extracted"
                    }
                
                try:
                    vision_result = await self.frame_analyzer.analyze_frames(frame_paths)
                    logger.info(f"🤖 AI detection completed: {vision_result.get('is_ai_generated', False)}")
                    return vision_result
                    
                except Exception as e:
                    logger.error(f"❌ Frame analysis failed: {e}")
                    return {
                        "is_ai_generated": False, 
                        "confidence": 0.0,
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
                _run_nlp_inference, 
                _run_vision_inference,
                _run_fusion_analysis
            )
            
            # Run NLP analysis
            nlp_result = await _run_nlp_inference(text, "tiktok")
            
            # Run vision analysis (placeholder for video context)
            vision_result = await _run_vision_inference([], "tiktok")
            
            # Run fusion
            fusion_result = await _run_fusion_analysis(vision_result, nlp_result, "tiktok")
            
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
        Kết hợp kết quả từ text pipeline và vision pipeline.
        
        Logic:
        - Nếu text verdict = FAKE_SCAM → final = FAKE_SCAM (bất kể AI hay không)
        - Nếu text = SAFE nhưng AI-generated với confidence cao → SUSPICIOUS
        - Nếu cả 2 đều SAFE → SAFE
        """
        text_verdict = text_result.get("verdict", "UNKNOWN")
        text_conf = text_result.get("confidence", 0.0)
        is_ai = vision_result.get("is_ai_generated", False)
        ai_conf = vision_result.get("confidence", 0.0)
        
        # Nâng cấp verdict nếu phát hiện AI-generated
        final_verdict = text_verdict
        if text_verdict == "SAFE" and is_ai and ai_conf > 0.7:
            final_verdict = "SUSPICIOUS"
            logger.info(f"🔍 Upgraded SAFE to SUSPICIOUS due to AI detection (confidence: {ai_conf:.3f})")
        
        # Tạo explanation tổng hợp
        explanations = []
        if text_verdict == "FAKE_SCAM":
            explanations.append("Nội dung có dấu hiệu lừa đảo rõ ràng")
        elif text_verdict == "SUSPICIOUS":
            explanations.append("Nội dung có khả năng lừa đảo")
        
        if is_ai and ai_conf > 0.6:
            explanations.append(f"Video có thể được tạo bằng AI ({round(ai_conf*100)}% confidence)")
        
        if not explanations:
            explanations.append("Không phát hiện dấu hiệu nguy hiểm")
        
        # Build final result
        return {
            "verdict": final_verdict,
            "confidence": text_conf,
            "is_ai_generated": is_ai,
            "ai_confidence": ai_conf,
            "intents": text_result.get("intents", {}),
            "transcript": text_result.get("transcript", ""),
            "explanation": " · ".join(explanations),
            "risk_level": text_result.get("risk_level", "LOW"),
            "requires_review": final_verdict != "SAFE",
            
            # Additional debugging info
            "text_verdict": text_verdict,
            "text_confidence": text_conf,
            "vision_frames_analyzed": vision_result.get("frames_analyzed", 0),
            "vision_frames_flagged": vision_result.get("frames_flagged", 0),
        }
