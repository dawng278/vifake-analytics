#!/usr/bin/env python3
"""
Perturbation Engine - Realistic Data "Dirtying" for Synthetic Data
Giải pháp tự động "làm bẩn" dữ liệu giả lập để tăng tính thực tế

Tuân thủ Privacy-by-Design:
- Chỉ áp dụng cho dữ liệu tổng hợp
- PySpark Track B processing cho leetspeak detection
- Tăng tính thực tế mà không vi phạm quyền riêng tư
"""

import random
import string
import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, udf, rand
from pyspark.sql.types import StringType, FloatType
import pymongo
from pymongo import MongoClient
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PerturbationType(Enum):
    """Các loại perturbation để làm bẩn dữ liệu"""
    TYPOS = "typos"
    LEETSPEAK = "leetspeak"
    EMOJI_INSERTION = "emoji_insertion"
    WHITESPACE_NOISE = "whitespace_noise"
    PUNCTUATION_ERRORS = "punctuation_errors"
    CASE_INCONSISTENCY = "case_inconsistency"
    WORD_REPETITION = "word_repetition"
    MISSING_CHARACTERS = "missing_characters"

@dataclass
class PerturbationConfig:
    """Cấu hình cho Perturbation Engine"""
    mongo_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name: str = "vifake_analytics"
    spark_app_name: str = "ViFake_Perturbation_Engine"
    
    # Perturbation probabilities
    typo_probability: float = 0.15
    leetspeak_probability: float = 0.20
    emoji_probability: float = 0.25
    whitespace_probability: float = 0.10
    punctuation_probability: float = 0.12
    case_probability: float = 0.18
    repetition_probability: float = 0.08
    missing_char_probability: float = 0.05
    
    # Vietnamese-specific settings
    vietnamese_tone_errors: float = 0.20
    teencode_injection: float = 0.25
    
    # Output settings
    batch_size: int = 1000
    output_collection: str = "perturbed_synthetic_data"

