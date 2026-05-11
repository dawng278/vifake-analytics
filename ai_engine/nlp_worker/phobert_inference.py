# ai_engine/nlp_worker/phobert_inference.py
"""
PhoBERT ONNX Inference for ViFake Analytics
Optimized Vietnamese NLP processing with ONNX runtime

Tuân thủ Privacy-by-Design:
- Zero-trust RAM processing
- Fast CPU inference for scalability
- No persistent storage of harmful content
"""

import os
import logging
import numpy as np
from typing import Dict, List, Optional, Union
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional heavy dependencies — not available on lightweight deployments (Render free)
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError as _e:
    logger.warning(f"⚠️  transformers/torch not available ({_e}). PhoBERT will run in mock mode.")
    TRANSFORMERS_AVAILABLE = False
    torch = None

@dataclass
class NLPConfig:
    """Cấu hình cho NLP Worker"""
    model_name: str = "vinai/phobert-base"
    max_length: int = 256
    batch_size: int = 16
    device: str = "cpu"  # Optimized for CPU inference
    use_onnx: bool = True  # ONNX for faster inference
    
    # Model paths
    MODEL_DIR = "ai_engine/nlp_worker/phobert_finetuned/best_model"
    ONNX_DIR = "ai_engine/nlp_worker/phobert_onnx"
    DEFAULT_MODEL = "vinai/phobert-base"

