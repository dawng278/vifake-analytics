#!/usr/bin/env python3
"""
Human-in-the-Loop Active Learning System for 2026 Scam Pattern Updates
Tầng 5: Active Learning & MLOps với cập nhật mẫu lừa đảo mới nhất

Tuân thủ Privacy-by-Design:
- 10% dữ liệu từ tài khoản test chính danh
- So sánh mẫu cũ vs mới để tự động điều chỉnh trọng số
- MLflow tracking và model retraining triggers
"""

import os
import sys
import json
import logging
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from pymongo import MongoClient
import mlflow
import mlflow.pytorch
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
import transformers
from transformers import AutoTokenizer, AutoModel
import torch
import torch.nn as nn
from tqdm import tqdm
import requests
from dataclasses import asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LearningMode(Enum):
    """Các chế độ học tập"""
    ACTIVE_LEARNING = "active_learning"
    CONTINUOUS_UPDATE = "continuous_update"
    PATTERN_DRIFT = "pattern_drift"
    HUMAN_FEEDBACK = "human_feedback"

class ReviewStatus(Enum):
    """Trạng thái review"""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    REJECTED = "rejected"

class PatternType(Enum):
    """Loại pattern phát hiện"""
    NEW_KEYWORDS = "new_keywords"
    NEW_SCAM_VARIANT = "new_scam_variant"
    LINGUISTIC_DRIFT = "linguistic_drift"
    PLATFORM_CHANGE = "platform_change"
    TARGET_SHIFT = "target_shift"

@dataclass
class ActiveLearningConfig:
    """Cấu hình cho Active Learning System"""
    mongo_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name: str = "vifake_analytics"
    mlflow_tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")
    
    # Active Learning parameters
    uncertainty_threshold: float = 0.6
    confidence_threshold: float = 0.8
    batch_size: int = 50
    max_queue_size: int = 1000
    
    # 2026 Pattern Detection
    test_account_ratio: float = 0.1  # 10% from test accounts
    pattern_drift_threshold: float = 0.15
    new_keyword_threshold: int = 5
    
    # Model Retraining
    retrain_threshold: int = 100  # Retrain after 100 new labels
    performance_drop_threshold: float = 0.05
    min_improvement_threshold: float = 0.02

