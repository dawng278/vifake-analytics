"""
ViFake Analytics - Frame Analyzer for AI-Generated Detection

Uses existing CLIP model to detect AI-generated content in video frames.
Leverages the vision worker already implemented in the project.
"""

import asyncio
import logging
from typing import List, Dict
import sys
from pathlib import Path

# Add project root to path for AI engine imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from ai_engine.vision_worker.clip_inference import CLIPVisionWorker, VisionConfig
    CLIP_AVAILABLE = True
except ImportError as _e:
    logging.getLogger(__name__).warning(f"⚠️  CLIP not available ({_e}). Frame analysis will be skipped.")
    CLIP_AVAILABLE = False
    CLIPVisionWorker = None
    VisionConfig = None

logger = logging.getLogger(__name__)

class FrameAnalyzer:
    """Analyze video frames to detect AI-generated content"""
    
    def __init__(self):
        self.worker = None
        if not CLIP_AVAILABLE:
            logger.warning("⚠️ CLIP unavailable — frame analysis disabled")
            return
        self.config = VisionConfig(
            device="cpu",  # Use CPU for Render.com compatibility
            dtype=None,     # float32 on CPU
            batch_size=1
        )
        self._load_model()
    
    def _load_model(self):
        """Load CLIP model for AI detection"""
        try:
            self.worker = CLIPVisionWorker(self.config)
            logger.info("✅ CLIP model loaded for AI detection")
        except Exception as e:
            logger.error(f"❌ Failed to load CLIP model: {e}")
            # Create fallback worker that returns neutral scores
            self.worker = None
    
    async def analyze_frames(self, frame_paths: List[str]) -> Dict:
        """
        Analyze list of frames to determine if video is AI-generated.
        
        Args:
            frame_paths: List of paths to frame images
            
        Returns:
            Dict with AI detection results
        """
        if not frame_paths:
            logger.warning("⚠️ No frames provided for analysis")
            return {
                "is_ai_generated": False,
                "confidence": 0.0,
                "frames_analyzed": 0,
                "frames_flagged": 0
            }
        
        if not self.worker:
            logger.warning("⚠️ CLIP worker not available, returning neutral result")
            return {
                "is_ai_generated": False,
                "confidence": 0.0,
                "frames_analyzed": len(frame_paths),
                "frames_flagged": 0
            }
        
        try:
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(
                None,
                self._run_inference,
                frame_paths
            )
            
            # Aggregate results
            ai_scores = [s for s in scores if s > 0.5]
            avg_confidence = sum(scores) / len(scores) if scores else 0.0
            is_ai = len(ai_scores) / len(scores) > 0.3  # >30% frames flagged as AI
            
            result = {
                "is_ai_generated": is_ai,
                "confidence": round(avg_confidence, 3),
                "frames_analyzed": len(frame_paths),
                "frames_flagged": len(ai_scores),
                "frame_scores": scores  # Include for debugging
            }
            
            logger.info(f"🤖 AI detection: {is_ai} (confidence: {avg_confidence:.3f}, "
                       f"{len(ai_scores)}/{len(scores)} frames flagged)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Frame analysis failed: {e}")
            return {
                "is_ai_generated": False,
                "confidence": 0.0,
                "frames_analyzed": len(frame_paths),
                "frames_flagged": 0,
                "error": str(e)
            }
    
    def _run_inference(self, frame_paths: List[str]) -> List[float]:
        """
        Run inference on frames to detect AI-generated content.
        Returns list of scores (0.0 = real, 1.0 = AI-generated).
        """
        scores = []
        
        for i, frame_path in enumerate(frame_paths):
            try:
                # Load and preprocess image
                image = Image.open(frame_path).convert("RGB")
                
                # Use CLIP to compare with AI-generated vs real concepts
                ai_score = self._compare_with_concept(image, "AI generated image, deepfake, synthetic, artificial")
                real_score = self._compare_with_concept(image, "real photograph, authentic, genuine, natural")
                
                # Calculate AI probability
                total_score = ai_score + real_score
                if total_score > 0:
                    ai_probability = ai_score / total_score
                else:
                    ai_probability = 0.5  # Neutral if both scores are low
                
                scores.append(ai_probability)
                logger.debug(f"Frame {i}: AI={ai_score:.3f}, Real={real_score:.3f}, Prob={ai_probability:.3f}")
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to analyze frame {i}: {e}")
                scores.append(0.0)  # Neutral score for failed frames
        
        return scores
    
    def _compare_with_concept(self, image: Image.Image, concept: str) -> float:
        """
        Compare image with text concept using CLIP.
        Returns similarity score.
        """
        try:
            # Use CLIP worker's internal methods
            result = self.worker.analyze_image(image, [concept])
            
            # Extract similarity score from result
            if result and "similarities" in result:
                return float(result["similarities"][0])
            else:
                # Fallback: use direct CLIP inference
                return self._direct_clip_inference(image, concept)
                
        except Exception as e:
            logger.warning(f"⚠️ CLIP comparison failed: {e}")
            return self._direct_clip_inference(image, concept)
    
    def _direct_clip_inference(self, image: Image.Image, concept: str) -> float:
        """
        Direct CLIP inference as fallback.
        """
        try:
            # Access CLIP model directly if available
            if hasattr(self.worker, 'model') and hasattr(self.worker, 'processor'):
                import torch
                
                # Preprocess inputs
                inputs = self.worker.processor(
                    text=[concept],
                    images=image,
                    return_tensors="pt",
                    padding=True
                )
                
                # Move to appropriate device
                device = torch.device(self.config.device)
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
                # Get embeddings
                with torch.no_grad():
                    outputs = self.worker.model(**inputs)
                    
                # Calculate similarity
                image_features = outputs.image_embeds
                text_features = outputs.text_embeds
                
                # Normalize features
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                
                # Cosine similarity
                similarity = torch.matmul(image_features, text_features.T).squeeze()
                return float(similarity.cpu().numpy())
            
        except Exception as e:
            logger.warning(f"⚠️ Direct CLIP inference failed: {e}")
        
        return 0.0  # Fallback score
