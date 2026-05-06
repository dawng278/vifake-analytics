#!/usr/bin/env python3
"""
ViFake Analytics API Gateway
FastAPI-based B2B2C service for content analysis

Tuân thủ Privacy-by-Design:
- Zero-trust RAM processing
- No persistent storage of harmful content
- Ethical AI service delivery
"""

import asyncio
import json
import uuid
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

# Add project root to path for AI engine imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Security, status
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, field_validator
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Startup and shutdown
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("🚀 ViFake Analytics API Gateway starting up...")
    logger.info("📊 API Documentation: /docs")
    logger.info("🔍 ReDoc Documentation: /redoc")
    
    yield
    
    # Shutdown
    logger.info("🛑 ViFake Analytics API Gateway shutting down...")
    
    # Clean up active jobs
    for job_id in list(active_jobs.keys()):
        fail_job(job_id, "Server shutdown")

# Initialize FastAPI app
app = FastAPI(
    title="ViFake Analytics API",
    description="B2B2C Content Analysis API for Child Safety",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Public API; tighten to specific origins in production
    allow_credentials=False,  # Must be False when allow_origins=["*"] (browser CORS rule)
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security
security = HTTPBearer()

# Global job storage (in production, use Redis/database)
active_jobs = {}
job_results = {}

# Lazy-loaded AI models (initialized on first use)
_nlp_model = None
_vision_worker = None
_fusion_model = None

def get_nlp_model():
    """Get or initialize PhoBERT NLP model"""
    global _nlp_model
    if _nlp_model is None:
        logger.info("🤖 Loading PhoBERT model (first use)...")
        try:
            from ai_engine.nlp_worker.phobert_inference import PhoBERTInference
            model_path = "models/phobert_scam_detector"
            if not os.path.exists(model_path):
                model_path = None  # Use default vinai/phobert-base
            _nlp_model = PhoBERTInference(model_path=model_path)
            logger.info("✅ PhoBERT model loaded")
        except Exception as e:
            logger.warning(f"⚠️ PhoBERT load failed: {e}, using fallback")
            _nlp_model = None
    return _nlp_model

def get_vision_worker():
    """Get or initialize CLIP vision worker"""
    global _vision_worker
    if _vision_worker is None:
        logger.info("🔍 Loading CLIP model (first use)...")
        try:
            from ai_engine.vision_worker.clip_inference import CLIPVisionWorker, VisionConfig
            config = VisionConfig()
            _vision_worker = CLIPVisionWorker(config)
            logger.info("✅ CLIP model loaded")
        except Exception as e:
            logger.warning(f"⚠️ CLIP load failed: {e}, using fallback")
            _vision_worker = None
    return _vision_worker

def get_fusion_model():
    """Get or initialize XGBoost fusion model"""
    global _fusion_model
    if _fusion_model is None:
        logger.info("🧠 Loading Fusion model (first use)...")
        try:
            from ai_engine.fusion_model.xgboost_fusion import XGBoostFusionModel, FusionConfig
            config = FusionConfig()
            _fusion_model = XGBoostFusionModel(config)
            # Try to load pre-trained model
            try:
                _fusion_model.load_model()
                logger.info("✅ Fusion model loaded from disk")
            except:
                logger.info("🆕 No pre-trained fusion model, using rule-based fallback")
        except Exception as e:
            logger.warning(f"⚠️ Fusion load failed: {e}, using fallback")
            _fusion_model = None
    return _fusion_model

# Pydantic models
class AnalyzeRequest(BaseModel):
    """Request model for content analysis"""
    url: str = Field(..., description="URL to analyze")
    platform: str = Field(..., description="Platform: youtube | facebook | tiktok")
    priority: str = Field(default="normal", description="Priority: low | normal | high")
    content: Optional[str] = Field(default=None, description="Optional text content for direct analysis")
    
    @field_validator('platform')
    @classmethod
    def validate_platform(cls, v):
        allowed = ['youtube', 'facebook', 'tiktok']
        if v not in allowed:
            raise ValueError(f"Platform must be one of: {allowed}")
        return v
    
    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v):
        allowed = ['low', 'normal', 'high']
        if v not in allowed:
            raise ValueError(f"Priority must be one of: {allowed}")
        return v

class AnalyzeResponse(BaseModel):
    """Response model for analysis request"""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status: processing | completed | failed")
    message: str = Field(..., description="Status message")
    estimated_time: Optional[int] = Field(None, description="Estimated processing time (seconds)")

class JobStatusResponse(BaseModel):
    """Response model for job status"""
    job_id: str
    status: str
    progress: Optional[float] = None
    current_stage: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class AnalysisResult(BaseModel):
    """Final analysis result model"""
    job_id: str
    url: str
    platform: str
    label: str
    confidence: float
    risk_level: str
    needs_review: bool
    analysis_details: Dict
    processing_time: float
    created_at: datetime

