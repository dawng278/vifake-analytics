#!/usr/bin/env python3
"""
CLIP FP16 Vision Worker for ViFake Analytics
Multi-modal image analysis with memory optimization for RTX 2050 (4GB VRAM)

Tuân thủ Privacy-by-Design:
- Zero-trust RAM processing
- No persistent storage of harmful content
- Memory optimization for GPU constraints
"""

import torch
import torch.nn.functional as F
from PIL import Image
import logging
import gc
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from transformers import CLIPProcessor, CLIPModel
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class VisionConfig:
    """Cấu hình cho Vision Worker"""
    model_name: str = "openai/clip-vit-base-patch32"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    dtype: torch.dtype = torch.float16  # FP16 for memory efficiency
    max_image_size: Tuple[int, int] = (336, 336)
    batch_size: int = 1  # Conservative for 4GB VRAM
    
    # Risk scoring thresholds
    risk_threshold: float = 0.7
    nsfw_threshold: float = 0.8
    
    # Memory management
    cleanup_frequency: int = 10  # Clean up every N inferences
    memory_cleanup_threshold: float = 0.8  # Clean when 80% VRAM used

class CLIPVisionWorker:
    """CLIP-based vision analysis worker with FP16 optimization"""
    
    def __init__(self, config: VisionConfig):
        self.config = config
        self.model = None
        self.processor = None
        self.inference_count = 0
        
        # Risk classification labels
        self.CANDIDATE_LABELS = [
            "child-safe cartoon content",
            "educational content for children", 
            "violent or disturbing content targeting children",
            "scam or phishing content",
            "sexual content",
            "inappropriate content for minors",
            "normal social media content",
            "advertisement targeting children"
        ]
        
        # Initialize model
        self._load_model()
    
    def _load_model(self):
        """Load CLIP model with FP16 optimization"""
        logger.info("🔍 Loading CLIP model with FP16 optimization...")
        
        try:
            # Load processor
            self.processor = CLIPProcessor.from_pretrained(self.config.model_name)
            
            # Load model with FP16
            self.model = CLIPModel.from_pretrained(
                self.config.model_name,
                torch_dtype=self.config.dtype,
                device_map="auto"
            )
            
            # Set to evaluation mode
            self.model.eval()
            
            # Enable memory efficient attention if available
            if hasattr(self.model, "gradient_checkpointing_enable"):
                self.model.gradient_checkpointing_enable()
            
            logger.info(f"✅ CLIP model loaded on {self.config.device}")
            logger.info(f"📱 Model dtype: {self.config.dtype}")
            logger.info(f"💾 VRAM usage: {self._get_vram_usage():.2f} GB")
            
        except Exception as e:
            logger.error(f"❌ Failed to load CLIP model: {e}")
            raise
    
    def _get_vram_usage(self) -> float:
        """Get current VRAM usage in GB"""
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024**3)
        return 0.0
    
    def _cleanup_memory(self):
        """Cleanup GPU memory"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        logger.debug(f"🧹 VRAM after cleanup: {self._get_vram_usage():.2f} GB")
    
    def preprocess_image(self, image_path: str) -> torch.Tensor:
        """Preprocess image for CLIP inference"""
        try:
            # Load and resize image
            image = Image.open(image_path).convert("RGB")
            
            # Resize if needed (memory efficient)
            if image.size != self.config.max_image_size:
                image.thumbnail(self.config.max_image_size, Image.Resampling.LANCZOS)
            
            # Process with CLIP processor
            inputs = self.processor(
                text=self.CANDIDATE_LABELS,
                images=image,
                return_tensors="pt",
                padding=True
            )
            
            # Move to device and convert dtype
            inputs = {k: v.to(self.config.device, dtype=self.config.dtype) for k, v in inputs.items()}
            
            return inputs
            
        except Exception as e:
            logger.error(f"❌ Failed to preprocess image {image_path}: {e}")
            raise
    
    @torch.no_grad()
    def analyze_image(self, image_path: str) -> Dict[str, float]:
        """Analyze image and return risk scores"""
        logger.info(f"🔍 Analyzing image: {image_path}")
        
        try:
            # Preprocess image
            inputs = self.preprocess_image(image_path)
            
            # Run inference
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=-1)
            
            # Convert to numpy for easier handling
            probs = probs.cpu().numpy().flatten()
            
            # Calculate risk scores
            risk_scores = self._calculate_risk_scores(probs)
            
            # Memory management
            self.inference_count += 1
            if self.inference_count % self.config.cleanup_frequency == 0:
                self._cleanup_memory()
            
            # Check VRAM usage
            vram_usage = self._get_vram_usage()
            if vram_usage > self.config.memory_cleanup_threshold:
                logger.warning(f"⚠️ High VRAM usage: {vram_usage:.2f} GB - forcing cleanup")
                self._cleanup_memory()
            
            return risk_scores
            
        except Exception as e:
            logger.error(f"❌ Failed to analyze image: {e}")
            self._cleanup_memory()
            raise
    
    def _calculate_risk_scores(self, probs: np.ndarray) -> Dict[str, float]:
        """Calculate comprehensive risk scores from CLIP probabilities"""
        scores = {}
        
        # Individual label probabilities
        for i, label in enumerate(self.CANDIDATE_LABELS):
            scores[label] = float(probs[i])
        
        # Aggregate risk categories
        violent_score = probs[2]  # "violent or disturbing content targeting children"
        scam_score = probs[3]     # "scam or phishing content"
        sexual_score = probs[4]    # "sexual content"
        inappropriate_score = probs[5]  # "inappropriate content for minors"
        
        # Combined risk score
        combined_risk = max(violent_score, scam_score, sexual_score, inappropriate_score)
        
        # Safety score (inverse of risk)
        safe_content = probs[0] + probs[1]  # "child-safe" + "educational"
        safety_score = safe_content / (safe_content + combined_risk + 1e-8)
        
        # Categorize risk level
        if combined_risk >= self.config.risk_threshold:
            risk_level = "HIGH"
        elif combined_risk >= 0.4:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Additional metrics
        scores.update({
            "combined_risk_score": float(combined_risk),
            "safety_score": float(safety_score),
            "risk_level": risk_level,
            "is_safe": combined_risk < self.config.risk_threshold,
            "requires_review": combined_risk >= 0.5,
            
            # Specific risk breakdowns
            "violent_risk": float(violent_score),
            "scam_risk": float(scam_score),
            "sexual_risk": float(sexual_score),
            "inappropriate_risk": float(inappropriate_score),
            
            # Metadata
            "inference_timestamp": torch.cuda.get_device_properties(0).total_memory / (1024**3) if torch.cuda.is_available() else 0,
            "vram_usage_gb": self._get_vram_usage()
        })
        
        return scores
    
    def get_vision_risk_score(self, image_path: str) -> float:
        """Get single risk score for quick decision making"""
        try:
            risk_scores = self.analyze_image(image_path)
            return risk_scores["combined_risk_score"]
        except Exception as e:
            logger.error(f"❌ Failed to get risk score: {e}")
            return 1.0  # Conservative: assume high risk on error
    
    def batch_analyze(self, image_paths: List[str]) -> List[Dict[str, float]]:
        """Analyze multiple images with memory management"""
        logger.info(f"🔍 Batch analyzing {len(image_paths)} images")
        
        results = []
        
        for i, image_path in enumerate(image_paths):
            try:
                result = self.analyze_image(image_path)
                results.append(result)
                
                # Progress logging
                if (i + 1) % 10 == 0:
                    logger.info(f"📊 Processed {i + 1}/{len(image_paths)} images")
                
            except Exception as e:
                logger.error(f"❌ Failed to analyze {image_path}: {e}")
                # Add error result
                error_result = {
                    "error": str(e),
                    "combined_risk_score": 1.0,  # Conservative
                    "risk_level": "HIGH",
                    "is_safe": False
                }
                results.append(error_result)
        
        # Final cleanup
        self._cleanup_memory()
        
        logger.info(f"✅ Batch analysis completed: {len(results)} results")
        return results
    
    def emergency_cleanup(self):
        """Emergency VRAM cleanup for OOM prevention"""
        logger.warning("🚨 Emergency VRAM cleanup triggered!")
        
        try:
            # Clear model from GPU
            if self.model is not None:
                self.model.cpu()
                del self.model
                self.model = None
            
            # Clear processor
            if self.processor is not None:
                del self.processor
                self.processor = None
            
            # Force cleanup
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            gc.collect()
            
            logger.info(f"✅ Emergency cleanup completed. VRAM: {self._get_vram_usage():.2f} GB")
            
        except Exception as e:
            logger.error(f"❌ Emergency cleanup failed: {e}")
    
    def __del__(self):
        """Cleanup on deletion"""
        self.emergency_cleanup()

# Global instance for singleton pattern
_vision_worker = None

def get_vision_worker() -> CLIPVisionWorker:
    """Get singleton vision worker instance"""
    global _vision_worker
    if _vision_worker is None:
        config = VisionConfig()
        _vision_worker = CLIPVisionWorker(config)
    return _vision_worker

# Convenience functions
def analyze_image_risk(image_path: str) -> Dict[str, float]:
    """Quick image analysis function"""
    worker = get_vision_worker()
    return worker.analyze_image(image_path)

def get_image_risk_score(image_path: str) -> float:
    """Get single risk score"""
    worker = get_vision_worker()
    return worker.get_vision_risk_score(image_path)

def batch_analyze_images(image_paths: List[str]) -> List[Dict[str, float]]:
    """Batch analyze images"""
    worker = get_vision_worker()
    return worker.batch_analyze(image_paths)

if __name__ == "__main__":
    # Test the vision worker
    logger.info("🧪 Testing CLIP Vision Worker...")
    
    try:
        worker = get_vision_worker()
        logger.info("✅ Vision worker initialized successfully")
        
        # Test with a dummy image path (will fail but tests the pipeline)
        # In real usage, provide actual image paths
        logger.info("🔍 Vision worker ready for image analysis")
        
    except Exception as e:
        logger.error(f"❌ Vision worker test failed: {e}")
        raise