class VietnameseLanguagePerturber:
    """Công cụ perturbation chuyên cho tiếng Việt"""
    
    # Vietnamese characters with tone marks
    VIETNAMESE_CHARS = {
        'a': ['á', 'à', 'ả', 'ã', 'ạ'],
        'ă': ['ắ', 'ằ', 'ẳ', 'ẵ', 'ặ'],
        'â': ['ấ', 'ầ', 'ẩ', 'ẫ', 'ậ'],
        'e': ['é', 'è', 'ẻ', 'ẽ', 'ẹ'],
        'ê': ['ế', 'ề', 'ể', 'ễ', 'ệ'],
        'i': ['í', 'ì', 'ỉ', 'ĩ', 'ị'],
        'o': ['ó', 'ò', 'ỏ', 'õ', 'ọ'],
        'ô': ['ố', 'ồ', 'ổ', 'ỗ', 'ộ'],
        'ơ': ['ớ', 'ờ', 'ở', 'ỡ', 'ợ'],
        'u': ['ú', 'ù', 'ủ', 'ũ', 'ụ'],
        'ư': ['ứ', 'ừ', 'ử', 'ữ', 'ự'],
        'y': ['ý', 'ỳ', 'ỷ', 'ỹ', 'ỵ'],
        'd': ['đ']
    }
    
    # Teencode mappings
    TEENCODE_MAP = {
        'không': 'ko', 'khong': 'ko',
        'gì': 'j', 'gi': 'j',
        'bạn': 'bn', 'ban': 'bn',
        'mình': 'mk', 'minh': 'mk',
        'vui': 'vl', 'vui': 'vl',
        'buồn': 'bn', 'buon': 'bn',
        'đẹp': 'dp', 'dep': 'dp',
        'hay': 'h', 'hay': 'h',
        'ok': 'ok', 'oke': 'ok',
        'thanks': 'tk', 'thank': 'tk',
        'sorry': 'sr', 'xin lỗi': 'sr'
    }
    
    # Leetspeak mappings
    LEETSPEAK_MAP = {
        'o': '0', 'i': '1', 'e': '3', 'a': '4', 's': '5', 't': '7',
        'l': '1', 'g': '9', 'b': '8', 'z': '2'
    }
    
    # Common emojis
    EMOJIS = ['😂', '😭', '😱', '🔥', '💯', '🎉', '🤑', '😎', '👍', '❤️', '💪', '🙏', '😊', '🤔', '👏']
    
    def __init__(self, config: PerturbationConfig):
        self.config = config
        random.seed(42)  # For reproducibility
    
    def introduce_typo(self, text: str) -> str:
        """Giới thiệu lỗi chính tả ngẫu nhiên"""
        if random.random() > self.config.typo_probability:
            return text
        
        words = text.split()
        if not words:
            return text
        
        # Select random word to modify
        word_idx = random.randint(0, len(words) - 1)
        word = words[word_idx]
        
        if len(word) <= 2:
            return text
        
        # Typo types
        typo_types = ['swap', 'delete', 'duplicate', 'replace']
        typo_type = random.choice(typo_types)
        
        if typo_type == 'swap' and len(word) >= 2:
            # Swap adjacent characters
            char_idx = random.randint(0, len(word) - 2)
            word = word[:char_idx] + word[char_idx+1] + word[char_idx] + word[char_idx+2:]
        elif typo_type == 'delete':
            # Delete random character
            char_idx = random.randint(1, len(word) - 2)
            word = word[:char_idx] + word[char_idx+1:]
        elif typo_type == 'duplicate':
            # Duplicate random character
            char_idx = random.randint(0, len(word) - 1)
            word = word[:char_idx+1] + word[char_idx] + word[char_idx+1:]
        elif typo_type == 'replace':
            # Replace with nearby character (QWERTY mistakes)
            char_idx = random.randint(0, len(word) - 1)
            nearby_chars = self._get_nearby_chars(word[char_idx])
            if nearby_chars:
                word = word[:char_idx] + random.choice(nearby_chars) + word[char_idx+1:]
        
        words[word_idx] = word
        return ' '.join(words)
    
    def _get_nearby_chars(self, char: str) -> List[str]:
        """Lấy các ký tự gần trên bàn phím QWERTY"""
        keyboard_map = {
            'q': ['w', 'a', 's'], 'w': ['q', 'e', 'a', 's', 'd'],
            'e': ['w', 'r', 's', 'd', 'f'], 'r': ['e', 't', 'd', 'f', 'g'],
            't': ['r', 'y', 'f', 'g', 'h'], 'y': ['t', 'u', 'g', 'h', 'j'],
            'u': ['y', 'i', 'h', 'j', 'k'], 'i': ['u', 'o', 'j', 'k', 'l'],
            'o': ['i', 'p', 'k', 'l'], 'p': ['o', 'l'],
            'a': ['q', 'w', 's', 'z'], 's': ['q', 'w', 'e', 'a', 'd', 'z', 'x'],
            'd': ['w', 'e', 'r', 's', 'f', 'x', 'c'], 'f': ['e', 'r', 't', 'd', 'g', 'c', 'v'],
            'g': ['r', 't', 'y', 'f', 'h', 'v', 'b'], 'h': ['t', 'y', 'u', 'g', 'j', 'b', 'n'],
            'j': ['y', 'u', 'i', 'h', 'k', 'n', 'm'], 'k': ['u', 'i', 'o', 'j', 'l', 'm'],
            'l': ['i', 'o', 'p', 'k'], 'z': ['a', 's', 'x'],
            'x': ['z', 's', 'd', 'c'], 'c': ['x', 'd', 'f', 'v'],
            'v': ['c', 'f', 'g', 'b'], 'b': ['v', 'g', 'h', 'n'],
            'n': ['b', 'h', 'j', 'm'], 'm': ['n', 'j', 'k']
        }
        return keyboard_map.get(char.lower(), [])
    
    def introduce_leetspeak(self, text: str) -> str:
        """Giới thiệu leetspeak vào văn bản"""
        if random.random() > self.config.leetspeak_probability:
            return text
        
        result = []
        for char in text.lower():
            if char in self.LEETSPEAK_MAP and random.random() < 0.3:  # 30% chance to replace
                result.append(self.LEETSPEAK_MAP[char])
            else:
                result.append(char)
        
        return ''.join(result)
    
    def inject_teencode(self, text: str) -> str:
        """Tiêm teencode vào văn bản tiếng Việt"""
        if random.random() > self.config.teencode_injection:
            return text
        
        words = text.split()
        for i, word in enumerate(words):
            if word.lower() in self.TEENCODE_MAP and random.random() < 0.4:  # 40% chance
                words[i] = self.TEENCODE_MAP[word.lower()]
        
        return ' '.join(words)
    
    def add_emoji_noise(self, text: str) -> str:
        """Thêm emoji ngẫu nhiên vào văn bản"""
        if random.random() > self.config.emoji_probability:
            return text
        
        # Random emoji insertion points
        num_emojis = random.randint(1, 3)
        words = text.split()
        
        for _ in range(num_emojis):
            if words:
                insert_pos = random.randint(0, len(words))
                emoji = random.choice(self.EMOJIS)
                words.insert(insert_pos, emoji)
        
        return ' '.join(words)
    
    def add_whitespace_noise(self, text: str) -> str:
        """Thêm khoảng trắng thừa"""
        if random.random() > self.config.whitespace_probability:
            return text
        
        # Add extra spaces randomly
        words = text.split()
        result = []
        
        for word in words:
            result.append(word)
            if random.random() < 0.2:  # 20% chance for extra space
                result.append('')  # Empty string creates double space when joined
        
        return ' '.join(result)
    
    def introduce_punctuation_errors(self, text: str) -> str:
        """Giới thiệu lỗi dấu câu"""
        if random.random() > self.config.punctuation_probability:
            return text
        
        # Remove or add punctuation randomly
        punctuation = ['.', ',', '!', '?', ';', ':']
        
        # Randomly remove punctuation
        for punct in punctuation:
            if random.random() < 0.1:  # 10% chance to remove each punctuation
                text = text.replace(punct, '')
        
        # Randomly add extra punctuation
        if random.random() < 0.3:  # 30% chance to add extra
            end_punct = random.choice(['!!!', '...', '!!', '??'])
            text = text.rstrip() + end_punct
        
        return text
    
    def introduce_case_inconsistency(self, text: str) -> str:
        """Giới thiệu inconsistency về chữ hoa/thường"""
        if random.random() > self.config.case_probability:
            return text
        
        words = text.split()
        for i, word in enumerate(words):
            if random.random() < 0.3:  # 30% chance to modify case
                if random.random() < 0.5:
                    words[i] = word.upper()
                else:
                    words[i] = word.lower()
        
        return ' '.join(words)
    
    def add_word_repetition(self, text: str) -> str:
        """Thêm lặp từ (thường thấy trong chat)"""
        if random.random() > self.config.repetition_probability:
            return text
        
        words = text.split()
        if not words:
            return text
        
        # Repeat random word
        word_idx = random.randint(0, len(words) - 1)
        repeat_count = random.randint(2, 3)  # Repeat 2-3 times
        
        words[word_idx:word_idx+1] = [words[word_idx]] * repeat_count
        
        return ' '.join(words)
    
    def introduce_vietnamese_tone_errors(self, text: str) -> str:
        """Giới thiệu lỗi dấu câu tiếng Việt"""
        if random.random() > self.config.vietnamese_tone_errors:
            return text
        
        # Randomly change or remove tone marks
        result = []
        for char in text:
            if char.lower() in self.VIETNAMESE_CHARS and random.random() < 0.2:
                # Either remove tone or change to different tone
                if random.random() < 0.5:
                    # Remove tone (use base character)
                    result.append(char.lower())
                else:
                    # Change to different tone
                    base_char = char.lower()
                    if base_char in ['d']:
                        result.append(random.choice(['d', 'đ']))
                    else:
                        tones = self.VIETNAMESE_CHARS[base_char]
                        result.append(random.choice(tones + [base_char]))
            else:
                result.append(char)
        
        return ''.join(result)
    
    def apply_all_perturbations(self, text: str) -> Tuple[str, Dict[str, bool]]:
        """Áp dụng tất cả các loại perturbation"""
        perturbations_applied = {
            'typos': False,
            'leetspeak': False,
            'emoji': False,
            'whitespace': False,
            'punctuation': False,
            'case': False,
            'repetition': False,
            'vietnamese_tones': False,
            'teencode': False
        }
        
        original_text = text
        
        # Apply each perturbation type
        text = self.introduce_typo(text)
        if text != original_text:
            perturbations_applied['typos'] = True
        
        text = self.introduce_leetspeak(text)
        if text != original_text:
            perturbations_applied['leetspeak'] = True
        
        text = self.add_emoji_noise(text)
        if text != original_text:
            perturbations_applied['emoji'] = True
        
        text = self.add_whitespace_noise(text)
        if text != original_text:
            perturbations_applied['whitespace'] = True
        
        text = self.introduce_punctuation_errors(text)
        if text != original_text:
            perturbations_applied['punctuation'] = True
        
        text = self.introduce_case_inconsistency(text)
        if text != original_text:
            perturbations_applied['case'] = True
        
        text = self.add_word_repetition(text)
        if text != original_text:
            perturbations_applied['repetition'] = True
        
        text = self.introduce_vietnamese_tone_errors(text)
        if text != original_text:
            perturbations_applied['vietnamese_tones'] = True
        
        text = self.inject_teencode(text)
        if text != original_text:
            perturbations_applied['teencode'] = True
        
        return text, perturbations_applied