class Pattern2026Detector:
    """Phát hiện pattern lừa đảo mới năm 2026"""
    
    def __init__(self, config: ActiveLearningConfig):
        self.config = config
        
        # 2026 specific keywords and patterns
        self.new_keywords_2026 = {
            "ai_generated": ["ai art", "ai image", "deepfake", "ai voice", "ai video"],
            "crypto_scams": ["crypto giveaway", "nft free", "web3 airdrop", "blockchain reward"],
            "gaming_2026": ["roblox 2026", "minecraft mods", "fortnite skins", "gaming crypto"],
            "social_trends": ["tiktok challenge", "instagram trend", "viral hack", "social media award"],
            "tech_scams": ["app beta", "software crack", "vpn premium", "antivirus free"],
            "metaverse": ["metaverse land", "virtual real estate", "meta tokens", "vr items"]
        }
        
        # Emerging scam patterns
        self.emerging_patterns = {
            "ai_impersonation": ["ai celebrity", "voice clone", "deepfake video"],
            "crypto_phishing": ["wallet connect", "meta mask", "private key", "seed phrase"],
            "subscription_traps": ["free trial", "premium access", "vip membership"],
            "social_engineering_2026": ["verify identity", "kyc required", "age verification"]
        }
    
    def detect_new_patterns(self, text: str, existing_keywords: Set[str]) -> Dict[str, any]:
        """Phát hiện pattern mới trong text"""
        text_lower = text.lower()
        detected_patterns = {
            "new_keywords_detected": [],
            "new_patterns_detected": [],
            "is_2026_pattern": False,
            "pattern_drift_score": 0.0,
            "confidence": 0.0
        }
        
        # Check for new keywords
        for category, keywords in self.new_keywords_2026.items():
            for keyword in keywords:
                if keyword in text_lower and keyword not in existing_keywords:
                    detected_patterns["new_keywords_detected"].append({
                        "keyword": keyword,
                        "category": category,
                        "context": self._extract_context(text, keyword)
                    })
                    detected_patterns["is_2026_pattern"] = True
        
        # Check for emerging patterns
        for pattern_type, patterns in self.emerging_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    detected_patterns["new_patterns_detected"].append({
                        "pattern": pattern,
                        "type": pattern_type,
                        "severity": self._calculate_pattern_severity(pattern)
                    })
                    detected_patterns["is_2026_pattern"] = True
        
        # Calculate pattern drift score
        detected_patterns["pattern_drift_score"] = self._calculate_drift_score(
            detected_patterns["new_keywords_detected"],
            detected_patterns["new_patterns_detected"]
        )
        
        # Calculate confidence
        detected_patterns["confidence"] = min(
            detected_patterns["pattern_drift_score"] + 
            len(detected_patterns["new_keywords_detected"]) * 0.1 +
            len(detected_patterns["new_patterns_detected"]) * 0.15,
            1.0
        )
        
        return detected_patterns
    
    def _extract_context(self, text: str, keyword: str, window: int = 20) -> str:
        """Trích xuất context xung quanh keyword"""
        text_lower = text.lower()
        keyword_pos = text_lower.find(keyword.lower())
        
        if keyword_pos == -1:
            return ""
        
        start = max(0, keyword_pos - window)
        end = min(len(text), keyword_pos + len(keyword) + window)
        
        return text[start:end].strip()
    
    def _calculate_pattern_severity(self, pattern: str) -> str:
        """Tính độ nghiêm trọng của pattern"""
        high_severity = ["private key", "seed phrase", "deepfake", "voice clone"]
        medium_severity = ["crypto", "nft", "wallet", "verify"]
        
        pattern_lower = pattern.lower()
        
        if any(term in pattern_lower for term in high_severity):
            return "high"
        elif any(term in pattern_lower for term in medium_severity):
            return "medium"
        else:
            return "low"
    
    def _calculate_drift_score(self, new_keywords: List[Dict], new_patterns: List[Dict]) -> float:
        """Tính điểm drift của pattern"""
        keyword_weight = 0.1
        pattern_weight = 0.15
        
        score = len(new_keywords) * keyword_weight + len(new_patterns) * pattern_weight
        return min(score, 1.0)