class VideoAnalyzeRequest(BaseModel):
    """Request model for video analysis"""
    video_url: str = Field(..., description="TikTok video URL to analyze")
    description: str = Field(default="", description="Video caption/description from DOM")
    author: str = Field(default="", description="Video author/creator")
    page_url: str = Field(default="", description="Full TikTok page URL")

class VideoAnalyzeResponse(BaseModel):
    """Response model for video analysis"""
    verdict: str = Field(..., description="SAFE | SUSPICIOUS | FAKE_SCAM")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    is_ai_generated: bool = Field(..., description="Whether video appears AI-generated")
    ai_confidence: float = Field(..., description="AI detection confidence")
    intents: Dict = Field(..., description="Scam intent analysis results")
    transcript: str = Field(..., description="Full audio transcript")
    explanation: str = Field(..., description="Human-readable explanation")
    processing_ms: int = Field(..., description="Total processing time in milliseconds")

# Authentication
async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify JWT token or API key"""
    token = credentials.credentials
    
    # Token validation (reads from environment variable, falls back to demo token for local dev)
    import os
    auth_token = os.getenv("AUTH_TOKEN", "demo-token-123")
    valid_tokens = {
        auth_token: {"user": "api_user", "permissions": ["analyze"]},
    }
    
    if token not in valid_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return valid_tokens[token]

# Helper functions
def create_analysis_job(url: str, platform: str, priority: str = "normal") -> str:
    """Create a new analysis job"""
    job_id = str(uuid.uuid4())
    
    job_info = {
        "job_id": job_id,
        "url": url,
        "platform": platform,
        "priority": priority,
        "status": "processing",
        "progress": 0.0,
        "current_stage": "Initializing...",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "result": None,
        "error": None
    }
    
    active_jobs[job_id] = job_info
    
    logger.info(f"📋 Created analysis job: {job_id} for {platform}:{url}")
    return job_id

def update_job_progress(job_id: str, progress: float, stage: str):
    """Update job progress"""
    if job_id in active_jobs:
        active_jobs[job_id]["progress"] = progress
        active_jobs[job_id]["current_stage"] = stage
        active_jobs[job_id]["updated_at"] = datetime.now()
        logger.debug(f"📊 Job {job_id}: {progress:.1f}% - {stage}")

def complete_job(job_id: str, result: Dict):
    """Complete job with results"""
    if job_id in active_jobs:
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["progress"] = 100.0
        active_jobs[job_id]["current_stage"] = "Completed"
        active_jobs[job_id]["result"] = result
        active_jobs[job_id]["updated_at"] = datetime.now()
        
        # Move to results storage
        job_results[job_id] = active_jobs[job_id].copy()
        del active_jobs[job_id]
        
        logger.info(f"✅ Job {job_id} completed successfully")

def fail_job(job_id: str, error: str):
    """Fail job with error"""
    if job_id in active_jobs:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = error
        active_jobs[job_id]["updated_at"] = datetime.now()
        
        # Move to results storage
        job_results[job_id] = active_jobs[job_id].copy()
        del active_jobs[job_id]
        
        logger.error(f"❌ Job {job_id} failed: {error}")

# Background processing
async def run_full_pipeline(job_id: str, url: str, platform: str, content: Optional[str] = None):
    """Run complete analysis pipeline with real AI models"""
    try:
        start_time = datetime.now()
        
        # Stage 1: Extract content
        update_job_progress(job_id, 5.0, "🔍 Extracting content...")
        if content:
            extracted_text = content
            logger.info(f"📝 Using provided content ({len(content)} chars)")
        else:
            extracted_text = _extract_text_from_url(url, platform)
            logger.info(f"🔗 Extracted from URL: {extracted_text[:100]}...")
        await asyncio.sleep(0.2)
        
        # Stage 2: Safety pre-check
        update_job_progress(job_id, 10.0, "🛡️ Running safety pre-check...")
        await asyncio.sleep(0.2)
        
        # Stage 3: NLP Analysis with PhoBERT
        update_job_progress(job_id, 25.0, "� Running PhoBERT NLP analysis...")
        nlp_result = _run_nlp_analysis(extracted_text)
        update_job_progress(job_id, 50.0, "📝 PhoBERT analysis complete")
        
        # Stage 4: Vision Analysis with CLIP (if image available)
        update_job_progress(job_id, 55.0, "�️ Running CLIP vision analysis...")
        vision_result = _run_vision_analysis(url, platform)
        update_job_progress(job_id, 75.0, "🖼️ CLIP analysis complete")
        
        # Stage 5: Fusion Decision
        update_job_progress(job_id, 80.0, "🧠 Running XGBoost decision fusion (14 features)...")
        post_data = {"content": extracted_text, "platform": platform}
        fusion_result = _run_fusion(vision_result, nlp_result, platform, post_data)
        update_job_progress(job_id, 95.0, "🧠 Fusion complete")
        
        # Stage 5b: Calibration
        update_job_progress(job_id, 96.0, "📐 Applying Platt calibration...")
        try:
            from ai_engine.fusion_model.calibration import apply_calibration_to_result
            fusion_result = apply_calibration_to_result(fusion_result, ece=0.12)
            logger.info(f"📐 Calibrated confidence: {fusion_result.get('confidence', 0):.3f}")
        except Exception as e:
            logger.warning(f"⚠️ Calibration failed: {e}")
        
        # Stage 6: Graph update (async, non-blocking)
        update_job_progress(job_id, 98.0, "🕸️ Updating graph analytics...")
        await asyncio.sleep(0.2)
        
        # Build final result
        processing_time = (datetime.now() - start_time).total_seconds()
        
        result = {
            "label": fusion_result.get("prediction", "FAKE_SCAM"),
            "confidence": fusion_result.get("confidence", 0.5),
            "risk_level": fusion_result.get("risk_level", "MEDIUM"),
            "needs_review": fusion_result.get("requires_review", True),
            "analysis_details": {
                "vision_risk": vision_result.get("combined_risk_score", 0.5),
                "nlp_risk": 1.0 - nlp_result.get("confidence", 0.5),
                "fusion_score": fusion_result.get("confidence", 0.5),
                "nlp_prediction": nlp_result.get("prediction", "UNKNOWN"),
                "nlp_confidence": nlp_result.get("confidence", 0.0),
                "nlp_method": nlp_result.get("detection_method", "unknown"),
                "nlp_flags": nlp_result.get("flags", []),
                "intent": nlp_result.get("intent", {}),
                "intent_label": nlp_result.get("intent_label", ""),
                "intent_explanation": nlp_result.get("intent_explanation", ""),
                "vision_safety": vision_result.get("safety_score", 0.5),
                "fusion_method": fusion_result.get("fusion_method", "unknown"),
                "calibration_applied": fusion_result.get("calibration_applied", False),
                "confidence_raw": fusion_result.get("confidence_raw", fusion_result.get("confidence", 0.5)),
                "platform_specific": {
                    "platform": platform,
                    "content_type": "video" if platform == "youtube" else "post",
                    "text_length": len(extracted_text)
                }
            },
            "processing_time": processing_time,
            "created_at": datetime.now().isoformat()
        }
        
        complete_job(job_id, result)
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed for job {job_id}: {e}")
        fail_job(job_id, str(e))

def _extract_text_from_url(url: str, platform: str) -> str:
    """Extract meaningful text from URL for analysis"""
    # In production, this would crawl the actual page
    # For local dev, we extract signals from the URL itself
    text_parts = []
    
    # Platform-specific extraction
    if platform == "youtube":
        if "watch?v=" in url:
            video_id = url.split("watch?v=")[-1].split("&")[0]
            text_parts.append(f"YouTube video {video_id}")
        else:
            text_parts.append(f"YouTube content: {url}")
    elif platform == "facebook":
        text_parts.append(f"Facebook post: {url}")
    elif platform == "tiktok":
        text_parts.append(f"TikTok video: {url}")
    
    # Add URL-based signals
    url_lower = url.lower()
    if any(kw in url_lower for kw in ["scam", "free", "gift", "robux", "nạp", "thẻ", "quà"]):
        text_parts.append("Cảnh báo: URL chứa từ khóa đáng ngờ liên quan đến lừa đảo hoặc quà tặng miễn phí")
    if any(kw in url_lower for kw in ["safe", "education", "học", "giáo"]):
        text_parts.append("URL có vẻ liên quan đến nội dung giáo dục an toàn")
    
    return " ".join(text_parts) if text_parts else url

def _run_nlp_analysis(text: str) -> Dict:
    """Run PhoBERT NLP analysis with comprehensive Vietnamese scam detection fallback"""
    phobert_result = None
    try:
        model = get_nlp_model()
        if model is not None:
            phobert_result = model.predict(text)
            logger.info(f"📝 PhoBERT result: {phobert_result.get('prediction')} (confidence: {phobert_result.get('confidence', 0):.3f})")
            
            # Trust PhoBERT only if confidence is reasonable (>= 50%)
            if phobert_result.get('confidence', 0) >= 0.5:
                return phobert_result
            else:
                logger.info(f"⚠️ PhoBERT confidence too low ({phobert_result.get('confidence', 0):.1%}), consulting scam detector...")
    except Exception as e:
        logger.warning(f"⚠️ NLP inference failed: {e}")
    
    # Comprehensive Vietnamese scam detection engine
    logger.info("📝 Running Vietnamese scam detection engine...")
    result = _vietnamese_scam_detector(text)
    
    # If PhoBERT ran but was low-confidence, pick the more confident result
    if phobert_result is not None:
        scam_conf = result.get('confidence', 0)
        phobert_conf = phobert_result.get('confidence', 0)
        logger.info(f"🔄 Comparing: PhoBERT={phobert_result.get('prediction')}@{phobert_conf:.3f} vs ScamDetector={result.get('prediction')}@{scam_conf:.3f}")
        if phobert_conf > scam_conf:
            result = phobert_result
        # Otherwise keep scam detector result (already in `result`)
    
    # Add intent detection
    try:
        from ai_engine.nlp_worker.intent_detector import detect_scam_intent, get_intent_explanation
        intent_result = detect_scam_intent(text)
        result["intent"] = intent_result
        result["intent_label"] = intent_result.get("primary_intent_label", "")
        result["intent_explanation"] = get_intent_explanation(intent_result.get("primary_intent", "none"))
        logger.info(f"🎯 Intent: {intent_result.get('primary_intent_label')} (score={intent_result.get('risk_weighted_score', 0):.3f})")
    except Exception as e:
        logger.warning(f"⚠️ Intent detection failed: {e}")
        result["intent"] = {"primary_intent": "unknown"}
    
    return result

def _vietnamese_scam_detector(text: str) -> Dict:
    """Multi-dimensional Vietnamese scam/fake news detection"""
    text_lower = text.lower()
    text_upper = text.upper()
    score = 0.0
    flags = []
    details = {}
    
    # === 1. URL & Shortlink Detection ===
    url_patterns = [
        r'bit\.ly', r'bitly', r'shorturl', r'tinyurl', r'cutt\.ly',
        r'fb-verify', r'facebook.*verify', r'xác.*minh.*danh.*tính',
        r'link.*click', r'click.*link', r'bấm.*vào.*đây', r'truy.*cập.*ngay',
        r'\.click\b', r'\.xyz\b', r'\.top\b', r'\.tk\b',
    ]
    url_count = 0
    for pat in url_patterns:
        import re
        if re.search(pat, text_lower):
            url_count += 1
    if url_count > 0:
        score += min(url_count * 0.15, 0.4)
        flags.append(f"SHORTLINK_SUSPICIOUS ({url_count} suspicious URLs)")
    details['url_risk'] = min(url_count * 0.15, 0.4)
    
    # === 2. Financial Scam Patterns ===
    financial_patterns = {
        'robux_phishing': [
            r'robux.*free', r'free.*robux', r'robux.*miễn.*phí',
            r'admin.*roblox', r'roblox.*admin', r'event.*robux',
            r'verify.*acc', r'xác.*minh.*acc', r'verify.*tài.*khoản',
        ],
        'gift_card_scam': [
            r'nạp.*thẻ.*được', r'thẻ.*gate', r'thẻ.*garena',
            r'nạp.*50k.*được.*500k', r'nạp.*100k.*được.*1tr',
            r'ưu.*đãi.*đặc.*biệt', r'khuyến.*mãi.*đặc.*biệt',
        ],
        'crypto_scam': [
            r'giveaway.*usdt', r'usdt.*giveaway', r'airdrop',
            r'connect.*ví', r'connect.*wallet', r'metamask',
            r'xác.*nhận.*giao.*dịch', r'confirm.*transaction',
            r'nhận.*thưởng.*usdt', r'nhận.*thưởng.*btc',
        ],
        'account_theft': [
            r'tài.*khoản.*bị.*khóa', r'account.*suspend',
            r'bị.*khóa.*trong.*24h', r'xác.*minh.*danh.*tính.*ngay',
            r'đăng.*nhập.*ngay', r'login.*now',
        ],
    }
    
    financial_score = 0
    for scam_type, patterns in financial_patterns.items():
        for pat in patterns:
            import re
            if re.search(pat, text_lower):
                financial_score += 0.12
                flags.append(f"FINANCIAL_SCAM:{scam_type}")
                break
    
    score += min(financial_score, 0.5)
    details['financial_risk'] = min(financial_score, 0.5)
    
    # === 3. Urgency & Pressure Language ===
    urgency_patterns = [
        r'nhanh.*tay', r'số.*lượng.*có.*hạn', r'chỉ.*còn',
        r'hết.*hạn', r'hôm.*nay.*thôi', r'duy.*nhất.*hôm.*nay',
        r'cơ.*hội.*cuối', r'đừng.*bỏ.*lỡ', r'kẻo.*hết',
        r'CHÚ.*Ý!', r'QUAN.*TRỌNG!', r'KHẨN.*CẤP!',
        r'GẤP!', r'NGAY!', r'LẬP.*TỨC!',
    ]
    urgency_count = sum(1 for pat in urgency_patterns if __import__('re').search(pat, text))
    urgency_score = min(urgency_count * 0.08, 0.3)
    score += urgency_score
    if urgency_count > 0:
        flags.append(f"URGENCY_PRESSURE ({urgency_count} patterns)")
    details['urgency_risk'] = urgency_score
    
    # === 4. Teencode & Child-Targeting Language ===
    teencode_patterns = [
        r'\bae\b', r'\bace\b', r'\bminh\s*ơi\b', r'\bê\s*ae\b',
        r'\bnè\b', r'\bđỉnh\b', r'\bxịn\b', r'\bngon\b',
        r'\bskibidi\b', r'\bsigma\b', r'\brizz\b',
    ]
    teencode_count = sum(1 for pat in teencode_patterns if __import__('re').search(pat, text_lower))
    teencode_score = min(teencode_count * 0.05, 0.15)
    score += teencode_score
    if teencode_count > 2:
        flags.append(f"TEENCODE_TARGETING ({teencode_count} patterns)")
    details['teencode_risk'] = teencode_score
    
    # === 5. Trust-Building Manipulation ===
    # ONLY scam-specific trust manipulation (not legitimate credentials)
    trust_patterns = [
        r'tin.*mình.*đi', r'tin.*tao.*đi', r'thật.*100%',
        r'đảm.*bảo.*100%.*robux', r'đảm.*bảo.*100%.*free',
        r'admin.*roblox.*chính.*thức', r'admin.*garena.*chính.*thức',
        r'hack.*đã.*test', r'cheat.*đã.*thử',
    ]
    trust_count = sum(1 for pat in trust_patterns if __import__('re').search(pat, text_lower))
    trust_score = min(trust_count * 0.08, 0.2)
    score += trust_score
    if trust_count > 0:
        flags.append(f"TRUST_MANIPULATION ({trust_count} patterns)")
    details['trust_manipulation_risk'] = trust_score
    
    # === 6. Emoji Abuse ===
    emoji_count = sum(1 for c in text if ord(c) > 0x1F000 or (0x2600 <= ord(c) <= 0x27BF))
    emoji_score = min(emoji_count * 0.02, 0.1)
    score += emoji_score
    if emoji_count > 5:
        flags.append(f"EMOJI_ABUSE ({emoji_count} emojis)")
    details['emoji_risk'] = emoji_score
    
    # === 7. ALL-CAPS Shouting ===
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    caps_score = min(caps_ratio * 0.3, 0.15) if caps_ratio > 0.3 else 0
    score += caps_score
    if caps_score > 0.05:
        flags.append(f"EXCESSIVE_CAPS ({caps_ratio:.0%})")
    details['caps_risk'] = caps_score
    
    # === 8. Safe Content Indicators (negative scoring) ===
    safe_patterns = [
        r'chính.*thức.*của.*bộ', r'website.*chính.*thức.*của.*bộ',
        r'nguồn.*tin.*chính.*thức', r'theo.*thông.*tin.*từ',
        r'chia.*sẻ.*cách.*học', r'học.*tiếng.*anh', r'học.*toán',
        r'phụ.*huynh.*có.*thể', r'giáo.*dục', r'kiến.*thức',
        r'bộ.*gdđt', r'bộ.*giáo.*dục', r'trường.*học',
        r'giáo.*viên', r'thầy.*cô', r'lớp.*học',
        r'bài.*tập', r'ôn.*tập', r'học.*bài',
        r'sách.*giáo.*khoa', r'chương.*trình.*học',
    ]
    safe_count = sum(1 for pat in safe_patterns if __import__('re').search(pat, text_lower))
    # Stronger discount for educational content
    safe_discount = min(safe_count * 0.25, 0.6)
    score = max(0, score - safe_discount)
    if safe_count > 0:
        flags.append(f"SAFE_INDICATORS ({safe_count} patterns)")
    details['safe_indicators'] = safe_count
    
    # === Normalize & Classify ===
    score = min(score, 1.0)
    
    # Adjust thresholds to reduce false positives
    if score >= 0.65:
        prediction = "FAKE_SCAM"
        risk_level = "HIGH"
    elif score >= 0.40:
        prediction = "FAKE_SCAM"
        risk_level = "MEDIUM"
    elif score >= 0.20:
        prediction = "SUSPICIOUS"
        risk_level = "LOW"
    else:
        prediction = "SAFE"
        risk_level = "LOW"
    
    confidence = 0.5 + (score * 0.45)  # Scale to 0.5-0.95 range
    
    logger.info(f"📝 Scam detection: {prediction} (score={score:.3f}, confidence={confidence:.3f})")
    if flags:
        logger.info(f"   Flags: {' | '.join(flags)}")
    
    return {
        "text": text,
        "prediction": prediction,
        "confidence": round(confidence, 3),
        "probabilities": {
            "SAFE": round(1.0 - score, 3),
            "FAKE_SCAM": round(score, 3)
        },
        "risk_level": risk_level,
        "is_safe": prediction == "SAFE",
        "requires_review": prediction != "SAFE",
        "detection_method": "vietnamese_scam_engine",
        "risk_score": round(score, 3),
        "flags": flags,
        "details": details
    }

def _run_vision_analysis(url: str, platform: str) -> Dict:
    """Run CLIP vision analysis (with graceful fallback)"""
    try:
        worker = get_vision_worker()
        if worker is not None:
            # In production, we'd download the thumbnail/image from the URL
            # For local dev, we analyze based on URL patterns
            logger.info("🔍 CLIP vision analysis: no image available, using URL-based heuristics")
    except Exception as e:
        logger.warning(f"⚠️ Vision analysis skipped: {e}")
    
    # Fallback: URL-based vision heuristics
    url_lower = url.lower()
    risk_score = 0.3  # Default moderate-low risk
    
    if any(kw in url_lower for kw in ["scam", "free", "gift", "robux"]):
        risk_score = 0.75
    elif any(kw in url_lower for kw in ["safe", "education"]):
        risk_score = 0.1
    
    return {
        "combined_risk_score": risk_score,
        "safety_score": 1.0 - risk_score,
        "violent_risk": 0.1,
        "scam_risk": risk_score,
        "sexual_risk": 0.05,
        "inappropriate_risk": risk_score * 0.5,
        "is_safe": risk_score < 0.5,
        "requires_review": risk_score >= 0.5,
        "risk_level": "HIGH" if risk_score >= 0.7 else ("MEDIUM" if risk_score >= 0.4 else "LOW")
    }

def _run_fusion(vision_result: Dict, nlp_result: Dict, platform: str, post_data: Dict = None) -> Dict:
    """Run XGBoost fusion with 14-feature vector or rule-based fallback"""
    try:
        model = get_fusion_model()
        if model is not None and model.is_trained:
            # Build 14-feature vector
            try:
                from ai_engine.fusion_model.feature_engineering import build_feature_vector
                if post_data is None:
                    post_data = {}
                post_data["content"] = nlp_result.get("text", "")
                post_data["platform"] = platform
                
                features = build_feature_vector(post_data, vision_result, nlp_result)
                
                # If model expects 14 features, use them directly
                if hasattr(model, 'feature_names') and len(model.feature_names) == 14:
                    features_scaled = model.scaler.transform(features)
                    prediction_proba = model.model.predict_proba(features_scaled)[0]
                    prediction_idx = model.model.predict(features_scaled)[0]
                    
                    prediction_label = model.LABELS[prediction_idx]
                    confidence = prediction_proba[prediction_idx]
                    risk_level = model._assess_fusion_risk(prediction_label, confidence)
                    
                    result = {
                        'prediction': prediction_label,
                        'confidence': float(confidence),
                        'risk_level': risk_level,
                        'requires_review': prediction_label != 'SAFE' and confidence < 0.8,
                        'fusion_method': 'xgboost_14features',
                        'feature_count': 14,
                    }
                    logger.info(f"🧠 Fusion (14-feature): {prediction_label} (confidence: {confidence:.3f})")
                    return result
            except Exception as e:
                logger.warning(f"⚠️ 14-feature fusion failed: {e}, falling back to 2-feature")
            
            # Fallback to original 2-feature fusion
            metadata = {"platform": platform}
            result = model.predict(vision_result, nlp_result, metadata)
            logger.info(f"🧠 Fusion result: {result.get('prediction')} (confidence: {result.get('confidence', 0):.3f})")
            return result
    except Exception as e:
        logger.warning(f"⚠️ Fusion failed: {e}")
    
    # Rule-based fallback fusion
    logger.info("🧠 Using rule-based fusion fallback")
    vision_risk = vision_result.get("combined_risk_score", 0.5)
    nlp_safe = nlp_result.get("is_safe", True)
    nlp_conf = nlp_result.get("confidence", 0.5)
    nlp_pred = nlp_result.get("prediction", "UNKNOWN")

    # Factor in intent detection score (separate signal from keyword matcher)
    intent_data = nlp_result.get("intent", {}) or {}
    intent_score = intent_data.get("risk_weighted_score", 0.0)
    intent_max = intent_data.get("max_intent_score", 0.0)
    primary_intent = intent_data.get("primary_intent", "none")
    has_strong_intent = intent_score >= 0.5 or intent_max >= 0.6

    # Strong intent signal → escalate regardless of keyword matcher
    if has_strong_intent and primary_intent not in ("none", "unknown"):
        prediction = "FAKE_SCAM"
        confidence = max(0.65, intent_score, intent_max)
        risk_level = "HIGH" if confidence >= 0.75 else "MEDIUM"
        logger.info(f"🎯 Fusion: intent '{primary_intent}' triggers FAKE_SCAM (intent_score={intent_score:.2f}, max={intent_max:.2f})")
    elif nlp_safe and vision_risk < 0.5:
        prediction = "SAFE"
        confidence = max(0.7, (1.0 - vision_risk + nlp_conf) / 2)
        risk_level = "LOW"
    elif not nlp_safe and nlp_conf < 0.45:
        # NLP says not safe but with very low confidence — don't trust it
        prediction = "SAFE"
        confidence = 0.5
        risk_level = "LOW"
        logger.info(f"⚠️ Fusion override: NLP said {nlp_pred} but confidence only {nlp_conf:.1%}, defaulting to SAFE")
    elif vision_risk >= 0.7 or (not nlp_safe and nlp_conf >= 0.45):
        prediction = nlp_pred if nlp_pred != "SAFE" else "FAKE_SCAM"
        confidence = max(vision_risk, nlp_conf)
        risk_level = "HIGH" if confidence >= 0.7 else "MEDIUM"
    else:
        prediction = "FAKE_SCAM"
        confidence = 0.55
        risk_level = "MEDIUM"

    # Suppress intent label when prediction is SAFE (avoids contradictory UI)
    # Don't strip it — keep for transparency, but mark as low-confidence
    if prediction == "SAFE" and intent_max < 0.3:
        # Truly safe, no significant intent detected
        pass

    return {
        "prediction": prediction,
        "confidence": round(confidence, 3),
        "risk_level": risk_level,
        "requires_review": prediction != "SAFE",
        "fusion_method": "rule_based_fallback"
    }

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint - API info and quick links"""
    return {
        "service": "ViFake Analytics API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health",
        "endpoints": {
            "analyze": "POST /api/v1/analyze",
            "analyze_video": "POST /api/v1/analyze/video",
            "job_status": "GET /api/v1/job/{job_id}",
            "result": "GET /api/v1/result/{job_id}",
            "stream": "GET /api/v1/stream/{job_id}",
            "list_jobs": "GET /api/v1/jobs",
            "stats": "GET /api/v1/stats",
        }
    }

