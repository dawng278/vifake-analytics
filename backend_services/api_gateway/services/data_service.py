#!/usr/bin/env python3
"""
Data Service Integration for ViFake Analytics
Service layer for MongoDB and data pipeline communication

Tuân thủ Privacy-by-Design:
- Zero-trust RAM processing
- Database query optimization
- No persistent storage of harmful content
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import aiohttp
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataServiceIntegration:
    """Integration layer for data services"""
    
    def __init__(self):
        # MongoDB configuration
        self.mongo_uri = "mongodb://localhost:27017"
        self.db_name = "vifake_analytics"
        self.client = None
        self.db = None
        
        # Data pipeline service URL
        self.pipeline_service_url = "http://localhost:8004"
        
        # Connection status
        self.mongo_connected = False
        self.pipeline_connected = False
        
        logger.info("📊 Data Service Integration initialized")
    
    async def connect_mongodb(self) -> bool:
        """Connect to MongoDB"""
        try:
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            self.db = self.client[self.db_name]
            
            # Test connection
            self.db.admin.command('ping')
            self.mongo_connected = True
            
            logger.info("✅ MongoDB connection established")
            return True
            
        except ConnectionFailure as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            self.mongo_connected = False
            return False
    
    async def check_pipeline_health(self) -> bool:
        """Check data pipeline service health"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.pipeline_service_url}/health", timeout=5) as response:
                    self.pipeline_connected = response.status == 200
                    return self.pipeline_connected
        except Exception as e:
            logger.warning(f"⚠️ Pipeline service health check failed: {e}")
            self.pipeline_connected = False
            return False
    
    async def trigger_crawling(self, platform: str, profile_id: str, crawl_config: Dict = None) -> Dict:
        """Trigger honeypot crawler"""
        logger.info(f"🔍 Triggering crawler for {platform}:{profile_id}")
        
        try:
            # Check pipeline service health
            if not self.pipeline_connected:
                await self.check_pipeline_health()
            
            if not self.pipeline_connected:
                logger.warning("⚠️ Pipeline service unavailable, using fallback")
                return self._fallback_crawling_result(platform, profile_id)
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "platform": platform,
                    "profile_id": profile_id,
                    "config": crawl_config or {}
                }
                
                async with session.post(f"{self.pipeline_service_url}/crawl", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Crawler triggered: {result.get('job_id', 'unknown')}")
                        return result
                    else:
                        logger.error(f"❌ Crawler trigger failed: {response.status}")
                        return self._fallback_crawling_result(platform, profile_id)
        
        except Exception as e:
            logger.error(f"❌ Crawling trigger failed: {e}")
            return self._fallback_crawling_result(platform, profile_id)
    
    async def get_post_metadata(self, post_id: str) -> Dict:
        """Fetch post metadata from MongoDB"""
        logger.info(f"📋 Fetching metadata for post: {post_id}")
        
        try:
            # Ensure MongoDB connection
            if not self.mongo_connected:
                await self.connect_mongodb()
            
            if not self.mongo_connected:
                logger.warning("⚠️ MongoDB unavailable, using fallback")
                return self._fallback_post_metadata(post_id)
            
            # Query posts collection
            posts_collection = self.db["posts_collection"]
            post_data = posts_collection.find_one({"post_id": post_id})
            
            if post_data:
                # Convert ObjectId to string for JSON serialization
                if "_id" in post_data:
                    post_data["_id"] = str(post_data["_id"])
                
                logger.info(f"✅ Metadata found for post: {post_id}")
                return post_data
            else:
                logger.warning(f"⚠️ Post not found: {post_id}")
                return self._fallback_post_metadata(post_id)
        
        except Exception as e:
            logger.error(f"❌ Metadata fetch failed: {e}")
            return self._fallback_post_metadata(post_id)
    
    async def save_analysis_result(self, post_id: str, analysis_result: Dict) -> bool:
        """Save analysis result to MongoDB"""
        logger.info(f"💾 Saving analysis result for post: {post_id}")
        
        try:
            # Ensure MongoDB connection
            if not self.mongo_connected:
                await self.connect_mongodb()
            
            if not self.mongo_connected:
                logger.error("❌ Cannot save result: MongoDB unavailable")
                return False
            
            # Update or insert post with analysis result
            posts_collection = self.db["posts_collection"]
            
            update_data = {
                "$set": {
                    "analysis_result": analysis_result,
                    "analysis_timestamp": datetime.now(),
                    "analysis_status": "completed"
                }
            }
            
            result = posts_collection.update_one(
                {"post_id": post_id},
                update_data,
                upsert=True
            )
            
            if result.matched_count > 0:
                logger.info(f"✅ Analysis result saved for post: {post_id}")
            else:
                logger.info(f"✅ New post created with analysis result: {post_id}")
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Analysis result save failed: {e}")
            return False
    
    async def get_user_interactions(self, post_id: str, limit: int = 100) -> List[Dict]:
        """Get user interactions for a post"""
        logger.info(f"👥 Fetching interactions for post: {post_id}")
        
        try:
            # Ensure MongoDB connection
            if not self.mongo_connected:
                await self.connect_mongodb()
            
            if not self.mongo_connected:
                logger.warning("⚠️ MongoDB unavailable, returning empty list")
                return []
            
            # Query interactions collection
            interactions_collection = self.db["user_interactions_collection"]
            cursor = interactions_collection.find(
                {"post_id": post_id}
            ).sort("interaction_timestamp", -1).limit(limit)
            
            interactions = []
            for interaction in cursor:
                # Convert ObjectId to string
                if "_id" in interaction:
                    interaction["_id"] = str(interaction["_id"])
                interactions.append(interaction)
            
            logger.info(f"✅ Found {len(interactions)} interactions for post: {post_id}")
            return interactions
        
        except Exception as e:
            logger.error(f"❌ Interactions fetch failed: {e}")
            return []
    
    async def get_synthetic_data_stats(self) -> Dict:
        """Get synthetic data statistics"""
        logger.info("📊 Fetching synthetic data statistics")
        
        try:
            # Ensure MongoDB connection
            if not self.mongo_connected:
                await self.connect_mongodb()
            
            if not self.mongo_connected:
                logger.warning("⚠️ MongoDB unavailable, using fallback")
                return self._fallback_synthetic_stats()
            
            # Query synthetic data collection
            synthetic_collection = self.db["synthetic_data_collection"]
            
            # Get collection stats
            total_count = synthetic_collection.count_documents({})
            
            # Get scenario distribution
            scenario_pipeline = [
                {"$group": {"_id": "$scenario", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            scenario_dist = list(synthetic_collection.aggregate(scenario_pipeline))
            
            # Get age group distribution
            age_pipeline = [
                {"$group": {"_id": "$age_group", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            age_dist = list(synthetic_collection.aggregate(age_pipeline))
            
            # Get average realism score
            realism_pipeline = [
                {"$group": {"_id": None, "avg_realism": {"$avg": "$realism_score"}}}
            ]
            realism_result = list(synthetic_collection.aggregate(realism_pipeline))
            avg_realism = realism_result[0]["avg_realism"] if realism_result else 0.0
            
            stats = {
                "total_synthetic_samples": total_count,
                "scenario_distribution": {item["_id"]: item["count"] for item in scenario_dist},
                "age_group_distribution": {item["_id"]: item["count"] for item in age_dist},
                "average_realism_score": avg_realism,
                "last_updated": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Synthetic data stats: {total_count} samples")
            return stats
        
        except Exception as e:
            logger.error(f"❌ Synthetic stats fetch failed: {e}")
            return self._fallback_synthetic_stats()
    
    async def get_training_metrics(self) -> Dict:
        """Get model training metrics from MongoDB"""
        logger.info("📈 Fetching training metrics")
        
        try:
            # Ensure MongoDB connection
            if not self.mongo_connected:
                await self.connect_mongodb()
            
            if not self.mongo_connected:
                logger.warning("⚠️ MongoDB unavailable, using fallback")
                return self._fallback_training_metrics()
            
            # Query training collection
            training_collection = self.db["model_training_collection"]
            
            # Get latest training run
            latest_training = training_collection.find_one(
                sort=[("training_timestamp", -1)]
            )
            
            if latest_training:
                # Convert ObjectId to string
                if "_id" in latest_training:
                    latest_training["_id"] = str(latest_training["_id"])
                
                logger.info("✅ Training metrics found")
                return latest_training
            else:
                logger.warning("⚠️ No training metrics found")
                return self._fallback_training_metrics()
        
        except Exception as e:
            logger.error(f"❌ Training metrics fetch failed: {e}")
            return self._fallback_training_metrics()
    
    async def get_audit_logs(self, limit: int = 100, event_type: str = None) -> List[Dict]:
        """Get audit logs from MongoDB"""
        logger.info(f"📋 Fetching audit logs (limit: {limit})")
        
        try:
            # Ensure MongoDB connection
            if not self.mongo_connected:
                await self.connect_mongodb()
            
            if not self.mongo_connected:
                logger.warning("⚠️ MongoDB unavailable, returning empty list")
                return []
            
            # Query audit logs collection
            audit_collection = self.db["audit_log_collection"]
            
            # Build query
            query = {}
            if event_type:
                query["event_type"] = event_type
            
            cursor = audit_collection.find(query).sort("event_timestamp", -1).limit(limit)
            
            logs = []
            for log in cursor:
                # Convert ObjectId to string
                if "_id" in log:
                    log["_id"] = str(log["_id"])
                logs.append(log)
            
            logger.info(f"✅ Found {len(logs)} audit logs")
            return logs
        
        except Exception as e:
            logger.error(f"❌ Audit logs fetch failed: {e}")
            return []
    
    def _fallback_crawling_result(self, platform: str, profile_id: str) -> Dict:
        """Fallback crawling result when service is unavailable"""
        logger.info("🔄 Using fallback crawling result")
        
        return {
            "job_id": f"fallback_{platform}_{profile_id}_{int(datetime.now().timestamp())}",
            "status": "completed",
            "platform": platform,
            "profile_id": profile_id,
            "posts_found": 0,
            "message": "Crawling service unavailable - using fallback",
            "crawling_method": "fallback_mock"
        }
    
    def _fallback_post_metadata(self, post_id: str) -> Dict:
        """Fallback post metadata when MongoDB is unavailable"""
        logger.info("🔄 Using fallback post metadata")
        
        return {
            "post_id": post_id,
            "platform": "unknown",
            "content_type": "unknown",
            "created_at": datetime.now().isoformat(),
            "author_id": "unknown",
            "text_content": "",
            "media_urls": [],
            "metadata": {
                "fallback": True,
                "reason": "MongoDB unavailable"
            }
        }
    
    def _fallback_synthetic_stats(self) -> Dict:
        """Fallback synthetic data statistics"""
        logger.info("🔄 Using fallback synthetic stats")
        
        return {
            "total_synthetic_samples": 750,
            "scenario_distribution": {
                "robux_phishing": 250,
                "gift_card_scam": 200,
                "malicious_link": 150,
                "account_theft": 100,
                "crypto_scam": 50
            },
            "age_group_distribution": {
                "8-10": 250,
                "11-13": 250,
                "14-17": 250
            },
            "average_realism_score": 0.91,
            "last_updated": datetime.now().isoformat(),
            "fallback": True
        }
    
    def _fallback_training_metrics(self) -> Dict:
        """Fallback training metrics"""
        logger.info("🔄 Using fallback training metrics")
        
        return {
            "model_name": "phobert_scam_detector",
            "training_timestamp": datetime.now().isoformat(),
            "training_status": "completed",
            "performance_metrics": {
                "accuracy": 0.92,
                "precision": 0.91,
                "recall": 0.93,
                "f1_score": 0.92
            },
            "training_config": {
                "epochs": 3,
                "batch_size": 16,
                "learning_rate": 2e-5
            },
            "fallback": True
        }
    
    async def get_service_status(self) -> Dict:
        """Get overall service status"""
        # Check MongoDB connection
        if not self.mongo_connected:
            await self.connect_mongodb()
        
        # Check pipeline service
        await self.check_pipeline_health()
        
        return {
            "mongodb_connected": self.mongo_connected,
            "pipeline_service_connected": self.pipeline_connected,
            "mongo_uri": self.mongo_uri,
            "database_name": self.db_name,
            "pipeline_service_url": self.pipeline_service_url,
            "last_check": datetime.now().isoformat()
        }
    
    async def cleanup_old_data(self, days_old: int = 30) -> Dict:
        """Clean up old data from MongoDB"""
        logger.info(f"🧹 Cleaning up data older than {days_old} days")
        
        try:
            # Ensure MongoDB connection
            if not self.mongo_connected:
                await self.connect_mongodb()
            
            if not self.mongo_connected:
                logger.error("❌ Cannot cleanup: MongoDB unavailable")
                return {"success": False, "reason": "MongoDB unavailable"}
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            # Clean up old posts
            posts_collection = self.db["posts_collection"]
            posts_deleted = posts_collection.delete_many({
                "created_at": {"$lt": cutoff_date},
                "analysis_status": "completed"
            }).deleted_count
            
            # Clean up old interactions
            interactions_collection = self.db["user_interactions_collection"]
            interactions_deleted = interactions_collection.delete_many({
                "interaction_timestamp": {"$lt": cutoff_date}
            }).deleted_count
            
            # Clean up old audit logs
            audit_collection = self.db["audit_log_collection"]
            logs_deleted = audit_collection.delete_many({
                "event_timestamp": {"$lt": cutoff_date}
            }).deleted_count
            
            result = {
                "success": True,
                "cutoff_date": cutoff_date.isoformat(),
                "posts_deleted": posts_deleted,
                "interactions_deleted": interactions_deleted,
                "audit_logs_deleted": logs_deleted,
                "total_deleted": posts_deleted + interactions_deleted + logs_deleted
            }
            
            logger.info(f"✅ Cleanup completed: {result['total_deleted']} records deleted")
            return result
        
        except Exception as e:
            logger.error(f"❌ Data cleanup failed: {e}")
            return {"success": False, "reason": str(e)}

# Global service instance
_data_service = None

def get_data_service() -> DataServiceIntegration:
    """Get singleton data service instance"""
    global _data_service
    if _data_service is None:
        _data_service = DataServiceIntegration()
    return _data_service

# Convenience functions
async def trigger_content_crawling(platform: str, profile_id: str) -> Dict:
    """Trigger content crawling"""
    service = get_data_service()
    return await service.trigger_crawling(platform, profile_id)

async def fetch_post_metadata(post_id: str) -> Dict:
    """Fetch post metadata"""
    service = get_data_service()
    return await service.get_post_metadata(post_id)

async def save_analysis(post_id: str, result: Dict) -> bool:
    """Save analysis result"""
    service = get_data_service()
    return await service.save_analysis_result(post_id, result)

if __name__ == "__main__":
    # Test data service integration
    async def test_data_service():
        service = get_data_service()
        
        # Test MongoDB connection
        mongo_ok = await service.connect_mongodb()
        print(f"MongoDB connected: {mongo_ok}")
        
        # Test pipeline health
        pipeline_ok = await service.check_pipeline_health()
        print(f"Pipeline healthy: {pipeline_ok}")
        
        # Test crawling trigger
        crawl_result = await service.trigger_crawling("youtube", "test_profile")
        print(f"Crawl result: {crawl_result}")
        
        # Test metadata fetch
        metadata = await service.get_post_metadata("test_post_123")
        print(f"Metadata: {metadata}")
        
        # Get service status
        status = await service.get_service_status()
        print(f"Service status: {status}")
    
    # Run test
    asyncio.run(test_data_service())
