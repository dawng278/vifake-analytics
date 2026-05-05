#!/usr/bin/env python3
"""
AI Service Integration for ViFake Analytics
Service layer for AI model communication

Tuân thủ Privacy-by-Design:
- Zero-trust RAM processing
- Service-to-service communication
- No persistent storage of harmful content
"""

import asyncio
import logging
import json
import numpy as np
from typing import Dict, List, Optional, Union
from datetime import datetime
import aiohttp
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIServiceIntegration:
    """Integration layer for AI services"""
    
    def __init__(self):
        self.vision_service_url = "http://localhost:8001"
        self.nlp_service_url = "http://localhost:8002"
        self.fusion_service_url = "http://localhost:8003"
        
        # Service availability cache
        self.service_status = {}
        self.last_health_check = datetime.now()
        
        logger.info("🤖 AI Service Integration initialized")
    
    async def check_service_health(self) -> Dict[str, bool]:
        """Check health of all AI services"""
        services = {
            "vision": self.vision_service_url,
            "nlp": self.nlp_service_url,
            "fusion": self.fusion_service_url
        }
        
        health_status = {}
        
        async with aiohttp.ClientSession() as session:
            for service_name, service_url in services.items():
                try:
                    async with session.get(f"{service_url}/health", timeout=5) as response:
                        health_status[service_name] = response.status == 200
                except Exception as e:
                    logger.warning(f"⚠️ {service_name} service health check failed: {e}")
                    health_status[service_name] = False
        
        self.service_status = health_status
        self.last_health_check = datetime.now()
        
        return health_status
    
    async def call_vision_analysis(self, image_path: str, image_data: Optional[bytes] = None) -> Dict:
        """Call CLIP vision analysis service"""
        logger.info(f"🖼️ Calling vision analysis for: {image_path}")
        
        try:
            # Check service health
            if not self.service_status.get("vision", True):
                await self.check_service_health()
            
            if not self.service_status.get("vision", False):
                logger.warning("⚠️ Vision service unavailable, using fallback")
                return self._fallback_vision_analysis(image_path)
            
            async with aiohttp.ClientSession() as session:
                # Prepare request data
                if image_data:
                    # Send image data directly
                    data = aiohttp.FormData()
                    data.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
                    
                    async with session.post(f"{self.vision_service_url}/analyze", data=data) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(f"✅ Vision analysis completed: {result.get('risk_level', 'UNKNOWN')}")
                            return result
                        else:
                            logger.error(f"❌ Vision service error: {response.status}")
                            return self._fallback_vision_analysis(image_path)
                else:
                    # Send image path
                    payload = {"image_path": image_path}
                    
                    async with session.post(f"{self.vision_service_url}/analyze_path", json=payload) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(f"✅ Vision analysis completed: {result.get('risk_level', 'UNKNOWN')}")
                            return result
                        else:
                            logger.error(f"❌ Vision service error: {response.status}")
                            return self._fallback_vision_analysis(image_path)
        
        except Exception as e:
            logger.error(f"❌ Vision analysis failed: {e}")
            return self._fallback_vision_analysis(image_path)
    
    async def call_nlp_analysis(self, text: str, language: str = "vi") -> Dict:
        """Call PhoBERT NLP analysis service"""
        logger.info(f"📝 Calling NLP analysis for text: {text[:50]}...")
        
        try:
            # Check service health
            if not self.service_status.get("nlp", True):
                await self.check_service_health()
            
            if not self.service_status.get("nlp", False):
                logger.warning("⚠️ NLP service unavailable, using fallback")
                return self._fallback_nlp_analysis(text)
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "text": text,
                    "language": language,
                    "return_probabilities": True
                }
                
                async with session.post(f"{self.nlp_service_url}/predict", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ NLP analysis completed: {result.get('prediction', 'UNKNOWN')}")
                        return result
                    else:
                        logger.error(f"❌ NLP service error: {response.status}")
                        return self._fallback_nlp_analysis(text)
        
        except Exception as e:
            logger.error(f"❌ NLP analysis failed: {e}")
            return self._fallback_nlp_analysis(text)
    
    async def call_fusion_model(self, vision_result: Dict, nlp_result: Dict, metadata: Dict = None) -> Dict:
        """Call XGBoost fusion model service"""
        logger.info("🧠 Calling fusion model for multi-modal analysis")
        
        try:
            # Check service health
            if not self.service_status.get("fusion", True):
                await self.check_service_health()
            
            if not self.service_status.get("fusion", False):
                logger.warning("⚠️ Fusion service unavailable, using fallback")
                return self._fallback_fusion_analysis(vision_result, nlp_result, metadata)
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "vision_result": vision_result,
                    "nlp_result": nlp_result,
                    "metadata": metadata or {}
                }
                
                async with session.post(f"{self.fusion_service_url}/predict", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Fusion analysis completed: {result.get('prediction', 'UNKNOWN')}")
                        return result
                    else:
                        logger.error(f"❌ Fusion service error: {response.status}")
                        return self._fallback_fusion_analysis(vision_result, nlp_result, metadata)
        
        except Exception as e:
            logger.error(f"❌ Fusion analysis failed: {e}")
            return self._fallback_fusion_analysis(vision_result, nlp_result, metadata)
    
    async def batch_analyze(self, items: List[Dict]) -> List[Dict]:
        """Batch analyze multiple items"""
        logger.info(f"📊 Batch analyzing {len(items)} items")
        
        results = []
        
        # Process in parallel with concurrency limit
        semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
        
        async def analyze_single(item):
            async with semaphore:
                try:
                    # Extract data
                    text = item.get("text", "")
                    image_path = item.get("image_path", "")
                    metadata = item.get("metadata", {})
                    
                    # Run analyses in parallel
                    vision_task = None
                    nlp_task = None
                    
                    if image_path:
                        vision_task = asyncio.create_task(self.call_vision_analysis(image_path))
                    
                    if text:
                        nlp_task = asyncio.create_task(self.call_nlp_analysis(text))
                    
                    # Wait for analyses
                    vision_result = await vision_task if vision_task else {}
                    nlp_result = await nlp_task if nlp_task else {}
                    
                    # Fusion analysis
                    fusion_result = await self.call_fusion_model(vision_result, nlp_result, metadata)
                    
                    return {
                        "item_id": item.get("id"),
                        "vision_result": vision_result,
                        "nlp_result": nlp_result,
                        "fusion_result": fusion_result,
                        "success": True
                    }
                    
                except Exception as e:
                    logger.error(f"❌ Batch item analysis failed: {e}")
                    return {
                        "item_id": item.get("id"),
                        "error": str(e),
                        "success": False
                    }
        
        # Run all analyses
        tasks = [analyze_single(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        successful_results = [r for r in results if isinstance(r, dict) and r.get("success")]
        
        logger.info(f"✅ Batch analysis completed: {len(successful_results)}/{len(items)} successful")
        return successful_results
    
    def _fallback_vision_analysis(self, image_path: str) -> Dict:
        """Fallback vision analysis when service is unavailable"""
        logger.info("🔄 Using fallback vision analysis")
        
        # Simple rule-based analysis
        filename = Path(image_path).name.lower()
        
        # Risk indicators based on filename
        risk_indicators = ["scam", "fake", "virus", "hack", "phish", "malware"]
        risk_score = sum(1.0 for indicator in risk_indicators if indicator in filename) / len(risk_indicators)
        
        return {
            "image_path": image_path,
            "combined_risk_score": risk_score,
            "safety_score": 1.0 - risk_score,
            "risk_level": "HIGH" if risk_score > 0.5 else "LOW",
            "is_safe": risk_score < 0.3,
            "requires_review": risk_score > 0.2,
            "analysis_method": "fallback_rule_based",
            "confidence": 0.7
        }
    
    def _fallback_nlp_analysis(self, text: str) -> Dict:
        """Fallback NLP analysis when service is unavailable"""
        logger.info("🔄 Using fallback NLP analysis")
        
        # Simple keyword-based analysis
        scam_keywords = ["free", "robux", "click", "link", "verify", "password", "account", "gift"]
        toxic_keywords = ["stupid", "idiot", "hate", "kill", "die"]
        
        scam_score = sum(1.0 for kw in scam_keywords if kw.lower() in text.lower()) / len(scam_keywords)
        toxic_score = sum(1.0 for kw in toxic_keywords if kw.lower() in text.lower()) / len(toxic_keywords)
        
        # Determine prediction
        if scam_score > 0.3:
            prediction = "FAKE_SCAM"
            confidence = min(scam_score + 0.5, 0.9)
        elif toxic_score > 0.2:
            prediction = "FAKE_TOXIC"
            confidence = min(toxic_score + 0.5, 0.9)
        else:
            prediction = "SAFE"
            confidence = 0.8
        
        return {
            "text": text,
            "prediction": prediction,
            "confidence": confidence,
            "probabilities": {
                "SAFE": 0.8 if prediction == "SAFE" else 0.1,
                "FAKE_TOXIC": 0.1 if prediction == "SAFE" else 0.2,
                "FAKE_SCAM": 0.1 if prediction == "SAFE" else 0.6,
                "FAKE_MISINFO": 0.0
            },
            "risk_level": "HIGH" if prediction != "SAFE" else "LOW",
            "is_safe": prediction == "SAFE",
            "requires_review": prediction != "SAFE",
            "analysis_method": "fallback_keyword_based"
        }
    
    def _fallback_fusion_analysis(self, vision_result: Dict, nlp_result: Dict, metadata: Dict = None) -> Dict:
        """Fallback fusion analysis when service is unavailable"""
        logger.info("🔄 Using fallback fusion analysis")
        
        # Simple weighted fusion
        vision_safe = vision_result.get("is_safe", True)
        nlp_safe = nlp_result.get("is_safe", True)
        vision_risk = vision_result.get("combined_risk_score", 0.0)
        nlp_confidence = nlp_result.get("confidence", 0.5)
        
        # Fusion logic
        if vision_safe and nlp_safe:
            prediction = "SAFE"
            confidence = 0.85
        elif vision_risk > 0.7 or not nlp_safe:
            prediction = "FAKE_SCAM"
            confidence = max(vision_risk, 1.0 - nlp_confidence)
        else:
            prediction = "FAKE_TOXIC"
            confidence = 0.6
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "probabilities": {
                "SAFE": 0.8 if prediction == "SAFE" else 0.1,
                "FAKE_TOXIC": 0.1 if prediction == "SAFE" else 0.3,
                "FAKE_SCAM": 0.1 if prediction == "SAFE" else 0.5,
                "FAKE_MISINFO": 0.0
            },
            "risk_level": "HIGH" if prediction != "SAFE" else "LOW",
            "is_safe": prediction == "SAFE",
            "requires_review": prediction != "SAFE",
            "fusion_method": "fallback_weighted",
            "feature_count": 10
        }
    
    async def get_service_metrics(self) -> Dict:
        """Get service performance metrics"""
        await self.check_service_health()
        
        metrics = {
            "service_status": self.service_status,
            "last_health_check": self.last_health_check.isoformat(),
            "service_urls": {
                "vision": self.vision_service_url,
                "nlp": self.nlp_service_url,
                "fusion": self.fusion_service_url
            }
        }
        
        return metrics

# Global service instance
_ai_service = None

def get_ai_service() -> AIServiceIntegration:
    """Get singleton AI service instance"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIServiceIntegration()
    return _ai_service

# Convenience functions
async def analyze_content_vision(image_path: str) -> Dict:
    """Analyze content with vision model"""
    service = get_ai_service()
    return await service.call_vision_analysis(image_path)

async def analyze_content_nlp(text: str) -> Dict:
    """Analyze content with NLP model"""
    service = get_ai_service()
    return await service.call_nlp_analysis(text)

async def analyze_content_fusion(vision_result: Dict, nlp_result: Dict, metadata: Dict = None) -> Dict:
    """Analyze content with fusion model"""
    service = get_ai_service()
    return await service.call_fusion_model(vision_result, nlp_result, metadata)

if __name__ == "__main__":
    # Test AI service integration
    async def test_ai_service():
        service = get_ai_service()
        
        # Test health check
        health = await service.check_service_health()
        print(f"Service health: {health}")
        
        # Test vision analysis
        vision_result = await service.call_vision_analysis("test_image.jpg")
        print(f"Vision result: {vision_result}")
        
        # Test NLP analysis
        nlp_result = await service.call_nlp_analysis("This is a test message")
        print(f"NLP result: {nlp_result}")
        
        # Test fusion
        fusion_result = await service.call_fusion_model(vision_result, nlp_result)
        print(f"Fusion result: {fusion_result}")
    
    # Run test
    asyncio.run(test_ai_service())