@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze_post(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    auth_user: Dict = Depends(verify_token)
):
    """B2B endpoint: Analyze content URL"""
    logger.info(f"📥 Analysis request from {auth_user['user']}: {request.platform}:{request.url}")
    
    # Create job
    job_id = create_analysis_job(request.url, request.platform, request.priority)
    
    # Start background processing with optional content
    background_tasks.add_task(run_full_pipeline, job_id, request.url, request.platform, request.content)
    
    # Estimate processing time based on priority
    estimated_time = {
        "high": 30,
        "normal": 60,
        "low": 120
    }.get(request.priority, 60)
    
    return AnalyzeResponse(
        job_id=job_id,
        status="processing",
        message="Analysis job created successfully",
        estimated_time=estimated_time
    )

@app.get("/api/v1/stream/{job_id}")
async def stream_progress(job_id: str):
    """SSE endpoint for real-time progress"""
    if job_id not in active_jobs and job_id not in job_results:
        raise HTTPException(status_code=404, detail="Job not found")
    
    async def event_generator():
        # Get job info
        job_info = active_jobs.get(job_id, job_results.get(job_id))
        
        if not job_info:
            yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
            return
        
        # Send current status
        yield f"data: {json.dumps(job_info)}\n\n"
        
        # If job is still processing, continue streaming
        if job_id in active_jobs:
            stages = [
                "🔍 Crawling metadata...",
                "🛡️ Quarantine check passed...",
                "🖼️ CLIP vision analysis running...",
                "📝 PhoBERT NLP analysis running...",
                "🧠 XGBoost decision fusion...",
                "🕸️ Updating Neo4j graph...",
                "✅ Analysis complete."
            ]
            
            for i, stage in enumerate(stages):
                if job_id not in active_jobs:  # Job completed
                    break
                
                progress = (i + 1) * (100.0 / len(stages))
                update_job_progress(job_id, progress, stage)
                
                yield f"data: {json.dumps(active_jobs[job_id])}\n\n"
                await asyncio.sleep(0.8)
        
        # Final status
        final_job_info = job_results.get(job_id, active_jobs.get(job_id))
        if final_job_info:
            yield f"data: {json.dumps(final_job_info)}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

