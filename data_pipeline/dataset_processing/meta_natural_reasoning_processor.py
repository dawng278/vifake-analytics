#!/usr/bin/env python3
"""
Data Engineering Script - Facebook Natural Reasoning Dataset Processor
Hóa thân thành kỹ sư dữ liệu xử lý tập dữ liệu khổng lồ từ Meta

Tuân thủ Privacy-by-Design:
- Streaming mode để không làm tràn SSD 512GB
- Zero-trust RAM processing
- MongoDB metadata theo VIFAKE_ARCHITECTURE_2.md
"""

import os
import sys
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Iterator, Optional
import json
import pymongo
from pymongo import MongoClient
from datasets import load_dataset, IterableDataset
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm
import re
import asyncio
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/vifake/meta_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ProcessingConfig:
    """Configuration for dataset processing"""
    mongo_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name: str = "vifake_analytics"
    batch_size: int = 1000
    max_retries: int = 3
    ssd_limit_gb: int = 512
    retention_days: int = 30
    
    # Keywords for scam detection
    scam_keywords: List[str] = [
        'chuyển tiền', 'chuyen tien', 'transfer money',
        'mật khẩu', 'mat khau', 'password',
        'quà tặng', 'qua tang', 'gift', 'present',
        'free', 'miễn phí', 'mien phi',
        'robux', 'game', 'account',
        'click', 'link', 'otp', 'verification'
    ]