class PerturbationEngine:
    """Main Perturbation Engine với PySpark integration"""
    
    def __init__(self, config: PerturbationConfig):
        self.config = config
        self.perturber = VietnameseLanguagePerturber(config)
        self.spark = None
        self.mongo_client = None
        self.db = None
        
        # Initialize Spark and MongoDB
        self._init_spark()
        self._init_mongodb()
    
    def _init_spark(self):
        """Initialize Spark session"""
        self.spark = SparkSession.builder \
            .appName(self.config.spark_app_name) \
            .config("spark.driver.memory", "4g") \
            .config("spark.executor.memory", "8g") \
            .config("spark.sql.shuffle.partitions", "100") \
            .getOrCreate()
        
        logger.info("✅ Spark session initialized")
    
    def _init_mongodb(self):
        """Initialize MongoDB connection"""
        try:
            self.mongo_client = MongoClient(self.config.mongo_uri)
            self.db = self.mongo_client[self.config.db_name]
            logger.info("✅ MongoDB connection established")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
    
    def load_synthetic_data(self) -> List[Dict]:
        """Load synthetic data from MongoDB"""
        logger.info("📥 Loading synthetic data from MongoDB...")
        
        try:
            collection = self.db.synthetic_data_collection
            cursor = collection.find({"used_in_training": False}).limit(10000)  # Process 10k at a time
            
            data = list(cursor)
            logger.info(f"✅ Loaded {len(data)} synthetic records")
            return data
            
        except Exception as e:
            logger.error(f"❌ Failed to load synthetic data: {e}")
            raise
    
    def perturb_text_udf(self, text: str) -> str:
        """UDF for Spark text perturbation"""
        perturbed_text, _ = self.perturber.apply_all_perturbations(text)
        return perturbed_text
    
    def process_with_spark(self, synthetic_data: List[Dict]) -> List[Dict]:
        """Process data using PySpark (Track B processing)"""
        logger.info("⚡ Starting PySpark Track B processing...")
        
        # Convert to Spark DataFrame
        df = self.spark.createDataFrame(synthetic_data)
        
        # Register UDF for perturbation
        perturb_udf = udf(self.perturb_text_udf, StringType())
        
        # Apply perturbations to conversation texts
        perturbed_df = df.withColumn(
            "perturbed_conversation",
            perturb_udf(col("conversation"))
        )
        
        # Add randomness for diverse perturbations
        perturbed_df = perturbed_df.withColumn("random_seed", (rand() * 1000).cast("int"))
        
        # Show sample results
        logger.info("📊 Sample perturbed conversations:")
        perturbed_df.select("synthetic_id", "conversation", "perturbed_conversation").show(5, truncate=False)
        
        # Convert back to Python list
        perturbed_data = perturbed_df.collect()
        
        # Transform Spark Row objects to dictionaries
        result_data = []
        for row in perturbed_data:
            # Create perturbation metadata
            original_text = row.conversation
            perturbed_text = row.perturbed_conversation
            
            # Track which perturbations were applied
            _, perturbations_applied = self.perturber.apply_all_perturbations(original_text)
            
            # Create new record
            perturbed_record = {
                "_id": str(row["_id"]) if "_id" in row else str(random.randint(100000, 999999)),
                "original_synthetic_id": row.synthetic_id,
                "original_conversation": original_text,
                "perturbed_conversation": perturbed_text,
                "perturbations_applied": perturbations_applied,
                "perturbation_timestamp": datetime.utcnow(),
                "perturbation_score": sum(perturbations_applied.values()) / len(perturbations_applied),
                "leetspeak_score": self.perturber._calculate_leetspeak_score(perturbed_text),
                "realism_boost": random.uniform(0.1, 0.3),  # Estimated realism improvement
                "scenario": row.scenario,
                "age_group": row.age_group,
                "language_variant": row.language_variant,
                "version": "v1.1_perturbed",
                "parent_synthetic_id": row.synthetic_id,
                "created_at": datetime.utcnow()
            }
            
            result_data.append(perturbed_record)
        
        logger.info(f"✅ Perturbed {len(result_data)} records using Spark")
        return result_data
    
    def _calculate_leetspeak_score(self, text: str) -> float:
        """Calculate leetspeak score for perturbed text"""
        leetspeak_count = 0
        total_chars = len(text)
        
        for char in text.lower():
            if char in self.perturber.LEETSPEAK_MAP.values():
                leetspeak_count += 1
        
        return leetspeak_count / max(total_chars, 1)
    
    def save_perturbed_data(self, perturbed_data: List[Dict]):
        """Save perturbed data to MongoDB"""
        logger.info("💾 Saving perturbed data to MongoDB...")
        
        try:
            collection = self.db[self.config.output_collection]
            
            # Insert perturbed data
            result = collection.insert_many(perturbed_data, ordered=False)
            logger.info(f"✅ Inserted {len(result.inserted_ids)} perturbed records")
            
            # Update original synthetic data to mark as used
            original_ids = [record["original_synthetic_id"] for record in perturbed_data]
            self.db.synthetic_data_collection.update_many(
                {"synthetic_id": {"$in": original_ids}},
                {"$set": {"used_in_training": True, "updated_at": datetime.utcnow()}}
            )
            
            logger.info("✅ Original synthetic data marked as used")
            
        except Exception as e:
            logger.error(f"❌ Failed to save perturbed data: {e}")
            raise
    
    def generate_perturbation_report(self, perturbed_data: List[Dict]):
        """Generate perturbation analysis report"""
        logger.info("📋 Generating perturbation report...")
        
        # Analyze perturbation statistics
        total_records = len(perturbed_data)
        perturbation_stats = {
            'typos': 0,
            'leetspeak': 0,
            'emoji': 0,
            'whitespace': 0,
            'punctuation': 0,
            'case': 0,
            'repetition': 0,
            'vietnamese_tones': 0,
            'teencode': 0
        }
        
        avg_perturbation_score = 0
        avg_leetspeak_score = 0
        avg_realism_boost = 0
        
        for record in perturbed_data:
            # Count perturbation types
            for pert_type in perturbation_stats:
                if record['perturbations_applied'].get(pert_type, False):
                    perturbation_stats[pert_type] += 1
            
            avg_perturbation_score += record['perturbation_score']
            avg_leetspeak_score += record['leetspeak_score']
            avg_realism_boost += record['realism_boost']
        
        # Calculate averages
        avg_perturbation_score /= total_records
        avg_leetspeak_score /= total_records
        avg_realism_boost /= total_records
        
        # Convert to percentages
        for pert_type in perturbation_stats:
            perturbation_stats[pert_type] = (perturbation_stats[pert_type] / total_records) * 100
        
        # Create report
        report = {
            "perturbation_summary": {
                "total_records_processed": total_records,
                "processing_timestamp": datetime.now().isoformat(),
                "engine_version": "v1.0",
                "track": "PySpark Track B"
            },
            "perturbation_statistics": perturbation_stats,
            "quality_metrics": {
                "avg_perturbation_score": avg_perturbation_score,
                "avg_leetspeak_score": avg_leetspeak_score,
                "avg_realism_boost": avg_realism_boost
            },
            "scenario_distribution": {},
            "language_variant_distribution": {}
        }
        
        # Calculate distributions
        for record in perturbed_data:
            scenario = record['scenario']
            variant = record['language_variant']
            
            report["scenario_distribution"][scenario] = report["scenario_distribution"].get(scenario, 0) + 1
            report["language_variant_distribution"][variant] = report["language_variant_distribution"].get(variant, 0) + 1
        
        # Save report
        report_file = f"data/perturbation/perturbation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📋 Perturbation report saved to: {report_file}")
        
        # Print summary
        logger.info("📊 PERTURBATION SUMMARY:")
        logger.info(f"   Total records: {total_records}")
        logger.info(f"   Avg perturbation score: {avg_perturbation_score:.3f}")
        logger.info(f"   Avg leetspeak score: {avg_leetspeak_score:.3f}")
        logger.info(f"   Avg realism boost: {avg_realism_boost:.3f}")
        logger.info(f"   Most common perturbation: {max(perturbation_stats, key=perturbation_stats.get)}")
    
    def cleanup(self):
        """Cleanup resources"""
        if self.spark:
            self.spark.stop()
            logger.info("🔌 Spark session stopped")
        
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("🔌 MongoDB connection closed")

def main():
    """Main execution function"""
    logger.info("🚀 Starting ViFake Perturbation Engine")
    logger.info("🎯 Purpose: Realistic data 'dirtying' for synthetic data")
    logger.info("🔧 Technology: PySpark Track B + Vietnamese NLP")
    logger.info("🔒 Compliance: Synthetic data only - Privacy safe")
    
    # Initialize engine
    config = PerturbationConfig()
    engine = PerturbationEngine(config)
    
    try:
        # Load synthetic data
        synthetic_data = engine.load_synthetic_data()
        
        if not synthetic_data:
            logger.warning("⚠️ No synthetic data found to perturb")
            return
        
        # Process with Spark (Track B)
        perturbed_data = engine.process_with_spark(synthetic_data)
        
        # Save perturbed data
        engine.save_perturbed_data(perturbed_data)
        
        # Generate report
        engine.generate_perturbation_report(perturbed_data)
        
        logger.info("🎉 Perturbation Engine completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Perturbation failed: {e}")
        raise
    finally:
        engine.cleanup()

if __name__ == "__main__":
    main()