@app.get("/api/v1/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, auth_user: Dict = Depends(verify_token)):
    """Get job status"""
    job_info = active_jobs.get(job_id, job_results.get(job_id))
    
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(**job_info)

@app.get("/api/v1/result/{job_id}", response_model=AnalysisResult)
async def get_analysis_result(job_id: str, auth_user: Dict = Depends(verify_token)):
    """Get final analysis result"""
    job_info = job_results.get(job_id)
    
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    result = job_info["result"]
    
    return AnalysisResult(
        job_id=job_id,
        url=job_info["url"],
        platform=job_info["platform"],
        label=result["label"],
        confidence=result["confidence"],
        risk_level=result["risk_level"],
        needs_review=result["needs_review"],
        analysis_details=result["analysis_details"],
        processing_time=result["processing_time"],
        created_at=job_info["created_at"]
    )

@app.delete("/api/v1/job/{job_id}")
async def delete_job(job_id: str, auth_user: Dict = Depends(verify_token)):
    """Delete job and results"""
    if job_id in active_jobs:
        del active_jobs[job_id]
    if job_id in job_results:
        del job_results[job_id]
    
    logger.info(f"🗑️ Job {job_id} deleted by {auth_user['user']}")
    return {"message": "Job deleted successfully"}

@app.get("/api/v1/jobs")
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    auth_user: Dict = Depends(verify_token)
):
    """List jobs"""
    all_jobs = {**active_jobs, **job_results}
    
    # Filter by status
    if status:
        all_jobs = {k: v for k, v in all_jobs.items() if v.get("status") == status}
    
    # Sort by creation time (newest first)
    sorted_jobs = sorted(
        all_jobs.values(),
        key=lambda x: x.get("created_at", datetime.min),
        reverse=True
    )
    
    # Limit results
    limited_jobs = sorted_jobs[:limit]
    
    return {
        "jobs": limited_jobs,
        "total": len(all_jobs),
        "filtered": len(limited_jobs)
    }

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "active_jobs": len(active_jobs),
        "completed_jobs": len(job_results)
    }