class MetaDatasetProcessor:
    """Kỹ sư dữ liệu xử lý Facebook Natural Reasoning Dataset"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.mongo_client = None
        self.db = None
        self.processed_count = 0
        self.scam_count = 0
        self.quarantine_count = 0
        
        # Initialize MongoDB connection
        self._init_mongodb()
        
    def _init_mongodb(self):
        """Initialize MongoDB connection with retry logic"""
        for attempt in range(self.config.max_retries):
            try:
                self.mongo_client = MongoClient(self.config.mongo_uri)
                self.db = self.mongo_client[self.config.db_name]
                
                # Test connection
                self.db.admin.command('ping')
                logger.info("✅ MongoDB connection established")
                return
                
            except Exception as e:
                logger.error(f"❌ MongoDB connection attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                asyncio.sleep(2 ** attempt)
    
    def _calculate_content_hash(self, content: str) -> str:
        """Calculate SHA-256 hash for zero-trust storage"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _detect_scam_keywords(self, text: str) -> Dict[str, any]:
        """Detect scam-related keywords in text"""
        text_lower = text.lower()
        detected_keywords = []
        scam_score = 0.0
        
        for keyword in self.config.scam_keywords:
            if keyword.lower() in text_lower:
                detected_keywords.append(keyword)
                scam_score += 0.1
        
        # Normalize scam score
        scam_score = min(scam_score, 1.0)
        
        return {
            "detected_keywords": detected_keywords,
            "scam_probability": scam_score,
            "contains_teencode": any(word in text_lower for word in ['skibidi', 'rizz', 'robux']),
            "leetspeak_score": self._calculate_leetspeak_score(text)
        }
    
    def _calculate_leetspeak_score(self, text: str) -> float:
        """Calculate leetspeak detection score"""
        leetspeak_patterns = {
            '0': 'o', '1': 'i', '3': 'e', '4': 'a',
            '5': 's', '7': 't', '@': 'a', '$': 's'
        }
        
        leetspeak_count = 0
        total_chars = len(text)
        
        for char in text.lower():
            if char in leetspeak_patterns:
                leetspeak_count += 1
        
        return leetspeak_count / max(total_chars, 1)
    
    def _quarantine_check(self, content: str) -> Dict[str, any]:
        """Zero-trust RAM quarantine filter"""
        # Check for CSAM and harmful content patterns
        harmful_patterns = [
            r'child.*abuse', r'csam', r'exploitation',
            r'violence', r'gore', r'extreme.*content'
        ]
        
        content_lower = content.lower()
        for pattern in harmful_patterns:
            if re.search(pattern, content_lower):
                logger.warning("🚨 Harmful content detected - QUARANTINE")
                return {
                    "is_quarantined": True,
                    "reason": "harmful_content_detected",
                    "action": "DROP"
                }
        
        return {"is_quarantined": False, "action": "PASS"}
    
    def _normalize_metadata(self, sample: Dict) -> Dict:
        """Normalize dataset sample to MongoDB metadata structure"""
        content = sample.get('text', '') or sample.get('conversation', '')
        
        # Zero-trust processing
        quarantine_result = self._quarantine_check(content)
        if quarantine_result["is_quarantined"]:
            self.quarantine_count += 1
            return None
        
        # Scam detection
        scam_analysis = self._detect_scam_keywords(content)
        
        # Create metadata according to VIFAKE_ARCHITECTURE_2.md
        metadata = {
            "post_id": f"meta_{sample.get('id', 'unknown')}",
            "platform": "facebook/natural_reasoning",
            "content_type": "text",
            "content_hash": self._calculate_content_hash(content),
            "is_quarantined": False,
            
            # Analysis metadata
            "analysis_timestamp": datetime.utcnow(),
            "scam_probability": scam_analysis["scam_probability"],
            "scam_type": self._classify_scam_type(scam_analysis["detected_keywords"]),
            "confidence_score": 0.85,  # Default confidence
            
            # Vietnamese language features
            "contains_teencode": scam_analysis["contains_teencode"],
            "leetspeak_score": scam_analysis["leetspeak_score"],
            "detected_keywords": scam_analysis["detected_keywords"],
            
            # Graph analytics
            "interaction_count": sample.get('response_count', 0),
            "propagation_depth": 1,  # Default for dataset
            "network_cluster": "research_dataset",
            
            # Compliance tracking
            "processing_tier": "research",
            "data_source": "facebook/natural_reasoning",
            "retention_expires": datetime.utcnow() + timedelta(days=self.config.retention_days),
            
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        if scam_analysis["scam_probability"] > 0.5:
            self.scam_count += 1
        
        return metadata
    
    def _classify_scam_type(self, keywords: List[str]) -> str:
        """Classify scam type based on detected keywords"""
        if any(word in keywords for word in ['robux', 'game', 'account']):
            return "gaming_account_theft"
        elif any(word in keywords for word in ['gift', 'present', 'qua tang']):
            return "gift_card_scam"
        elif any(word in keywords for word in ['password', 'mat khau', 'otp']):
            return "phishing"
        elif any(word in keywords for word in ['transfer', 'chuyen tien']):
            return "money_transfer_scam"
        else:
            return "suspicious_content"
    
    def _process_batch(self, batch_samples: List[Dict]) -> int:
        """Process a batch of samples and insert into MongoDB"""
        processed_samples = []
        
        for sample in batch_samples:
            try:
                metadata = self._normalize_metadata(sample)
                if metadata:  # Only process if not quarantined
                    processed_samples.append(metadata)
            except Exception as e:
                logger.error(f"❌ Error processing sample: {e}")
                continue
        
        if processed_samples:
            try:
                # Insert batch to MongoDB
                result = self.db.posts_collection.insert_many(processed_samples, ordered=False)
                batch_count = len(result.inserted_ids)
                self.processed_count += batch_count
                
                logger.info(f"✅ Inserted batch of {batch_count} records")
                return batch_count
                
            except Exception as e:
                logger.error(f"❌ MongoDB batch insert failed: {e}")
                return 0
        
        return 0
    
    def _log_progress(self):
        """Log processing progress every 1000 records"""
        logger.info(f"📊 Progress Update:")
        logger.info(f"   Total processed: {self.processed_count:,}")
        logger.info(f"   Scam content: {self.scam_count:,} ({self.scam_count/self.processed_count*100:.1f}%)")
        logger.info(f"   Quarantined: {self.quarantine_count:,}")
        logger.info(f"   Processing rate: {self.processed_count/1000:.1f} records/second")
    
    async def process_streaming_dataset(self, dataset_name: str = "facebook/natural_reasoning", split: str = "train"):
        """Process dataset in streaming mode to avoid SSD overflow"""
        logger.info(f"🚀 Starting streaming processing of {dataset_name}")
        logger.info(f"⚙️ Configuration: batch_size={self.config.batch_size}, retention={self.config.retention_days} days")
        
        try:
            # Load dataset in streaming mode
            logger.info("📥 Loading dataset in streaming mode...")
            dataset = load_dataset(dataset_name, split=split, streaming=True)
            
            batch_samples = []
            batch_counter = 0
            
            # Process streaming data
            logger.info("⚡ Starting streaming processing...")
            for sample in tqdm(dataset, desc="Processing samples"):
                batch_samples.append(sample)
                
                # Process batch when full
                if len(batch_samples) >= self.config.batch_size:
                    await self._process_batch_async(batch_samples)
                    batch_samples = []
                    batch_counter += 1
                    
                    # Log progress every 1000 records (every batch for batch_size=1000)
                    if batch_counter % 1 == 0:
                        self._log_progress()
                
                # Check SSD usage periodically
                if batch_counter % 10 == 0:
                    await self._check_storage_usage()
            
            # Process remaining samples
            if batch_samples:
                await self._process_batch_async(batch_samples)
            
            logger.info("🎉 Dataset processing completed!")
            self._final_report()
            
        except Exception as e:
            logger.error(f"❌ Dataset processing failed: {e}")
            raise
        finally:
            await self._cleanup()
    
    async def _process_batch_async(self, batch_samples: List[Dict]):
        """Async batch processing"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._process_batch, batch_samples)
    
    async def _check_storage_usage(self):
        """Check SSD usage and warn if approaching limit"""
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            used_gb = used / (1024**3)
            total_gb = total / (1024**3)
            
            usage_percent = (used_gb / total_gb) * 100
            
            if usage_percent > 85:
                logger.warning(f"⚠️ SSD usage high: {usage_percent:.1f}% ({used_gb:.1f}GB/{total_gb:.1f}GB)")
            elif usage_percent > 95:
                logger.error(f"🚨 SSD usage critical: {usage_percent:.1f}% - Consider stopping processing")
                
        except Exception as e:
            logger.error(f"❌ Error checking storage usage: {e}")
    
    def _final_report(self):
        """Generate final processing report"""
        logger.info("📋 FINAL PROCESSING REPORT")
        logger.info("=" * 50)
        logger.info(f"📊 Total records processed: {self.processed_count:,}")
        logger.info(f"🚨 Scam content detected: {self.scam_count:,} ({self.scam_count/self.processed_count*100:.1f}%)")
        logger.info(f"🛡️ Content quarantined: {self.quarantine_count:,}")
        logger.info(f"⏰ Processing completed at: {datetime.utcnow()}")
        logger.info(f"📈 Average processing rate: {self.processed_count/3600:.1f} records/hour")
        logger.info("=" * 50)
    
    async def _cleanup(self):
        """Cleanup resources"""
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("🔌 MongoDB connection closed")

async def main():
    """Main execution function"""
    logger.info("🚀 Starting ViFake Analytics - Meta Dataset Processor")
    logger.info("🎯 Role: Data Engineering Specialist")
    logger.info("📋 Dataset: facebook/natural_reasoning")
    logger.info("🔒 Mode: Privacy-by-Design Streaming Processing")
    
    # Initialize processor
    config = ProcessingConfig()
    processor = MetaDatasetProcessor(config)
    
    try:
        # Process dataset
        await processor.process_streaming_dataset()
        
    except KeyboardInterrupt:
        logger.info("⏹️ Processing interrupted by user")
        await processor._cleanup()
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        await processor._cleanup()
        sys.exit(1)

if __name__ == "__main__":
    # Run the processor
    asyncio.run(main())
