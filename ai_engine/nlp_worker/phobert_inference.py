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

try:
    from ai_engine.nlp_worker.teencode_normalizer import normalize as _normalize_teencode, contains_high_risk_teencode
    _TEENCODE_AVAILABLE = True
except ImportError:
    try:
        from teencode_normalizer import normalize as _normalize_teencode, contains_high_risk_teencode
        _TEENCODE_AVAILABLE = True
    except ImportError:
        _TEENCODE_AVAILABLE = False
        def _normalize_teencode(t): return t
        def contains_high_risk_teencode(t): return False

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
        # Normalize teen-code before pattern matching
        has_high_risk_teencode = contains_high_risk_teencode(text)
        text = _normalize_teencode(text)
        t = text.lower()

        # ── FAKE_SCAM signals ─────────────────────────────────────────────
        SCAM_PATTERNS = [
            # Credential harvesting
            "mật khẩu", "password", "pass ", "tài khoản", "đăng nhập", "login",
            "seed phrase", "private key", "otp", "verify acc", "xác nhận acc",
            # Payment pressure
            "nạp thẻ trước", "nạp trước", "chuyển khoản trước", "thanh toán trước",
            "cọc trước", "phí kích hoạt", "phí xác minh",
            # Gaming scams — Roblox / Robux (English + Vietnamese + mixed)
            "robux miễn phí", "robux free", "free robux", "robux hack",
            "unlock robux", "get robux", "earn robux", "robux generator",
            "robux secret", "secret robux", "robux method", "robux cheat",
            "how to get robux", "how to unlock robux",
            "roblox hack", "roblox cheat", "roblox glitch",
            "vbucks", "v-bucks", "free vbucks", "vbucks generator",
            "skin miễn phí", "free skin", "skin hack",
            "nâng cấp acc", "boost acc",
            # Gaming scams — Free Fire (kim cương, elite pass)
            "kim cương miễn phí", "free kim cương", "kim cương free",
            "hack kim cương", "kim cương hack", "kim cương generator",
            "free fire hack", "free fire cheat", "free fire mod",
            "hack ff", "mod ff", "hack free fire",
            "elite pass miễn phí", "free elite pass", "elite pass free",
            "hack elite pass", "bundle miễn phí", "free bundle",
            "tool hack free fire", "apk mod free fire",
            "nhận kim cương", "tặng kim cương",
            # Gaming scams — Liên Quân Mobile (quân huy, tướng, ngọc)
            "hack liên quân", "liên quân hack", "mod liên quân",
            "hack quân huy", "quân huy miễn phí", "free quân huy",
            "quân huy hack", "quân huy generator",
            "hack tướng", "tướng miễn phí", "free tướng", "unlock tướng",
            "hack ngọc", "ngọc miễn phí", "free ngọc",
            "tool hack liên quân", "mod lq", "hack lq",
            "tặng quân huy", "nhận quân huy",
            # Gaming scams — PUBG Mobile (UC, RP, BP)
            "hack uc", "uc miễn phí", "free uc", "uc free",
            "uc hack", "uc generator", "uc pubg hack",
            "hack pubg", "pubg hack", "pubg cheat", "pubg mod",
            "hack royale pass", "royale pass miễn phí", "free royale pass",
            "tool hack pubg", "mod pubg", "apk mod pubg",
            "tặng uc", "nhận uc",
            # Generic "secret method" / "new method" in gaming context
            "secret method", "new secret", "new method hack",
            "free coins", "free gems", "unlimited coins", "unlimited gems",
            "coin generator", "gem generator", "diamond hack",
            "tool hack", "apk mod", "mod apk",
            # Crypto scams
            "airdrop", "connect ví", "metamask", "ví tiền điện tử",
            "nhân x10", "x100 lợi nhuận", "đầu tư sinh lời",
            # Urgency / pressure
            "kẻo hết slot", "còn vài suất", "hết hôm nay", "giới hạn",
            "nhanh tay", "ưu đãi đặc biệt chỉ hôm nay",
            # Info gathering
            "ib mình", "inbox mình", "nhắn tin để nhận", "điền form",
            "đưa tài khoản", "cho mình tài khoản",
            # Gaming doubling / trade scam (trẻ em bị lừa #1)
            "đưa robux", "gửi robux", "chuyển robux", "trade robux",
            "đổi robux", "mượn robux", "cho robux",
            "đưa skin", "gửi skin", "trade skin", "đổi skin",
            "đưa gem", "gửi gem", "đưa coin", "gửi coin",
            "đưa diamond", "đưa kim cương", "gửi kim cương",
            "nhân đôi robux", "x2 robux", "doubling robux",
            "nhân đôi skin", "nhân đôi gem", "nhân đôi coin",
            "nhân đôi kim cương", "x2 kim cương", "x2 uc",
            "nhân đôi uc", "nhân đôi quân huy", "x2 quân huy",
            "đưa uc", "gửi uc", "trade uc", "đổi uc",
            "đưa quân huy", "gửi quân huy", "trade quân huy",
            "đưa tướng", "cho tướng", "trade tướng",
            # Account takeover / lending scam
            "cho mình acc", "cho mượn acc", "đưa acc",
            "cho mình nick", "cho mượn nick", "đưa nick",
            "đăng nhập acc để", "login acc để",
            "cho mình tài khoản để", "cho mượn tài khoản",
            "đưa tài khoản để",
            # Cookie logger / code injection
            "nhập code vào", "nhập code này",
            "paste code", "dán code vào",
            "nhập vào trình duyệt", "nhập vào browser",
            "nhập vào console", "paste vào console",
            "editthiscookie", "roblox cookie",
            "cookie logger",
            # Fake middleman / trust manipulation
            "trung gian trade", "mình sẽ trung gian",
            "test acc cho", "fix acc cho", "nâng cấp acc cho",
            "sửa acc", "boost acc cho",
            "đảm bảo không scam", "không lừa đâu",
            "mình thề", "trust me", "no scam", "100% legit",
            # Item lending scam
            "cho mượn skin", "cho mượn item",
            "mượn thử", "cho mượn thử",
            "trả lại sau", "sẽ trả lại",
            "đưa để test", "cho để kiểm tra",
        ]

        # ── SUSPICIOUS signals ────────────────────────────────────────────
        SUSPICIOUS_PATTERNS = [
            "miễn phí", "free", "tặng", "giveaway",
            "bán acc", "mua acc", "acc game", "acc game giá rẻ",
            "kiếm tiền online", "kiếm tiền tại nhà",
            "hoa hồng", "commission", "affiliate",
            "link tải", "click vào đây", "bấm vào link",
            "bit.ly", "tinyurl", "rút gọn link",
        ]

        text_len = len(t.split())
        scam_hits  = [p for p in SCAM_PATTERNS     if p in t]
        susp_hits  = [p for p in SUSPICIOUS_PATTERNS if p in t]

        # === Semantic gaming context detection (catches patterns keyword matching misses) ===
        # E.g. "đưa tôi 1000 robux để nhận 1000000 robux" — words in between break exact match
        import re as _re
        GAME_ITEMS_RB = ['robux', 'roblox', 'skin', 'gem', 'coin', 'diamond', 'kim cương',
                         'vbucks', 'v-bucks', 'gamepass', 'item', 'pet',
                         # Free Fire
                         'free fire', 'freefire', 'garena', 'elite pass', 'bundle',
                         # Liên Quân
                         'liên quân', 'lien quan', 'quân huy', 'tướng', 'ngọc',
                         # PUBG
                         'pubg', 'royale pass',
                         # In-game currencies
                         ' uc', 'uc ', ' bp', ' rp', ' kc']
        ACTION_WORDS_RB = ['đưa', 'gửi', 'cho', 'trade', 'chuyển', 'nhập', 'đổi',
                           'trao', 'bỏ', 'nạp', 'mượn', 'transfer', 'swap', 'drop']
        RECEIVE_WORDS_RB = ['nhận', 'lấy', 'được', 'trả', 'unlock', 'hoàn']
        SCAM_TRIGGERS_RB = ['hack', 'cheat', 'generator', 'mod ', 'tool ', 'vô hạn', 'bẻ khóa']

        has_game_item = any(g in t for g in GAME_ITEMS_RB)
        has_action_word = any(a in t for a in ACTION_WORDS_RB)
        has_receive_word = any(r in t for r in RECEIVE_WORDS_RB)
        has_scam_trigger = any(s in t for s in SCAM_TRIGGERS_RB)

        # Educational/review context suppresses gaming scam signals
        SAFE_GAMING_CONTEXT = ['hướng dẫn', 'review', 'đánh giá', 'cách chơi',
                               'mẹo chơi', 'thủ thuật chơi', 'update', 'cập nhật',
                               'thi đấu', 'giải đấu', 'livestream', 'cho người mới',
                               'tutorial', 'beginner', 'tips', 'guide',
                               'highlight', 'gameplay', 'montage', 'rank',
                               'leo rank', 'bảng xếp hạng', 'chiến thuật',
                               'meta', 'tier list', 'top tướng', 'combo']
        is_educational = any(s in t for s in SAFE_GAMING_CONTEXT)

        if has_game_item and has_scam_trigger and not scam_hits:
            # Major fix: Game item + hacking keyword = SCAM automatically
            scam_hits.append('SEMANTIC:gaming_hack_tool')
        elif has_game_item and has_action_word and has_receive_word and not scam_hits and not is_educational:
            # Semantic doubling pattern: game item + give + receive = scam
            scam_hits.append('SEMANTIC:gaming_give_receive')
        elif has_game_item and has_action_word and not scam_hits and not is_educational:
            # Game item + action = at least suspicious (but NOT if educational)
            susp_hits.append('SEMANTIC:gaming_action')

        # Number ratio detection: "1000 robux ... 1000000 robux" → ratio 1000:1
        if has_game_item:
            numbers = [int(n) for n in _re.findall(r'\d+', text) if 2 <= len(n) <= 10]
            if len(numbers) >= 2:
                numbers.sort()
                ratio = numbers[-1] / max(numbers[0], 1)
                if ratio >= 30 and not scam_hits:  # 30x+ raw number ratio with gaming = fallback scam trigger
                    scam_hits.append(f'SEMANTIC:number_ratio_x{ratio:.0f}')

        # --- NEW: Specific Market Price Anomaly check ---
        # E.g. 10k VND = 10,000 Robux (1000x real rate)
        price_pattern = r'(\d+[\.,]?\d*)\s*(k|vnd|đ|đồng)'
        item_pattern = r'(\d+[\.,]?\d*)\s*(robux|rbx|kim cương|kc|quân huy|qh|uc)'
        
        found_prices = list(_re.finditer(price_pattern, t))
        found_items = list(_re.finditer(item_pattern, t))
        
        if found_prices and found_items:
            price_limits = {'robux': 40, 'rbx': 40, 'kc': 100, 'kim cương': 100, 'qh': 50, 'quân huy': 50, 'uc': 50}
            for mp in found_prices:
                for mi in found_items:
                    # If they are within 60 characters of each other in the text
                    if abs(mp.start() - mi.start()) < 60:
                        try:
                            # Extract price
                            p_val = float(mp.group(1).replace('.','').replace(',',''))
                            if mp.group(2) == 'k': p_val *= 1000
                            
                            # Extract item quantity
                            i_val = float(mi.group(1).replace('.','').replace(',',''))
                            i_type = mi.group(2).strip()
                            
                            if p_val > 0 and i_val > 0:
                                money_units = p_val / 1000 # Per 1k VND
                                market_ratio = i_val / money_units
                                
                                # Determine limit based on item type
                                current_limit = price_limits.get(i_type, 50)
                                if market_ratio > current_limit:
                                    scam_hits.append(f'SEMANTIC:price_anomaly_{i_type}_ratio{market_ratio:.0f}')
                                    break # Found one, good enough
                        except: pass


        # Boost score when raw teen-code password/account keywords were found
        teencode_boost = 0.10 if has_high_risk_teencode else 0.0

        # Score: mỗi scam keyword +0.18, mỗi suspicious +0.08, cap at 0.97
        scam_score = min(0.97, 0.35 + len(scam_hits) * 0.18 + teencode_boost)
        susp_score = min(0.85, 0.30 + len(susp_hits) * 0.10)

        if scam_hits:
            prob_fake  = round(scam_score, 3)
            prob_susp  = round(min(0.3, (1 - scam_score) * 0.4), 3)
            prob_safe  = round(max(0.03, 1 - prob_fake - prob_susp), 3)
            prediction = "FAKE_SCAM"
            confidence = prob_fake
            risk_level = "HIGH" if confidence >= 0.7 else "MEDIUM"
            is_safe    = False
        elif susp_hits and not is_educational:
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
                "SAFE":       prob_safe,
                "SUSPICIOUS": prob_susp,
                "FAKE_SCAM":  prob_fake,
            },
            "risk_level":      risk_level,
            "is_safe":         is_safe,
            "requires_review": prediction != "SAFE",
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
