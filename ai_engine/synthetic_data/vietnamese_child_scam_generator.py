#!/usr/bin/env python3
"""
Synthetic Data Generation - Vietnamese Child Scam Scenarios
Đóng vai chuyên gia ngôn ngữ học và an ninh mạng tạo dữ liệu giả lập

Tuân thủ Privacy-by-Design:
- 100% dữ liệu tổng hợp, không vi phạm quyền riêng tư
- Tiếng Việt với Teencode và từ lóng Gen Alpha
- Định dạng JSON cho PhoBERT training
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
from enum import Enum
import pymongo
from pymongo import MongoClient
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ScamScenario(Enum):
    """Các kịch bản lừa đảo đặc thù trẻ em Việt Nam"""
    ROBUX_PHISHING = "robux_phishing"
    GAMING_ACCOUNT_THEFT = "gaming_account_theft"
    GIFT_CARD_SCAM = "gift_card_scam"
    FAKE_GIVEAWAY = "fake_giveaway"
    CELEBRITY_IMPERSONATION = "celebrity_impersonation"
    MALICIOUS_LINK_CLICK = "malicious_link_click"
    OTP_THEFT = "otp_theft"
    PARENT_ACCOUNT_ACCESS = "parent_account_access"

class AgeGroup(Enum):
    """Nhóm tuổi mục tiêu"""
    CHILD_8_10 = "8-10"
    CHILD_11_13 = "11-13"
    TEEN_14_17 = "14-17"

@dataclass
class SyntheticConfig:
    """Cấu hình tạo dữ liệu tổng hợp"""
    mongo_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name: str = "vifake_analytics"
    output_file: str = "data/synthetic/vietnamese_child_scams.json"
    num_samples: int = 500
    min_conversation_turns: int = 3
    max_conversation_turns: int = 8

class VietnameseLanguageModel:
    """Mô hình ngôn ngữ tiếng Việt cho trẻ em"""
    
    # Teencode và từ lóng Gen Alpha 2026
    TEENCODE_DICT = {
        "skibidi": ["bizar", "lạ lùng", "kỳ quặc"],
        "rizz": ["charming", "hấp dẫn", "duyên"], 
        "sigma": ["ngầu", "chất", "pro"],
        "based": ["đỉnh", "hay", "chuẩn"],
        "cap": ["hạn chế", "giới hạn"],
        "goated": ["vô địch", "tuyệt vời"],
        "slay": ["làm tốt", "chinh phục"],
        "vibe": ["cảm giác", "không khí"],
        "bet": ["chắc chắn", "đúng vậy"],
        "no cap": ["không nói dối", "thật"],
        "ghost": ["biến mất", "lặn"],
        "simp": ["tán", "thích"],
        "clap": ["tuyệt", "đỉnh"],
        "pog": ["tuyệt vời", "chấn động"]
    }
    
    # Từ lóng game và Roblox
    GAMING_SLANG = {
        "robux": ["tiền game", "xu roblox"],
        "free robux": ["robux miễn phí", "robux free"],
        "nạp": ["nạp tiền", "add tiền"],
        "acc": ["account", "tài khoản"],
        "pass": ["password", "mật khẩu"],
        "otp": ["mã xác thực", "mã otp"],
        "link": ["đường link", "url"],
        "click": ["nhấp vào", "bấm vào"],
        "verify": ["xác nhận", "xác thực"],
        "hack": ["hack", "tool hack"],
        "mod": ["mod game", "cheat"]
    }
    
    # Cụm từ lừa đảo phổ biến
    SCAM_PHRASES = [
        "free robux 2026",
        "nạp robux free 100%",
        "gift card miễn phí",
        "robux giveaway",
        "click link nhận quà",
        "verify account ngay",
        "mã otp để nhận quà",
        "password để nhận robux",
        "admin roblox tặng robux",
        "event giới hạn 24h"
    ]

class SyntheticDataGenerator:
    """Tạo dữ liệu giả lập hội thoại lừa đảo tiếng Việt"""
    
    def __init__(self, config: SyntheticConfig):
        self.config = config
        self.lang_model = VietnameseLanguageModel()
        self.mongo_client = None
        self.db = None
        
        # Initialize MongoDB
        self._init_mongodb()
        
        # Scenario templates
        self.scenario_templates = self._init_scenario_templates()
    
    def _init_mongodb(self):
        """Initialize MongoDB connection"""
        try:
            self.mongo_client = MongoClient(self.config.mongo_uri)
            self.db = self.mongo_client[self.config.db_name]
            logger.info("✅ MongoDB connection established")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
    
    def _init_scenario_templates(self) -> Dict[ScamScenario, List[Dict]]:
        """Khởi tạo template cho từng kịch bản lừa đảo"""
        templates = {
            ScamScenario.ROBUX_PHISHING: [
                {
                    "scammer_opening": [
                        "ae {name} ơi, admin roblox đang event free robux nè!",
                        "hello {name}, t có 10,000 robux free cho newbie nè",
                        "yo {name}, m biết cách get robux free không?",
                        "{name} ơi, t vừa nhận được 50k robux free, muốn không?"
                    ],
                    "victim_responses": [
                        "thật á? sao get vậy bác?",
                        "free á? t tin được không?",
                        "chắc thật chứ? có lừa không?",
                        "wow, t muốn lắm! chỉ t với"
                    ],
                    "scammer_pressure": [
                        "click vào link này: {fake_link} , chỉ cần verify acc thôi",
                        "nhập password roblox vào đây {fake_link} để nhận robux",
                        "admin cần verify acc, vào link này {fake_link} nha",
                        "nhanh lên, event chỉ 24h thôi! {fake_link}"
                    ],
                    "victim_compliance": [
                        "ok t đang click",
                        "password của t là {fake_password}",
                        "t đã verify xong rồi",
                        "sao chưa thấy robux nhỉ?"
                    ]
                }
            ],
            
            ScamScenario.GIFT_CARD_SCAM: [
                {
                    "scammer_opening": [
                        "{name} ơi, t có gift card 500k free nè",
                        "hello, t đang giveaway iTunes card 1000k",
                        "ae ơi, event tặng gift card cho 100 người đầu tiên",
                        "{name}, t nhận được code gift card free, muốn không?"
                    ],
                    "victim_responses": [
                        "thật á? card gì vậy bác?",
                        "free 500k? tin được không?",
                        "làm sao để nhận vậy bạn?",
                        "t muốn lắm! chỉ t với"
                    ],
                    "scammer_pressure": [
                        "cần verify tài khoản banking để nhận card",
                        "nhập số thẻ ATM và mã OTP vào đây {fake_link}",
                        "admin cần confirm tuổi, vào link này {fake_link}",
                        "nhanh lên, chỉ còn 10 slot thôi! {fake_link}"
                    ],
                    "victim_compliance": [
                        "số thẻ của t là {fake_card}",
                        "mã OTP là {fake_otp}",
                        "t đã nhập thông tin rồi",
                        "sao chưa nhận được card?"
                    ]
                }
            ],
            
            ScamScenario.MALICIOUS_LINK_CLICK: [
                {
                    "scammer_opening": [
                        "{name} ơi, có video mới của {celebrity} nè!",
                        "check out game mới skibidi này {name} ơi",
                        "t có tool hack robux pro nè, muốn không?",
                        "{name}, có app filter tiktok mới siêu hay"
                    ],
                    "victim_responses": [
                        "link đâu vậy bạn?",
                        "game gì vậy? có hay không?",
                        "tool hack á? có an toàn không?",
                        "app gì vậy? cho t xin link"
                    ],
                    "scammer_pressure": [
                        "click vào đây nè: {fake_link}",
                        "download tại link này: {fake_link}",
                        "link đây: {fake_link} , nhanh lên!",
                        "{fake_link} - siêu hay, phải thử!"
                    ],
                    "victim_compliance": [
                        "ok t đang click",
                        "t đang download",
                        "link bị virus á?",
                        "tài khoản t bị mất rồi!"
                    ]
                }
            ]
        }
        return templates
    
    def _generate_teen_code_text(self, base_text: str) -> str:
        """Thêm teencode vào văn bản"""
        words = base_text.split()
        result_words = []
        
        for word in words:
            # Randomly replace with teen code
            if random.random() < 0.3:  # 30% chance
                for teen_word, meanings in self.lang_model.TEENCODE_DICT.items():
                    if any(meaning in word.lower() for meaning in meanings):
                        result_words.append(teen_word)
                        break
                else:
                    result_words.append(word)
            else:
                result_words.append(word)
        
        return " ".join(result_words)
    
    def _add_emojis_and_punctuation(self, text: str) -> str:
        """Thêm emoji và dấu câu theo style trẻ em"""
        emojis = ["😂", "😱", "🔥", "💯", "🎉", "🤑", "😎", "👍", "❤️", "💪"]
        
        # Add emojis at end
        if random.random() < 0.4:  # 40% chance
            text += f" {random.choice(emojis)}"
        
        # Add excessive punctuation
        if random.random() < 0.3:  # 30% chance
            text += random.choice(["!!!", "!!", "!!!"])
        
        # Add lowercase/uppercase mix
        if random.random() < 0.2:  # 20% chance
            text = text.upper()
        
        return text
    
    def _generate_fake_link(self) -> str:
        """Tạo link giả mạo"""
        domains = ["bit.ly", "tinyurl.com", "cutt.ly", "short.link"]
        fake_paths = ["robux-free", "gift-card", "verify-account", "claim-prize"]
        
        domain = random.choice(domains)
        path = random.choice(fake_paths)
        random_id = uuid.uuid4().hex[:8]
        
        return f"https://{domain}/{path}-{random_id}"
    
    def _generate_fake_credentials(self) -> Dict[str, str]:
        """Tạo thông tin đăng nhập giả (an toàn)"""
        fake_passwords = ["123456", "password123", "roblox123", "child123", "game123"]
        fake_cards = ["4111-1111-1111-1111", "5500-0000-0000-0004", "3400-0000-0000-009"]
        fake_otp = str(random.randint(100000, 999999))
        
        return {
            "password": random.choice(fake_passwords),
            "card": random.choice(fake_cards),
            "otp": fake_otp
        }
    
    def _generate_conversation_turn(self, role: str, template_list: List[str], 
                                  context: Dict) -> str:
        """Tạo một lượt hội thoại"""
        template = random.choice(template_list)
        
        # Replace placeholders
        text = template.format(**context)
        
        # Add teen code and emojis if victim
        if role == "victim":
            text = self._generate_teen_code_text(text)
            text = self._add_emojis_and_punctuation(text)
        
        return text
    
    def _generate_single_conversation(self, scenario: ScamScenario, 
                                     age_group: AgeGroup) -> Dict:
        """Tạo một cuộc hội thoại lừa đảo"""
        
        # Get template for scenario
        templates = self.scenario_templates.get(scenario, self.scenario_templates[ScamScenario.ROBUX_PHISHING])
        template = random.choice(templates)
        
        # Generate conversation length
        num_turns = random.randint(self.config.min_conversation_turns, 
                                 self.config.max_conversation_turns)
        
        # Context for template replacement
        fake_creds = self._generate_fake_credentials()
        context = {
            "name": random.choice(["minh", "an", "bin", "linh", "huy", "mai", "khoa"]),
            "fake_link": self._generate_fake_link(),
            "fake_password": fake_creds["password"],
            "fake_card": fake_creds["card"], 
            "fake_otp": fake_creds["otp"],
            "celebrity": random.choice(["sơn tùng", "đen vâu", "đàm vĩnh hưng", "jack"])
        }
        
        conversation = []
        roles = ["scammer", "victim"]
        current_role = 0
        
        for turn in range(num_turns):
            role = roles[current_role]
            
            if role == "scammer":
                if turn == 0:
                    text = self._generate_conversation_turn(role, template["scammer_opening"], context)
                elif turn < num_turns - 1:
                    text = self._generate_conversation_turn(role, template["scammer_pressure"], context)
                else:
                    text = self._generate_conversation_turn(role, template["scammer_pressure"], context)
            else:  # victim
                if turn == 1:
                    text = self._generate_conversation_turn(role, template["victim_responses"], context)
                else:
                    text = self._generate_conversation_turn(role, template["victim_compliance"], context)
            
            conversation.append({
                "role": role,
                "text": text,
                "timestamp": (datetime.now() + timedelta(minutes=turn*5)).isoformat()
            })
            
            current_role = 1 - current_role  # Switch roles
        
        return {
            "synthetic_id": f"synth_{uuid.uuid4().hex[:8]}",
            "scenario": scenario.value,
            "age_group": age_group.value,
            "conversation_turns": len(conversation),
            "conversation": conversation,
            "language_variant": self._detect_language_variant(conversation),
            "generation_metadata": {
                "generation_timestamp": datetime.now().isoformat(),
                "generation_model": "template_based_v2.0",
                "generation_prompt": f"Vietnamese child scam scenario - {scenario.value}"
            }
        }
    
    def _detect_language_variant(self, conversation: List[Dict]) -> str:
        """Phát hiện biến thể ngôn ngữ"""
        all_text = " ".join([turn["text"] for turn in conversation])
        
        teen_code_count = sum(1 for word in self.lang_model.TEENCODE_DICT.keys() 
                            if word in all_text.lower())
        gaming_count = sum(1 for word in self.lang_model.GAMING_SLANG.keys() 
                         if word in all_text.lower())
        
        if teen_code_count > 3:
            return "teencode_heavy"
        elif gaming_count > 2:
            return "gaming_focused"
        else:
            return "mixed"
    
    def _calculate_realism_score(self, conversation_data: Dict) -> float:
        """Tính điểm realism cho hội thoại"""
        conversation = conversation_data["conversation"]
        
        # Factors for realism
        factors = {
            "conversation_flow": 0.0,  # Natural back-and-forth
            "age_appropriate": 0.0,   # Language matches age group
            "scam_progression": 0.0,  # Logical scam development
            "emotional_manipulation": 0.0  # Psychological tactics
        }
        
        # Conversation flow (alternating roles)
        role_sequence = [turn["role"] for turn in conversation]
        expected_sequence = ["scammer", "victim"] * len(conversation)
        if role_sequence == expected_sequence[:len(role_sequence)]:
            factors["conversation_flow"] = 1.0
        
        # Age appropriate language
        teen_code_ratio = sum(1 for turn in conversation 
                            if any(word in turn["text"].lower() 
                                 for word in self.lang_model.TEENCODE_DICT.keys())) / len(conversation)
        if 0.2 <= teen_code_ratio <= 0.6:  # Not too little, not too much
            factors["age_appropriate"] = 1.0
        
        # Scam progression (hook -> pressure -> compliance)
        if len(conversation) >= 3:
            factors["scam_progression"] = 1.0
        
        # Calculate overall score
        realism_score = sum(factors.values()) / len(factors)
        return min(realism_score, 1.0)
    
    def _calculate_safety_score(self, conversation_data: Dict) -> float:
        """Tính điểm safety (không chứa nội dung độc hại thực)"""
        conversation = conversation_data["conversation"]
        all_text = " ".join([turn["text"] for turn in conversation])
        
        # Check for actual harmful content
        harmful_patterns = [
            r'\b\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\b',  # Real credit card numbers
            r'\b\d{3}-\d{2}-\d{4}\b',  # Real SSN format
            r'child.*abuse',  # Real harmful content
        ]
        
        import re
        for pattern in harmful_patterns:
            if re.search(pattern, all_text, re.IGNORECASE):
                return 0.0  # Contains real harmful content
        
        return 1.0  # Safe synthetic content
    
    def generate_synthetic_dataset(self) -> List[Dict]:
        """Tạo toàn bộ dataset tổng hợp"""
        logger.info(f"🚀 Starting synthetic data generation: {self.config.num_samples} samples")
        
        synthetic_data = []
        
        # Generate samples for each scenario and age group
        scenarios = list(ScamScenario)
        age_groups = list(AgeGroup)
        
        for i in tqdm(range(self.config.num_samples), desc="Generating conversations"):
            # Random scenario and age group
            scenario = random.choice(scenarios)
            age_group = random.choice(age_groups)
            
            # Generate conversation
            conversation_data = self._generate_single_conversation(scenario, age_group)
            
            # Add quality metrics
            conversation_data["realism_score"] = self._calculate_realism_score(conversation_data)
            conversation_data["safety_score"] = self._calculate_safety_score(conversation_data)
            conversation_data["diversity_score"] = random.uniform(0.7, 1.0)  # Placeholder
            
            # Add to dataset
            synthetic_data.append(conversation_data)
            
            # Log progress
            if (i + 1) % 100 == 0:
                logger.info(f"📊 Generated {i + 1}/{self.config.num_samples} samples")
        
        logger.info(f"✅ Synthetic dataset generation completed: {len(synthetic_data)} samples")
        return synthetic_data
    
    def save_to_json(self, synthetic_data: List[Dict]):
        """Lưu dataset ra file JSON"""
        os.makedirs(os.path.dirname(self.config.output_file), exist_ok=True)
        
        with open(self.config.output_file, 'w', encoding='utf-8') as f:
            json.dump(synthetic_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Dataset saved to: {self.config.output_file}")
    
    def save_to_mongodb(self, synthetic_data: List[Dict]):
        """Lưu dataset vào MongoDB theo VIFAKE_ARCHITECTURE_2.md"""
        logger.info("📥 Saving synthetic data to MongoDB...")
        
        # Transform to match synthetic_data_collection schema
        mongo_documents = []
        
        for data in synthetic_data:
            doc = {
                "_id": str(uuid.uuid4()),
                "synthetic_id": data["synthetic_id"],
                
                # Generation metadata
                "generation_prompt": data["generation_metadata"]["generation_prompt"],
                "generation_model": data["generation_metadata"]["generation_model"],
                "generation_timestamp": datetime.fromisoformat(data["generation_metadata"]["generation_timestamp"]),
                
                # Scenario classification
                "scam_scenario": data["scenario"],
                "target_age_group": data["age_group"],
                "language_variant": data["language_variant"],
                
                # Content structure
                "conversation_turns": data["conversation_turns"],
                "participant_roles": ["scammer", "victim_child"],
                
                # Quality metrics
                "realism_score": data["realism_score"],
                "diversity_score": data["diversity_score"],
                "safety_score": data["safety_score"],
                
                # Usage tracking
                "used_in_training": False,
                "training_performance": 0.0,
                "human_reviewed": False,
                "reviewer_notes": "",
                
                # Version control
                "version": "v1.0",
                "parent_synthetic_id": None,
                
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            mongo_documents.append(doc)
        
        # Insert to MongoDB
        try:
            result = self.db.synthetic_data_collection.insert_many(mongo_documents, ordered=False)
            logger.info(f"✅ Inserted {len(result.inserted_ids)} documents to MongoDB")
        except Exception as e:
            logger.error(f"❌ MongoDB insertion failed: {e}")
            raise
    
    def generate_training_report(self, synthetic_data: List[Dict]):
        """Tạo báo cáo dataset cho training PhoBERT"""
        report = {
            "dataset_info": {
                "total_samples": len(synthetic_data),
                "generation_date": datetime.now().isoformat(),
                "model_target": "PhoBERT",
                "language": "Vietnamese",
                "purpose": "Child scam detection"
            },
            "scenario_distribution": {},
            "age_group_distribution": {},
            "language_variant_distribution": {},
            "quality_metrics": {
                "avg_realism_score": 0.0,
                "avg_safety_score": 0.0,
                "avg_diversity_score": 0.0
            }
        }
        
        # Calculate distributions
        for data in synthetic_data:
            # Scenario distribution
            scenario = data["scenario"]
            report["scenario_distribution"][scenario] = report["scenario_distribution"].get(scenario, 0) + 1
            
            # Age group distribution
            age_group = data["age_group"]
            report["age_group_distribution"][age_group] = report["age_group_distribution"].get(age_group, 0) + 1
            
            # Language variant distribution
            variant = data["language_variant"]
            report["language_variant_distribution"][variant] = report["language_variant_distribution"].get(variant, 0) + 1
            
            # Quality metrics
            report["quality_metrics"]["avg_realism_score"] += data["realism_score"]
            report["quality_metrics"]["avg_safety_score"] += data["safety_score"]
            report["quality_metrics"]["avg_diversity_score"] += data["diversity_score"]
        
        # Average quality metrics
        num_samples = len(synthetic_data)
        for metric in report["quality_metrics"]:
            report["quality_metrics"][metric] /= num_samples
        
        # Save report
        report_file = self.config.output_file.replace('.json', '_report.json')
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📋 Training report saved to: {report_file}")
        
        # Print summary
        logger.info("📊 DATASET SUMMARY:")
        logger.info(f"   Total samples: {report['dataset_info']['total_samples']}")
        logger.info(f"   Avg realism: {report['quality_metrics']['avg_realism_score']:.3f}")
        logger.info(f"   Avg safety: {report['quality_metrics']['avg_safety_score']:.3f}")
        logger.info(f"   Scenarios: {len(report['scenario_distribution'])}")
        logger.info(f"   Age groups: {len(report['age_group_distribution'])}")

def main():
    """Main execution function"""
    logger.info("🚀 Starting Vietnamese Child Scam Synthetic Data Generator")
    logger.info("🎯 Role: Ngôn ngữ học & An ninh mạng chuyên gia")
    logger.info("📋 Target: 500 mẫu hội thoại cho PhoBERT training")
    logger.info("🔒 Mode: 100% Synthetic - Privacy Compliant")
    
    # Initialize generator
    config = SyntheticConfig()
    generator = SyntheticDataGenerator(config)
    
    try:
        # Generate synthetic dataset
        synthetic_data = generator.generate_synthetic_dataset()
        
        # Save to JSON file
        generator.save_to_json(synthetic_data)
        
        # Save to MongoDB
        generator.save_to_mongodb(synthetic_data)
        
        # Generate training report
        generator.generate_training_report(synthetic_data)
        
        logger.info("🎉 Synthetic data generation completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Generation failed: {e}")
        raise
    finally:
        if generator.mongo_client:
            generator.mongo_client.close()

if __name__ == "__main__":
    from tqdm import tqdm
    main()