class HumanReviewQueue:
    """Hàng đợi review cho con người"""
    
    def __init__(self, config: ActiveLearningConfig):
        self.config = config
        self.mongo_client = None
        self.db = None
        self._init_mongodb()
    
    def _init_mongodb(self):
        """Initialize MongoDB connection"""
        try:
            self.mongo_client = MongoClient(self.config.mongo_uri)
            self.db = self.mongo_client[self.config.db_name]
            logger.info("✅ MongoDB connection established")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
    
    def add_to_review_queue(self, item_data: Dict) -> str:
        """Thêm item vào hàng đợi review"""
        queue_item = {
            "_id": str(uuid.uuid4()),
            "queue_item_id": f"review_{uuid.uuid4().hex[:8]}",
            
            # Item identification
            "item_type": item_data.get("item_type", "conversation"),
            "item_id": item_data.get("item_id"),
            "item_hash": hashlib.sha256(str(item_data).encode()).hexdigest(),
            
            # ML Model Uncertainty
            "model_confidence": item_data.get("model_confidence", 0.0),
            "uncertainty_type": item_data.get("uncertainty_type", "low_confidence"),
            
            # 2026 Pattern Information
            "is_2026_pattern": item_data.get("is_2026_pattern", False),
            "new_keywords_detected": item_data.get("new_keywords_detected", []),
            "new_patterns_detected": item_data.get("new_patterns_detected", []),
            "pattern_drift_score": item_data.get("pattern_drift_score", 0.0),
            
            # Human Review Priority
            "priority_score": self._calculate_priority_score(item_data),
            "review_reason": item_data.get("review_reason", "model_uncertainty"),
            
            # Review Assignment
            "assigned_reviewer": None,
            "review_deadline": datetime.utcnow() + timedelta(hours=24),
            "review_status": ReviewStatus.PENDING.value,
            
            # Review Outcome
            "human_label": None,
            "human_confidence": 0.0,
            "reviewer_notes": "",
            
            # Model Update Impact
            "used_in_retraining": False,
            "performance_impact": 0.0,
            
            # Metadata
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        try:
            # Insert into MongoDB
            collection = self.db.active_learning_queue
            result = collection.insert_one(queue_item)
            
            logger.info(f"✅ Added item {queue_item['queue_item_id']} to review queue")
            return queue_item["queue_item_id"]
            
        except Exception as e:
            logger.error(f"❌ Failed to add item to review queue: {e}")
            raise
    
    def _calculate_priority_score(self, item_data: Dict) -> float:
        """Tính điểm ưu tiên cho review"""
        score = 0.0
        
        # Low model confidence increases priority
        model_confidence = item_data.get("model_confidence", 1.0)
        if model_confidence < self.config.uncertainty_threshold:
            score += 0.4
        
        # 2026 patterns increase priority
        if item_data.get("is_2026_pattern", False):
            score += 0.3
        
        # Pattern drift increases priority
        drift_score = item_data.get("pattern_drift_score", 0.0)
        score += drift_score * 0.2
        
        # New keywords increase priority
        new_keywords = item_data.get("new_keywords_detected", [])
        score += len(new_keywords) * 0.05
        
        return min(score, 1.0)
    
    def get_review_batch(self, batch_size: int = None) -> List[Dict]:
        """Lấy batch items để review"""
        if batch_size is None:
            batch_size = self.config.batch_size
        
        try:
            collection = self.db.active_learning_queue
            
            # Get high priority pending items
            cursor = collection.find({
                "review_status": ReviewStatus.PENDING.value
            }).sort("priority_score", -1).limit(batch_size)
            
            items = list(cursor)
            
            # Mark as in_review
            item_ids = [item["_id"] for item in items]
            collection.update_many(
                {"_id": {"$in": item_ids}},
                {
                    "$set": {
                        "review_status": ReviewStatus.IN_REVIEW.value,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"📋 Retrieved {len(items)} items for review")
            return items
            
        except Exception as e:
            logger.error(f"❌ Failed to get review batch: {e}")
            raise
    
    def submit_review(self, queue_item_id: str, review_data: Dict) -> bool:
        """Nộp kết quả review"""
        try:
            collection = self.db.active_learning_queue
            
            # Update item with review results
            update_data = {
                "review_status": ReviewStatus.COMPLETED.value,
                "human_label": review_data.get("human_label"),
                "human_confidence": review_data.get("human_confidence", 0.0),
                "reviewer_notes": review_data.get("reviewer_notes", ""),
                "reviewed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = collection.update_one(
                {"queue_item_id": queue_item_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ Review submitted for {queue_item_id}")
                return True
            else:
                logger.warning(f"⚠️ No item found with ID {queue_item_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to submit review: {e}")
            return False
    
    def get_retraining_candidates(self) -> List[Dict]:
        """Lấy các items đã review để retraining"""
        try:
            collection = self.db.active_learning_queue
            
            # Get completed reviews not used in retraining
            cursor = collection.find({
                "review_status": ReviewStatus.COMPLETED.value,
                "used_in_retraining": False,
                "human_confidence": {"$gte": 0.7}  # High confidence human labels
            })
            
            candidates = list(cursor)
            logger.info(f"📊 Found {len(candidates)} retraining candidates")
            return candidates
            
        except Exception as e:
            logger.error(f"❌ Failed to get retraining candidates: {e}")
            return []

class ModelRetrainingEngine:
    """Engine retraining model với active learning"""
    
    def __init__(self, config: ActiveLearningConfig):
        self.config = config
        self.review_queue = HumanReviewQueue(config)
        self.pattern_detector = Pattern2026Detector(config)
        
        # Initialize MLflow
        mlflow.set_tracking_uri(config.mlflow_tracking_uri)
        mlflow.set_experiment("vifake-active-learning-2026")
        
        # Model components
        self.tokenizer = None
        self.model = None
        self.vectorizer = TfidfVectorizer(max_features=10000)
        
        self._load_base_model()
    
    def _load_base_model(self):
        """Load base PhoBERT model"""
        try:
            model_name = "vinai/phobert-base"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            
            logger.info("✅ Base PhoBERT model loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load base model: {e}")
            # Fallback to simple model
            logger.info("🔄 Using fallback model architecture")
    
    def check_retraining_trigger(self) -> bool:
        """Kiểm tra xem có cần retraining không"""
        candidates = self.review_queue.get_retraining_candidates()
        
        # Check if we have enough new labels
        if len(candidates) >= self.config.retrain_threshold:
            logger.info(f"🔄 Retraining triggered: {len(candidates)} new labels available")
            return True
        
        # Check for significant pattern drift
        pattern_drift_items = [
            item for item in candidates 
            if item.get("pattern_drift_score", 0) > self.config.pattern_drift_threshold
        ]
        
        if len(pattern_drift_items) >= 20:  # 20 items with significant drift
            logger.info(f"🔄 Retraining triggered: {len(pattern_drift_items)} pattern drift items")
            return True
        
        return False
    
    def prepare_training_data(self, retraining_candidates: List[Dict]) -> Tuple[List[str], List[int]]:
        """Chuẩn bị dữ liệu training từ candidates"""
        texts = []
        labels = []
        
        for candidate in retraining_candidates:
            # Extract text from candidate
            item_type = candidate.get("item_type", "conversation")
            
            if item_type == "conversation":
                # Handle conversation data
                conversation_data = candidate.get("conversation", {})
                if isinstance(conversation_data, str):
                    text = conversation_data
                else:
                    # Extract from conversation turns
                    text = " ".join([
                        turn.get("text", "") 
                        for turn in conversation_data.get("conversation", [])
                        if turn.get("role") == "scammer"
                    ])
            else:
                text = candidate.get("text", "")
            
            if text:
                texts.append(text)
                # Convert human label to binary (1=scam, 0=legitimate)
                human_label = candidate.get("human_label", "legitimate")
                label = 1 if human_label.lower() in ["scam", "malicious", "harmful"] else 0
                labels.append(label)
        
        logger.info(f"📊 Prepared {len(texts)} training samples")
        return texts, labels
    
    def calculate_performance_improvement(self, old_metrics: Dict, new_metrics: Dict) -> float:
        """Tính độ cải thiện performance"""
        improvements = []
        
        for metric in ["accuracy", "precision", "recall", "f1_score"]:
            old_val = old_metrics.get(metric, 0)
            new_val = new_metrics.get(metric, 0)
            improvement = (new_val - old_val) / max(old_val, 0.001)
            improvements.append(improvement)
        
        avg_improvement = np.mean(improvements)
        return avg_improvement
    
    def run_retraining_pipeline(self):
        """Chạy complete retraining pipeline"""
        logger.info("🚀 Starting model retraining pipeline...")
        
        with mlflow.start_run(run_name=f"active-learning-retrain-{datetime.now().strftime('%Y%m%d-%H%M%S')}") as run:
            try:
                # Get retraining candidates
                candidates = self.review_queue.get_retraining_candidates()
                
                if not candidates:
                    logger.info("ℹ️ No retraining candidates available")
                    return
                
                # Prepare training data
                texts, labels = self.prepare_training_data(candidates)
                
                if len(texts) < 10:  # Minimum samples for training
                    logger.warning("⚠️ Insufficient training samples")
                    return
                
                # Split data
                X_train, X_val, y_train, y_val = train_test_split(
                    texts, labels, test_size=0.2, random_state=42, stratify=labels
                )
                
                # Feature extraction
                X_train_features = self.vectorizer.fit_transform(X_train)
                X_val_features = self.vectorizer.transform(X_val)
                
                # Train simple model (placeholder for actual training)
                from sklearn.linear_model import LogisticRegression
                model = LogisticRegression(random_state=42)
                model.fit(X_train_features, y_train)
                
                # Evaluate
                y_pred = model.predict(X_val_features)
                new_metrics = {
                    "accuracy": accuracy_score(y_val, y_pred),
                    "precision": precision_score(y_val, y_pred, average='weighted'),
                    "recall": recall_score(y_val, y_pred, average='weighted'),
                    "f1_score": f1_score(y_val, y_pred, average='weighted')
                }
                
                # Log metrics to MLflow
                for metric, value in new_metrics.items():
                    mlflow.log_metric(metric, value)
                
                mlflow.log_param("training_samples", len(X_train))
                mlflow.log_param("validation_samples", len(X_val))
                mlflow.log_param("new_patterns_2026", 
                               sum(1 for c in candidates if c.get("is_2026_pattern", False)))
                
                # Log model
                mlflow.sklearn.log_model(model, "model")
                
                # Update candidates as used in retraining
                candidate_ids = [c["_id"] for c in candidates]
                self.review_queue.db.active_learning_queue.update_many(
                    {"_id": {"$in": candidate_ids}},
                    {"$set": {
                        "used_in_retraining": True,
                        "performance_impact": new_metrics["f1_score"],
                        "updated_at": datetime.utcnow()
                    }}
                )
                
                logger.info("✅ Model retraining completed successfully!")
                logger.info(f"📊 New F1 Score: {new_metrics['f1_score']:.3f}")
                
            except Exception as e:
                logger.error(f"❌ Retraining pipeline failed: {e}")
                mlflow.log_param("error", str(e))
                raise

class ActiveLearningSystem:
    """Main Active Learning System"""
    
    def __init__(self, config: ActiveLearningConfig):
        self.config = config
        self.pattern_detector = Pattern2026Detector(config)
        self.review_queue = HumanReviewQueue(config)
        self.retraining_engine = ModelRetrainingEngine(config)
        
        # Existing keywords for comparison
        self.existing_keywords = set()
        self._load_existing_keywords()
    
    def _load_existing_keywords(self):
        """Load existing keywords from database"""
        try:
            client = MongoClient(self.config.mongo_uri)
            db = client[self.config.db_name]
            
            # Load from posts collection
            posts = db.posts_collection.find({}, {"detected_keywords": 1})
            for post in posts:
                keywords = post.get("detected_keywords", [])
                self.existing_keywords.update(keywords)
            
            logger.info(f"✅ Loaded {len(self.existing_keywords)} existing keywords")
            client.close()
            
        except Exception as e:
            logger.error(f"❌ Failed to load existing keywords: {e}")
    
    def process_new_data(self, data_items: List[Dict]) -> List[str]:
        """Xử lý data mới và thêm vào review queue nếu cần"""
        queue_item_ids = []
        
        for item in data_items:
            # Extract text for analysis
            text = self._extract_text_from_item(item)
            if not text:
                continue
            
            # Detect 2026 patterns
            pattern_analysis = self.pattern_detector.detect_new_patterns(text, self.existing_keywords)
            
            # Determine if review is needed
            needs_review = self._should_review_item(item, pattern_analysis)
            
            if needs_review:
                # Prepare queue item data
                queue_data = {
                    "item_type": item.get("type", "text"),
                    "item_id": item.get("id", str(uuid.uuid4())),
                    "text": text,
                    "conversation": item.get("conversation", {}),
                    "model_confidence": item.get("confidence", 0.0),
                    "uncertainty_type": item.get("uncertainty_type", "low_confidence"),
                    **pattern_analysis
                }
                
                # Add to review queue
                queue_id = self.review_queue.add_to_review_queue(queue_data)
                queue_item_ids.append(queue_id)
                
                # Update existing keywords with new ones
                for keyword_info in pattern_analysis["new_keywords_detected"]:
                    self.existing_keywords.add(keyword_info["keyword"])
        
        logger.info(f"📋 Added {len(queue_item_ids)} items to review queue")
        return queue_item_ids
    
    def _extract_text_from_item(self, item: Dict) -> str:
        """Trích xuất text từ item"""
        if "text" in item:
            return item["text"]
        elif "conversation" in item:
            conversation = item["conversation"]
            if isinstance(conversation, dict) and "conversation" in conversation:
                # Extract from conversation turns
                texts = []
                for turn in conversation["conversation"]:
                    if isinstance(turn, dict) and "text" in turn:
                        texts.append(turn["text"])
                return " ".join(texts)
            elif isinstance(conversation, list):
                return " ".join([str(turn) for turn in conversation])
        return ""
    
    def _should_review_item(self, item: Dict, pattern_analysis: Dict) -> bool:
        """Quyết định xem item có cần review không"""
        # Low model confidence
        if item.get("confidence", 1.0) < self.config.uncertainty_threshold:
            return True
        
        # 2026 pattern detected
        if pattern_analysis["is_2026_pattern"]:
            return True
        
        # Significant pattern drift
        if pattern_analysis["pattern_drift_score"] > self.config.pattern_drift_threshold:
            return True
        
        # High uncertainty type
        if item.get("uncertainty_type") in ["high_entropy", "disagreement"]:
            return True
        
        return False
    
    def run_active_learning_cycle(self):
        """Chạy một chu kỳ active learning hoàn chỉnh"""
        logger.info("🔄 Starting active learning cycle...")
        
        try:
            # Step 1: Check if retraining is needed
            if self.retraining_engine.check_retraining_trigger():
                logger.info("🔄 Triggering model retraining...")
                self.retraining_engine.run_retraining_pipeline()
            else:
                logger.info("ℹ️ No retraining needed at this time")
            
            # Step 2: Process any pending test account data (10% rule)
            self._process_test_account_data()
            
            # Step 3: Update model weights based on new patterns
            self._update_model_weights()
            
            logger.info("✅ Active learning cycle completed")
            
        except Exception as e:
            logger.error(f"❌ Active learning cycle failed: {e}")
            raise
    
    def _process_test_account_data(self):
        """Xử lý dữ liệu từ tài khoản test (10%)"""
        logger.info("📊 Processing test account data...")
        
        try:
            # In a real implementation, this would connect to test account APIs
            # For now, simulate with synthetic test data
            test_data_count = int(100 * self.config.test_account_ratio)  # 10 items
            
            for i in range(test_data_count):
                # Simulate test account data
                test_item = {
                    "id": f"test_{i}",
                    "type": "conversation",
                    "confidence": random.uniform(0.3, 0.9),
                    "uncertainty_type": random.choice(["low_confidence", "high_entropy"]),
                    "text": f"Test data item {i} with potential 2026 patterns",
                    "conversation": {
                        "conversation": [
                            {"role": "scammer", "text": "Check out this new crypto giveaway!"},
                            {"role": "victim", "text": "Is this legit?"}
                        ]
                    }
                }
                
                # Process through active learning
                self.process_new_data([test_item])
            
            logger.info(f"✅ Processed {test_data_count} test account items")
            
        except Exception as e:
            logger.error(f"❌ Failed to process test account data: {e}")
    
    def _update_model_weights(self):
        """Cập nhật trọng số model dựa trên pattern mới"""
        logger.info("⚖️ Updating model weights based on new patterns...")
        
        try:
            # Get recent 2026 patterns
            recent_patterns = self.review_queue.db.active_learning_queue.find({
                "is_2026_pattern": True,
                "review_status": ReviewStatus.COMPLETED.value,
                "reviewed_at": {"$gte": datetime.utcnow() - timedelta(days=7)}
            })
            
            pattern_weights = {}
            for pattern in recent_patterns:
                # Extract new keywords and patterns
                new_keywords = pattern.get("new_keywords_detected", [])
                new_patterns = pattern.get("new_patterns_detected", [])
                
                # Calculate weights based on human confidence
                human_confidence = pattern.get("human_confidence", 0.0)
                
                for keyword_info in new_keywords:
                    keyword = keyword_info["keyword"]
                    pattern_weights[keyword] = pattern_weights.get(keyword, 0) + human_confidence
                
                for pattern_info in new_patterns:
                    pattern = pattern_info["pattern"]
                    pattern_weights[pattern] = pattern_weights.get(pattern, 0) + human_confidence
            
            # Normalize weights
            max_weight = max(pattern_weights.values()) if pattern_weights else 1.0
            normalized_weights = {
                k: v / max_weight for k, v in pattern_weights.items()
            }
            
            # Save updated weights
            weights_collection = self.review_queue.db.pattern_weights_collection
            weights_collection.update_one(
                {"model_version": "latest"},
                {"$set": {
                    "weights": normalized_weights,
                    "updated_at": datetime.utcnow(),
                    "total_patterns": len(normalized_weights)
                }},
                upsert=True
            )
            
            logger.info(f"✅ Updated weights for {len(normalized_weights)} patterns")
            
        except Exception as e:
            logger.error(f"❌ Failed to update model weights: {e}")

def main():
    """Main execution function"""
    logger.info("🚀 Starting ViFake Human-in-the-Loop Active Learning System")
    logger.info("🎯 Purpose: 2026 scam pattern updates with 10% test account integration")
    logger.info("🔧 Technology: MLflow + MongoDB + Active Learning")
    logger.info("🔒 Compliance: Limited test data usage + Human oversight")
    
    # Initialize system
    config = ActiveLearningConfig()
    active_learning = ActiveLearningSystem(config)
    
    try:
        # Run active learning cycle
        active_learning.run_active_learning_cycle()
        
        logger.info("🎉 Active Learning System completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Active Learning System failed: {e}")
        raise

if __name__ == "__main__":
    main()