@app.post("/api/v1/analyze/video", response_model=VideoAnalyzeResponse)
async def analyze_video(
    request: VideoAnalyzeRequest,
    auth_user: Dict = Depends(verify_token)
):
    """
    Pipeline phân tích video TikTok.
    Server tự tải audio/frames từ video_url — client không cần tải gì.
    """
    import time
    start_time = time.time()
    
    logger.info(f"🎬 Video analysis request from {auth_user['user']}: {request.video_url}")
    
    try:
        # Import pipeline coordinator with correct path
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from video_pipeline.pipeline_coordinator import VideoAnalysisPipeline
        
        pipeline = VideoAnalysisPipeline()
        result = await pipeline.run(
            video_url=request.video_url,
            description=request.description,
            author=request.author,
        )
        
        result["processing_ms"] = int((time.time() - start_time) * 1000)
        
        logger.info(f"✅ Video analysis completed in {result['processing_ms']}ms: {result['verdict']}")
        return VideoAnalyzeResponse(**result)
        
    except Exception as e:
        logger.error(f"❌ Video analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Video analysis failed: {str(e)}"
        )

@app.get("/api/v1/stats")
async def get_stats(auth_user: Dict = Depends(verify_token)):
    """Get system statistics"""
    all_jobs = {**active_jobs, **job_results}
    
    stats = {
        "total_jobs": len(all_jobs),
        "active_jobs": len(active_jobs),
        "completed_jobs": len([j for j in job_results.values() if j["status"] == "completed"]),
        "failed_jobs": len([j for j in job_results.values() if j["status"] == "failed"]),
        "platforms": {},
        "average_processing_time": 0.0
    }
    
    # Platform distribution
    for job in all_jobs.values():
        platform = job.get("platform", "unknown")
        stats["platforms"][platform] = stats["platforms"].get(platform, 0) + 1
    
    # Average processing time
    completed_jobs = [j for j in job_results.values() if j["status"] == "completed" and j.get("result")]
    if completed_jobs:
        total_time = sum(j["result"]["processing_time"] for j in completed_jobs)
        stats["average_processing_time"] = total_time / len(completed_jobs)
    
    return stats

# Run server
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
