#!/usr/bin/env python3
"""
CLIP FP16 Vision Worker for ViFake Analytics
Multi-modal image analysis with memory optimization for RTX 2050 (4GB VRAM)

Tuân thủ Privacy-by-Design:
- Zero-trust RAM processing
- No persistent storage of harmful content
- Memory optimization for GPU constraints
"""

import logging
import gc
import os
import yaml
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_PROMPTS_YAML = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "clip_prompts.yaml"
)

def _load_clip_prompts() -> dict:
    """Load domain-specific CLIP prompts from YAML config."""
    try:
        with open(_PROMPTS_YAML, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        labels = (
            cfg.get("safe", []) +
            cfg.get("suspicious", []) +
            cfg.get("high_risk", [])
        )
        risk_map = cfg.get("risk_map", {})
        return {"labels": labels, "risk_map": risk_map}
    except Exception as e:
        logger.warning(f"Could not load clip_prompts.yaml ({e}), using built-in prompts")
        return {}

# Optional heavy dependencies
try:
    import torch
    import torch.nn.functional as F
    from PIL import Image
    from transformers import CLIPProcessor, CLIPModel
    CLIP_AVAILABLE = True
except ImportError as _e:
    logger.warning(f"⚠️  CLIP/transformers not available ({_e}). Vision worker will run in mock mode.")
    CLIP_AVAILABLE = False
    torch = None
    Image = None

# Safe no_grad decorator — evaluated at class-definition time, must not call torch when None
if CLIP_AVAILABLE:
    _no_grad = torch.no_grad()
else:
    def _no_grad(fn):  # type: ignore
        return fn

@dataclass
class VisionConfig:
    """Cấu hình cho Vision Worker"""
    model_name: str = "openai/clip-vit-base-patch32"
    device: str = "cuda" if (CLIP_AVAILABLE and torch is not None and torch.cuda.is_available()) else "cpu"
    dtype: object = None  # torch.float16 when torch is available
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
        
        # Load domain-specific prompts from YAML; fall back to built-ins
        _prompt_cfg = _load_clip_prompts()
        if _prompt_cfg.get("labels"):
            self.CANDIDATE_LABELS = _prompt_cfg["labels"]
            _risk_map = _prompt_cfg.get("risk_map", {})
            self._safe_indices      = set(_risk_map.get("safe_indices", []))
            self._suspicious_indices = set(_risk_map.get("suspicious_indices", []))
            self._high_risk_indices  = set(_risk_map.get("high_risk_indices", []))
            logger.info(f"✅ Loaded {len(self.CANDIDATE_LABELS)} CLIP prompts from config/clip_prompts.yaml")
        else:
            # Built-in fallback prompts
            self.CANDIDATE_LABELS = [
                "safe cooking recipe food video",
                "educational tutorial content",
                "online scam phishing fraud warning message",
                "bank transfer payment QR code on screen",
                "fake prize giveaway lottery winner announcement",
                "deepfake AI-generated face synthetic video",
                "normal social media entertainment content",
                "celebrity advertisement promotion",
            ]
            self._safe_indices       = {0, 1, 6, 7}
            self._suspicious_indices = set()
            self._high_risk_indices  = {2, 3, 4, 5}

        # Map label index → risk category (legacy, kept for _calculate_risk_scores)
        self.LABEL_RISK_MAP = {
            i: "high_risk" for i in self._high_risk_indices
        }
        self.LABEL_RISK_MAP.update({i: "suspicious" for i in self._suspicious_indices})
        
        # Initialize model
        self._load_model()
    
    def _load_model(self):
        """Load CLIP model with FP16 optimization"""
        logger.info("🔍 Loading CLIP model with FP16 optimization...")
        
        try:
            # Load processor
            self.processor = CLIPProcessor.from_pretrained(self.config.model_name)
            
            # Load model with FP16 — use_safetensors=True avoids torch.load CVE-2025-32434 check
            self.model = CLIPModel.from_pretrained(
                self.config.model_name,
                torch_dtype=self.config.dtype,
                device_map="auto",
                use_safetensors=True,
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
    
    def preprocess_image(self, image_path: str) -> object:
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
    
    @_no_grad
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
        
        # Aggregate risk scores using label_risk_map
        risk_subscores = {}
        for idx, category in self.LABEL_RISK_MAP.items():
            risk_subscores[category] = float(probs[idx]) if idx < len(probs) else 0.0

        scam_score       = risk_subscores.get("scam_risk", 0.0)
        money_score      = risk_subscores.get("money_risk", 0.0)
        fake_reward_score= risk_subscores.get("fake_reward_risk", 0.0)
        deepfake_score   = risk_subscores.get("deepfake_risk", 0.0)

        # Combined content risk (max across scam-related labels)
        combined_risk = max(scam_score, money_score, fake_reward_score, deepfake_score)
        
        # Safety score: safe labels vs risk labels
        safe_content = probs[0] + probs[1]  # cooking + educational
        safety_score = safe_content / (safe_content + combined_risk + 1e-8)
        
        # Risk level
        if combined_risk >= self.config.risk_threshold:
            risk_level = "HIGH"
        elif combined_risk >= 0.4:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        scores.update({
            "combined_risk_score": float(combined_risk),
            "safety_score":        float(safety_score),
            "risk_level":          risk_level,
            "is_safe":             combined_risk < self.config.risk_threshold,
            "requires_review":     combined_risk >= 0.5,
            # Per-category breakdowns
            "scam_risk":           scam_score,
            "money_risk":          money_score,
            "fake_reward_risk":    fake_reward_score,
            "deepfake_risk":       deepfake_score,
            # Legacy aliases kept for pipeline compatibility
            "violent_risk":        0.0,
            "sexual_risk":         0.0,
            "inappropriate_risk":  0.0,
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