class PhoBERTInference:
    """Optimized PhoBERT inference with ONNX support"""
    
    def __init__(self, model_path: Optional[str] = None, config: Optional[NLPConfig] = None):
        self.config = config or NLPConfig()
        self.tokenizer = None
        self.model = None

        if not TRANSFORMERS_AVAILABLE:
            logger.warning("⚠️  PhoBERT running in mock mode (transformers not installed)")
            self.labels = {0: "SAFE", 1: "TOXIC", 2: "MANIPULATIVE"}
            self.onnx_model = None
            return

        # Determine model path
        if model_path is None:
            model_path = self.config.MODEL_DIR if os.path.exists(self.config.MODEL_DIR) else self.config.DEFAULT_MODEL

        logger.info(f"🤖 Loading PhoBERT from: {model_path}")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)

        # Load model — use_safetensors=True avoids torch.load CVE-2025-32434 check
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_path,
            num_labels=3,
            ignore_mismatched_sizes=True,
            use_safetensors=True,
        )

        # Setup for inference
        self.model.eval()
        self.model.to(self.config.device)

        # Label mapping — internal 3-class
        self.labels = {0: "SAFE", 1: "TOXIC", 2: "MANIPULATIVE"}
        # Pipeline verdict mapping: translate PhoBERT classes → pipeline verdicts
        self.verdict_map = {
            "SAFE":         "SAFE",
            "TOXIC":        "SUSPICIOUS",
            "MANIPULATIVE": "FAKE_SCAM",
        }
        
        logger.info(f"✅ PhoBERT loaded on {self.config.device}")
        logger.info(f"📝 Labels: {list(self.labels.values())}")
    
    def predict(self, text: str) -> Dict[str, Union[str, float, Dict]]:
        """Single text prediction with comprehensive results"""
        if not TRANSFORMERS_AVAILABLE or self.model is None:
            return self._rule_based_predict(text)
        try:
            # Tokenize input
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=self.config.max_length,
                padding=True
            )

            # Move to device
            inputs = {k: v.to(self.config.device) for k, v in inputs.items()}

            # Run inference
            with torch.no_grad():
                logits = self.model(**inputs).logits
            
            # Calculate probabilities
            probs = torch.softmax(logits, dim=-1).squeeze().tolist()
            pred_id = int(torch.argmax(logits, dim=-1).item())
            
            # Confidence score
            confidence = max(probs)
            
            # Risk assessment
            risk_level = self._assess_risk_level(pred_id, confidence)
            
            raw_pred = self.labels.get(pred_id, "UNKNOWN")
            verdict  = self.verdict_map.get(raw_pred, raw_pred)
            
            return {
                "text": text,
                "prediction":   raw_pred,     # PhoBERT class (SAFE/TOXIC/MANIPULATIVE)
                "verdict":      verdict,       # Pipeline verdict (SAFE/SUSPICIOUS/FAKE_SCAM)
                "confidence":   confidence,
                "probabilities": {self.labels[i]: probs[i] for i in range(len(probs))},
                "risk_level":   risk_level,
                "is_safe":      pred_id == 0,
                "requires_review": pred_id in [1, 2] and confidence < 0.8,
                "model_info": {
                    "model":      self.config.model_name,
                    "max_length": self.config.max_length,
                    "device":     self.config.device
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Prediction failed: {e}")
            return {
                "text": text,
                "prediction": "ERROR",
                "confidence": 0.0,
                "error": str(e),
                "is_safe": False,
                "requires_review": True
            }
    
    def _assess_risk_level(self, pred_id: int, confidence: float) -> str:
        """Assess risk level based on prediction and confidence"""
        if pred_id == 0:  # SAFE
            return "LOW"
        elif pred_id in [1, 2]:  # TOXIC or MANIPULATIVE
            if confidence >= 0.8:
                return "HIGH"
            elif confidence >= 0.6:
                return "MEDIUM"
            else:
                return "LOW"
        else:
            return "UNKNOWN"

    def _rule_based_predict(self, text: str) -> Dict[str, Union[str, float, Dict]]:
        """Keyword-based fallback khi không có torch/transformers (Render free tier).
        Detect scam patterns đặc thù thị trường Việt Nam."""
        t = text.lower()

        # ── FAKE_SCAM signals ─────────────────────────────────────────────
        SCAM_PATTERNS = [
            # Credential harvesting
            "mật khẩu", "password", "pass ", "tài khoản", "đăng nhập", "login",
            "seed phrase", "private key", "otp", "verify acc", "xác nhận acc",
            # Payment pressure
            "nạp thẻ trước", "nạp trước", "chuyển khoản trước", "thanh toán trước",
            "cọc trước", "phí kích hoạt", "phí xác minh",
            # Gaming scams
            "robux miễn phí", "robux free", "free robux", "robux hack",
            "vbucks", "v-bucks", "skin miễn phí", "acc game giá rẻ",
            "nâng cấp acc", "boost acc",
            # Crypto scams
            "airdrop", "connect ví", "metamask", "ví tiền điện tử",
            "nhân x10", "x100 lợi nhuận", "đầu tư sinh lời",
            # Urgency / pressure
            "kẻo hết slot", "còn vài suất", "hết hôm nay", "giới hạn",
            "nhanh tay", "ưu đãi đặc biệt chỉ hôm nay",
            # Info gathering
            "ib mình", "inbox mình", "nhắn tin để nhận", "điền form",
            "đưa tài khoản", "cho mình tài khoản",
        ]

        # ── SUSPICIOUS signals ────────────────────────────────────────────
        SUSPICIOUS_PATTERNS = [
            "miễn phí", "free", "tặng", "giveaway",
            "bán acc", "mua acc", "acc game",
            "kiếm tiền online", "kiếm tiền tại nhà",
            "hoa hồng", "commission", "affiliate",
            "link tải", "click vào đây", "bấm vào link",
            "bit.ly", "tinyurl", "rút gọn link",
        ]

        text_len = len(t.split())
        scam_hits  = [p for p in SCAM_PATTERNS     if p in t]
        susp_hits  = [p for p in SUSPICIOUS_PATTERNS if p in t]

        # Score: mỗi scam keyword +0.18, mỗi suspicious +0.08, cap at 0.97
        scam_score = min(0.97, 0.35 + len(scam_hits) * 0.18)
        susp_score = min(0.85, 0.30 + len(susp_hits) * 0.10)

        if scam_hits:
            prob_fake  = round(scam_score, 3)
            prob_susp  = round(min(0.3, (1 - scam_score) * 0.4), 3)
            prob_safe  = round(max(0.03, 1 - prob_fake - prob_susp), 3)
            prediction = "FAKE_SCAM"
            confidence = prob_fake
            risk_level = "HIGH" if confidence >= 0.7 else "MEDIUM"
            is_safe    = False
        elif susp_hits:
            prob_susp  = round(susp_score, 3)
            prob_fake  = round(min(0.25, susp_score * 0.3), 3)
            prob_safe  = round(max(0.1, 1 - prob_susp - prob_fake), 3)
            prediction = "SUSPICIOUS"
            confidence = prob_susp
            risk_level = "MEDIUM"
            is_safe    = False
        else:
            prob_safe  = 0.82
            prob_susp  = 0.12
            prob_fake  = 0.06
            prediction = "SAFE"
            confidence = prob_safe
            risk_level = "LOW"
            is_safe    = True

        return {
            "text":         text,
            "prediction":   prediction,
            "confidence":   confidence,
            "probabilities": {
                "SAFE":         prob_safe,
                "TOXIC":        prob_susp,
                "MANIPULATIVE": prob_fake,
            },
            "risk_level":      risk_level,
            "is_safe":         is_safe,
            "requires_review": prediction == "SUSPICIOUS",
            "mock":            True,
            "mock_reason":     "rule_based_fallback",
            "matched_patterns": scam_hits or susp_hits,
        }

    def batch_predict(self, texts: List[str]) -> List[Dict]:
        """Batch prediction for efficiency"""
        logger.info(f"📊 Batch processing {len(texts)} texts")
        
        results = []
        
        # Process in batches
        for i in range(0, len(texts), self.config.batch_size):
            batch_texts = texts[i:i + self.config.batch_size]
            
            try:
                # Tokenize batch
                inputs = self.tokenizer(
                    batch_texts,
                    return_tensors="pt",
                    truncation=True,
                    max_length=self.config.max_length,
                    padding=True
                )
                
                # Move to device
                inputs = {k: v.to(self.config.device) for k, v in inputs.items()}
                
                # Run inference
                with torch.no_grad():
                    logits = self.model(**inputs).logits
                
                # Process batch results
                probs = torch.softmax(logits, dim=-1)
                pred_ids = torch.argmax(logits, dim=-1)
                
                for j, text in enumerate(batch_texts):
                    pred_id = pred_ids[j].item()
                    prob_list = probs[j].tolist()
                    confidence = max(prob_list)
                    
                    result = {
                        "text": text,
                        "prediction": self.labels.get(pred_id, "UNKNOWN"),
                        "confidence": confidence,
                        "probabilities": {self.labels[k]: prob_list[k] for k in range(len(prob_list))},
                        "risk_level": self._assess_risk_level(pred_id, confidence),
                        "is_safe": pred_id == 0,
                        "requires_review": pred_id in [1, 2] and confidence < 0.8
                    }
                    
                    results.append(result)
                
                # Progress logging
                if (i + len(batch_texts)) % 50 == 0:
                    logger.info(f"📊 Processed {i + len(batch_texts)}/{len(texts)} texts")
                
            except Exception as e:
                logger.error(f"❌ Batch processing failed: {e}")
                # Add error results for this batch
                for text in batch_texts:
                    results.append({
                        "text": text,
                        "prediction": "ERROR",
                        "confidence": 0.0,
                        "error": str(e),
                        "is_safe": False,
                        "requires_review": True
                    })
        
        logger.info(f"✅ Batch processing completed: {len(results)} results")
        return results
    
    def get_text_features(self, text: str) -> Dict:
        """Extract text features for fusion model"""
        try:
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=self.config.max_length,
                padding=True
            )
            
            inputs = {k: v.to(self.config.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs, output_hidden_states=True)
                
                # Get last hidden state
                hidden_states = outputs.hidden_states[-1]
                
                # Pool to get sentence embedding
                sentence_embedding = hidden_states.mean(dim=1).squeeze().cpu().numpy()
                
                # Get logits for classification features
                logits = outputs.logits.squeeze().cpu().numpy()
                probs = torch.softmax(torch.from_numpy(logits), dim=-1).numpy()
            
            return {
                "text": text,
                "embedding": sentence_embedding.tolist(),
                "classification_logits": logits.tolist(),
                "classification_probs": probs.tolist(),
                "embedding_dim": len(sentence_embedding),
                "feature_extraction_success": True
            }
            
        except Exception as e:
            logger.error(f"❌ Feature extraction failed: {e}")
            return {
                "text": text,
                "embedding": [],
                "classification_logits": [],
                "classification_probs": [],
                "embedding_dim": 0,
                "feature_extraction_success": False,
                "error": str(e)
            }
    
    def convert_to_onnx(self, save_path: Optional[str] = None):
        """Convert model to ONNX for faster inference"""
        if save_path is None:
            save_path = self.config.ONNX_DIR
        
        logger.info("🔄 Converting PhoBERT to ONNX...")
        
        try:
            import torch.onnx
            
            # Create dummy input
            dummy_input = {
                "input_ids": torch.randint(0, 1000, (1, self.config.max_length)),
                "attention_mask": torch.ones(1, self.config.max_length)
            }
            
            # Export to ONNX
            torch.onnx.export(
                self.model,
                (dummy_input["input_ids"], dummy_input["attention_mask"]),
                f"{save_path}/phobert_model.onnx",
                input_names=["input_ids", "attention_mask"],
                output_names=["logits"],
                dynamic_axes={
                    "input_ids": {0: "batch_size", 1: "sequence"},
                    "attention_mask": {0: "batch_size", 1: "sequence"},
                    "logits": {0: "batch_size"}
                },
                opset_version=12
            )
            
            # Save tokenizer
            self.tokenizer.save_pretrained(save_path)
            
            logger.info(f"✅ ONNX model saved to {save_path}")
            
        except Exception as e:
            logger.error(f"❌ ONNX conversion failed: {e}")
            raise
    
    def load_onnx_model(self, onnx_path: Optional[str] = None):
        """Load ONNX model for faster inference"""
        if onnx_path is None:
            onnx_path = self.config.ONNX_DIR
        
        try:
            import onnxruntime as ort
            
            # Load ONNX model
            self.onnx_model = ort.InferenceSession(f"{onnx_path}/phobert_model.onnx")
            
            logger.info("✅ ONNX model loaded successfully")
            logger.info("🚀 Ready for fast CPU inference")
            
        except Exception as e:
            logger.error(f"❌ ONNX loading failed: {e}")
            raise
    
    def predict_onnx(self, text: str) -> Dict:
        """Fast prediction using ONNX model"""
        if self.onnx_model is None:
            logger.warning("⚠️ ONNX model not loaded, falling back to PyTorch")
            return self.predict(text)
        
        try:
            # Tokenize
            inputs = self.tokenizer(
                text,
                return_tensors="np",
                truncation=True,
                max_length=self.config.max_length,
                padding=True
            )
            
            # Run ONNX inference
            outputs = self.onnx_model.run(
                None,
                {
                    "input_ids": inputs["input_ids"],
                    "attention_mask": inputs["attention_mask"]
                }
            )
            
            logits = outputs[0].squeeze()
            probs = self._softmax(logits)
            pred_id = np.argmax(logits)
            
            return {
                "text": text,
                "prediction": self.labels.get(int(pred_id), "UNKNOWN"),
                "confidence": float(max(probs)),
                "probabilities": {self.labels[i]: float(probs[i]) for i in range(len(probs))},
                "inference_engine": "ONNX",
                "is_safe": int(pred_id) == 0
            }
            
        except Exception as e:
            logger.error(f"❌ ONNX prediction failed: {e}")
            return self.predict(text)
    
    def _softmax(self, x):
        """Softmax function"""
        exp_x = np.exp(x - np.max(x))
        return exp_x / exp_x.sum()

if __name__ == "__main__":
    inference = PhoBERTInference()
    test_text = "Nội dung an toàn cho mọi lứa tuổi học sinh"
    result = inference.predict(test_text)
    print("Test inference result:")
    print(result)
