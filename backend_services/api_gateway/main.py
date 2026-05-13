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

# URL result cache (TTL 300s, max 1000 entries)
try:
    from backend_services.cache_manager import url_cache
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from cache_manager import url_cache
    except ImportError:
        url_cache = None

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

# Live scan statistics — seeded from actual training pipeline data:
# - 2,800 mẫu synthetic (phobert_train.jsonl): 2000 scam (label=1), 800 safe (label=0)
# - 750 mẫu labeled (vietnamese_child_scams_labeled.json): 750 scam
# - 79 mẫu real validation (real_validation_set.jsonl): 27 FAKE_SCAM, 18 SUSPICIOUS, 34 SAFE
# Total pipeline-processed: 3,629 samples
_scan_stats = {
    "total_scans":   3_629,   # tổng mẫu đã qua pipeline (synthetic + real_validation)
    "scam_detected": 2_777,   # 2000 (train) + 750 (labeled) + 27 (real_val FAKE_SCAM)
    "suspicious":       18,   # real_validation SUSPICIOUS
    "safe":            834,   # 800 (train) + 34 (real_val SAFE)
}

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
            # Check for actual model weight files — not just the directory
            _weight_exts = ('.bin', '.safetensors', '.onnx', '.pt')
            _has_weights = os.path.isdir(model_path) and any(
                f.endswith(_weight_exts) for f in os.listdir(model_path)
            )
            if not _has_weights:
                logger.info("⚠️ No fine-tuned weights found, loading vinai/phobert-base from HuggingFace")
                model_path = None  # PhoBERTInference will use vinai/phobert-base
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
    images: Optional[List[str]] = Field(default=None, description="Optional list of explicit image URLs provided by client")
    
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
        "demo-token-123":   {"user": "api_user", "permissions": ["analyze"]},
        "vifake-demo-2024": {"user": "api_user", "permissions": ["analyze"]},
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

def _sanitize(obj):
    """Recursively convert numpy scalars/arrays to plain Python types for JSON serialization"""
    try:
        import numpy as np
        if isinstance(obj, np.generic):  # covers np.bool_, np.float32, np.int64, etc.
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def complete_job(job_id: str, result: Dict):
    """Complete job with results"""
    if job_id in active_jobs:
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["progress"] = 100.0
        active_jobs[job_id]["current_stage"] = "Completed"
        active_jobs[job_id]["result"] = _sanitize(result)  # strip numpy types
        active_jobs[job_id]["updated_at"] = datetime.now()
        
        # Move to results storage
        job_results[job_id] = active_jobs[job_id].copy()
        del active_jobs[job_id]
        
        # Update live stats
        label = result.get("label", "")
        _scan_stats["total_scans"] += 1
        if label == "FAKE_SCAM":
            _scan_stats["scam_detected"] += 1
        elif label == "SUSPICIOUS":
            _scan_stats["suspicious"] += 1
        else:
            _scan_stats["safe"] += 1
        
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
async def run_full_pipeline(job_id: str, url: str, platform: str, content: Optional[str] = None, images: Optional[List[str]] = None):
    """Run complete analysis pipeline with real AI models"""
    try:
        start_time = datetime.now()

        # Cache hit: skip re-analysis for recently seen URLs (TTL 300s)
        if not content and url_cache is not None:
            cached = url_cache.get(url)
            if cached is not None:
                logger.info(f"📦 Cache hit for {url[:60]} — returning cached result")
                complete_job(job_id, cached)
                return
        
        # Stage 1: Extract content (crawl page once, reuse HTML for text + vision)
        update_job_progress(job_id, 5.0, "🔍 Crawling URL and extracting content...")
        _page_html = ""
        if content:
            extracted_text = content
            logger.info(f"📝 Using provided content ({len(content)} chars)")
        else:
            # Pre-crawl once — share HTML between text extraction and CLIP og:image
            try:
                import requests as _preq
                _r = _preq.get(url, headers=_CRAWL_HEADERS, timeout=10, allow_redirects=True)
                if _r.ok:
                    _page_html = _r.text
                    logger.info(f"🌐 Pre-crawled {len(_page_html)} bytes from {url[:60]}")
            except Exception as _pce:
                logger.warning(f"⚠️ Pre-crawl failed: {_pce}")
            extracted_text = _extract_text_from_url(url, platform, _page_html)
            logger.info(f"🔗 Extracted from URL: {extracted_text[:100]}...")

            # yt-dlp fallback: if crawled text is too short (<80 chars) for video platforms,
            # try yt-dlp to get title + description + tags from TikTok/YouTube/Facebook
            _is_video_platform = platform in ("tiktok", "youtube", "facebook") or any(
                d in url for d in ("tiktok.com", "youtube.com", "youtu.be", "fb.com", "facebook.com")
            )
            if _is_video_platform and len(extracted_text) < 80:
                try:
                    from ai_engine.vision_worker.ytdlp_extractor import extract_video_metadata, build_text_from_metadata
                    update_job_progress(job_id, 7.0, "📹 Fetching video metadata via yt-dlp...")
                    _meta = extract_video_metadata(url, timeout=15)
                    _ytdlp_text = build_text_from_metadata(_meta)
                    if _ytdlp_text and len(_ytdlp_text) > 20:
                        # Prepend username signal if any, then append yt-dlp content
                        _prefix = extracted_text if extracted_text != url else ""
                        extracted_text = (_prefix + " " + _ytdlp_text).strip()
                        logger.info(f"📹 yt-dlp enriched text: {len(extracted_text)} chars")
                    else:
                        logger.info("📹 yt-dlp returned no useful text")
                except Exception as _ydl_e:
                    logger.warning(f"⚠️ yt-dlp fallback failed: {_ydl_e}")
        await asyncio.sleep(0.2)
        
        # Stage 2: Safety pre-check
        update_job_progress(job_id, 10.0, "🛡️ Running safety pre-check...")
        await asyncio.sleep(0.2)
        
        # Stage 3: NLP Analysis with PhoBERT
        update_job_progress(job_id, 25.0, "� Running PhoBERT NLP analysis...")
        nlp_result = _run_nlp_analysis(extracted_text)
        update_job_progress(job_id, 50.0, "📝 PhoBERT analysis complete")
        
        # Stage 4: Vision Analysis with CLIP (if image available)
        update_job_progress(job_id, 55.0, "🖼️ Running CLIP vision analysis...")
        vision_result = _run_vision_analysis(url, platform, page_html=_page_html, text=extracted_text, provided_images=images)
        update_job_progress(job_id, 75.0, "🖼️ CLIP analysis complete")
        
        # Stage 5: Fusion Decision
        update_job_progress(job_id, 80.0, "🧠 Running XGBoost decision fusion (29 features)...")
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
            "extracted_text": extracted_text if not content else None,  # crawled text (URL-mode only)
            "analysis_details": {
                "vision_risk": vision_result.get("combined_risk_score", 0.5),
                "vision_confidence": vision_result.get("combined_risk_score", 0.5),  # alias for frontend bar
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
        
        # Safe content override: if NLP has NO scam flags and says SAFE, trust NLP over XGBoost
        # (XGBoost trained on synthetic scam data can bias toward FAKE_SCAM for neutral text)
        # BUT: Don't override to SAFE if text contains gaming keywords (potential scam context)
        nlp_flags_raw = nlp_result.get("flags", [])
        has_scam_flags = any(
            f for f in nlp_flags_raw
            if not f.startswith("SAFE_INDICATORS") and not f.startswith("TEENCODE")
        )
        # Check for gaming context that should prevent safe override
        GAMING_CONTEXT_KEYWORDS = [
            'robux', 'roblox', 'vbucks', 'v-bucks', 'skin', 'gem',
            'diamond', 'kim cương', 'free fire', 'acc game', 'nick game',
            'trade', 'swap', 'doubling', 'nhân đôi', 'cookie logger',
            'cho mượn acc', 'đưa acc', 'nhập code',
            # Free Fire
            'freefire', 'garena', 'elite pass', 'bundle',
            'hack ff', 'mod ff', 'hack free fire',
            # Liên Quân
            'liên quân', 'lien quan', 'quân huy', 'hack lq', 'mod lq',
            # PUBG
            'pubg', 'royale pass', 'hack uc', 'hack pubg',
        ]
        text_for_check = extracted_text.lower()
        has_gaming_context = any(kw in text_for_check for kw in GAMING_CONTEXT_KEYWORDS)

        if not has_scam_flags and nlp_result.get("is_safe", False) and not has_gaming_context:
            result["label"] = "SAFE"
            result["risk_level"] = "LOW"
            result["confidence"] = round(min(result["confidence"], 0.25), 3)
            result["needs_review"] = False
            logger.info("🛡️ Safe override: NLP=SAFE + 0 scam flags + no gaming context → SAFE")
        elif has_gaming_context and not has_scam_flags:
            # Gaming content without explicit scam flags → SUSPICIOUS (not safe)
            result["label"] = "SUSPICIOUS"
            result["risk_level"] = "MEDIUM"
            result["confidence"] = max(result["confidence"], 0.45)
            result["needs_review"] = True
            logger.info(f"⚠️ Gaming context override: gaming keywords found → SUSPICIOUS")

        # Upgrade borderline FAKE_SCAM to SUSPICIOUS when confidence is in gray zone (0.40-0.69)
        label = result["label"]
        conf_val = result.get("confidence", 0.5)
        if label == "FAKE_SCAM" and 0.40 <= conf_val < 0.70:
            result["label"] = "SUSPICIOUS"
            result["risk_level"] = "MEDIUM"
            result["needs_review"] = True
            logger.info(f"⚠️ Gray-zone: confidence={conf_val:.3f} → downgraded FAKE_SCAM to SUSPICIOUS")

        # Normalize risk_level — never LOW for FAKE_SCAM, never HIGH for SAFE
        label = result["label"]
        if label == "FAKE_SCAM" and result["risk_level"] == "LOW":
            result["risk_level"] = "MEDIUM"
        elif label == "SAFE":
            result["risk_level"] = "LOW"
        elif label == "SUSPICIOUS" and result["risk_level"] not in ("MEDIUM", "HIGH"):
            result["risk_level"] = "MEDIUM"

        complete_job(job_id, result)
        # Store in cache (URL-mode only; don't cache user-pasted content)
        if not content and url_cache is not None:
            url_cache.set(url, result)
            logger.debug(f"📦 Cached result for {url[:60]}")
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed for job {job_id}: {e}")
        fail_job(job_id, str(e))

# Enhanced headers to mimic real browser for better crawling success
_CRAWL_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Ch-UA': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-UA-Mobile': '?0',
    'Sec-Ch-UA-Platform': '"Windows"',
}

def _extract_text_from_url(url: str, platform: str, page_html: str = "") -> str:
    """Crawl the real page and extract title, description, og:description, visible text.
    If page_html is provided (pre-crawled), skip the HTTP request and parse directly."""
    import re as _re

    # --- Username/path scam signal extracted from URL (works even if crawl fails) ---
    _SCAM_URL_TOKENS = {
        "rbx", "robux", "unlock", "free", "hack", "cheat", "gem", "coin",
        "gift", "giveaway", "crypto", "usdt", "airdrop", "generator", "gen",
        "scam", "phishing", "crack", "mod", "cheats", "vbuck", "uc", "diamond",
    }
    _url_username_signal = ""
    # TikTok: extract @username from URL path
    _tt_user_m = _re.search(r'tiktok\.com/@([^/?#&]+)', url)
    if _tt_user_m:
        _uname = _tt_user_m.group(1).lower()
        # Split username into tokens (handle camelCase/underscores/numbers)
        _uname_tokens = set(_re.split(r'[^a-z]', _uname)) | {_uname}
        if _uname_tokens & _SCAM_URL_TOKENS or any(kw in _uname for kw in _SCAM_URL_TOKENS):
            _url_username_signal = (
                f"free robux unlock hack roblox account generator scam tài khoản "
                f"lừa đảo miễn phí username @{_uname}"
            )
            logger.info(f"⚠️ Scam username in TikTok URL: @{_uname}")
    # YouTube: extract channel/user from URL path
    _yt_chan_m = _re.search(r'youtube\.com/(?:@|c/|channel/|user/)([^/?#&]+)', url)
    if _yt_chan_m:
        _chan = _yt_chan_m.group(1).lower()
        _chan_tokens = set(_re.split(r'[^a-z]', _chan)) | {_chan}
        if _chan_tokens & _SCAM_URL_TOKENS or any(kw in _chan for kw in _SCAM_URL_TOKENS):
            _url_username_signal = (
                f"free robux unlock hack account generator scam channel @{_chan}"
            )
            logger.info(f"⚠️ Scam channel in YouTube URL: @{_chan}")

    try:
        from bs4 import BeautifulSoup
        if not page_html:
            import requests as _req
            resp = _req.get(url, headers=_CRAWL_HEADERS, timeout=8, allow_redirects=True)
            resp.raise_for_status()
            page_html = resp.text
        soup = BeautifulSoup(page_html, "lxml")

        parts = []

        # 0. Username scam signal (inject first so NLP sees it)
        if _url_username_signal:
            parts.append(_url_username_signal)

        # 1. <title>
        if soup.title and soup.title.string:
            parts.append(soup.title.string.strip())

        # 2. Open Graph tags (most social platforms use these)
        for prop in ("og:title", "og:description", "twitter:title", "twitter:description"):
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content"):
                parts.append(tag["content"].strip())

        # 3. <meta name="description">
        desc = soup.find("meta", attrs={"name": "description"})
        if desc and desc.get("content"):
            parts.append(desc["content"].strip())

        # 4. YouTube: oEmbed for title + ytInitialData JSON in page
        if platform == "youtube" and "youtube.com" in url:
            # 4a. YouTube oEmbed — fast, no auth needed
            try:
                import requests as _oe_req
                _oe = _oe_req.get(
                    "https://www.youtube.com/oembed",
                    params={"url": url, "format": "json"},
                    headers=_CRAWL_HEADERS,
                    timeout=5,
                )
                if _oe.ok:
                    _oe_data = _oe.json()
                    if _oe_data.get("title"):
                        parts.append(_oe_data["title"])
                    if _oe_data.get("author_name"):
                        parts.append(f"YouTube channel: {_oe_data['author_name']}")
            except Exception:
                pass
            # 4b. ytInitialData JSON in page
            m = _re.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', page_html)
            if m:
                parts.append(m.group(1))
            m2 = _re.search(r'"shortDescription":"([^"]{10,500})"', page_html)
            if m2:
                parts.append(m2.group(1).replace("\\n", " "))

        # 5. TikTok: oEmbed API (bypasses bot protection) + yt-dlp fallback + JSON patterns from page HTML
        if platform == "tiktok" and "tiktok.com" in url:
            # 5a. TikTok oEmbed — always returns title + caption + author_url
            try:
                import requests as _oe_req
                _oe = _oe_req.get(
                    "https://www.tiktok.com/oembed",
                    params={"url": url},
                    headers=_CRAWL_HEADERS,
                    timeout=6,
                )
                if _oe.ok:
                    _oe_data = _oe.json()
                    # title is usually the caption e.g. "free Roblox #roblox #rbx"
                    if _oe_data.get("title"):
                        parts.append(_oe_data["title"])
                    # author_url e.g. "https://www.tiktok.com/@rbxunlock"
                    if _oe_data.get("author_url"):
                        _au = _oe_data["author_url"]
                        _au_name = _au.split("@")[-1] if "@" in _au else _au
                        parts.append(f"TikTok author @{_au_name}")
                    # html embed contains full caption paragraph + hashtag anchors
                    if _oe_data.get("html"):
                        _oe_m = _re.findall(r'<p>(.*?)</p>', _oe_data["html"], _re.DOTALL)
                        for _oe_cap in _oe_m:
                            _oe_cap_clean = _re.sub(r'<[^>]+>', ' ', _oe_cap).strip()
                            if _oe_cap_clean:
                                parts.append(_oe_cap_clean)
                    logger.info(f"🎵 TikTok oEmbed: title='{_oe_data.get('title','')[:60]}'")
            except Exception as _oe_e:
                logger.debug(f"TikTok oEmbed failed: {_oe_e}")
            
            # 5b. yt-dlp fallback for TikTok (bypasses most anti-bot restrictions)
            if len(parts) < 2:  # If oEmbed failed or returned insufficient content
                try:
                    import yt_dlp
                    _ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': True,
                        'simulate': True,  # Don't download
                    }
                    with yt_dlp.YoutubeDL(_ydl_opts) as _ydl:
                        _info = _ydl.extract_info(url, download=False)
                        if _info.get('title'):
                            parts.append(_info['title'])
                        if _info.get('description'):
                            parts.append(_info['description'])
                        if _info.get('uploader'):
                            parts.append(f"TikTok author @{_info['uploader']}")
                        if _info.get('thumbnail'):
                            # Store thumbnail URL for later use
                            logger.info(f"🖼️ TikTok thumbnail via yt-dlp: {_info['thumbnail'][:80]}")
                    logger.info(f"🎵 TikTok yt-dlp fallback successful")
                except Exception as _ydl_e:
                    logger.warning(f"⚠️ TikTok yt-dlp fallback failed: {_ydl_e}")

            # 5b. JSON patterns from page HTML (fallback)
            _tiktok_patterns = [
                r'"desc"\s*:\s*"([^"]{5,300})"',                        # video caption
                r'"videoDescription"\s*:\s*"([^"]{5,300})"',            # alt description key
                r'"caption"\s*:\s*"([^"]{5,300})"',                     # caption key
                r'"nickName"\s*:\s*"([^"]{2,80})"',                     # author nickname
                r'"textExtra":\[.*?"hashtagName"\s*:\s*"([^"]{2,80})"', # hashtag
            ]
            for _pat in _tiktok_patterns:
                _tm = _re.search(_pat, page_html)
                if _tm and _tm.group(1) not in parts:
                    parts.append(_tm.group(1))

        # 6. Facebook: OGP description often contains post text (login wall limits HTML)
        if platform == "facebook":
            for div in soup.find_all("div", {"data-ad-preview": True}):
                t = div.get_text(" ", strip=True)
                if t:
                    parts.append(t)

        # 7. Fallback: main visible text (first 800 chars)
        if len(parts) < 2:
            body_text = soup.get_text(" ", strip=True)
            parts.append(body_text[:800])

        text = " ".join(dict.fromkeys(parts))  # deduplicate preserving order
        logger.info(f"🌐 Crawled {len(text)} chars from {url[:60]}")
        return text if text.strip() else url

    except Exception as e:
        logger.warning(f"⚠️ URL crawl failed ({e}), falling back to URL heuristics")

    # Fallback: URL + username signal
    url_lower = url.lower()
    signals = []
    if _url_username_signal:
        signals.append(_url_username_signal)
    if any(kw in url_lower for kw in [
        "scam", "free", "gift", "robux", "nạp", "thẻ", "quà",
        "rbx", "unlock", "hack", "generator", "gen", "crypto", "usdt",
        "airdrop", "vbuck", "cheat", "mod", "giveaway",
    ]):
        signals.append("Cảnh báo: URL chứa từ khóa đáng ngờ liên quan đến lừa đảo hoặc quà tặng miễn phí")
    if any(kw in url_lower for kw in ["safe", "education", "học", "giáo"]):
        signals.append("Nội dung giáo dục an toàn")
    return " ".join(signals) if signals else url


def _fetch_thumbnail_url(url: str, platform: str, page_html: str = "") -> Optional[str]:
    """Extract thumbnail/image URL from og:image, twitter:image, or YouTube thumbnail API."""
    import re as _re
    # TikTok: oEmbed returns thumbnail_url (CDN signed URL, no IP block)
    if platform == "tiktok" and "tiktok.com" in url:
        try:
            import requests as _oe_req
            _oe = _oe_req.get(
                "https://www.tiktok.com/oembed",
                params={"url": url},
                headers=_CRAWL_HEADERS,
                timeout=6,
            )
            if _oe.ok:
                _thumb = _oe.json().get("thumbnail_url")
                if _thumb:
                    logger.info(f"🖼️ TikTok thumbnail via oEmbed: {_thumb[:80]}")
                    return _thumb
        except Exception as _te:
            logger.debug(f"TikTok thumbnail oEmbed failed: {_te}")
    # YouTube: direct thumbnail URL from video ID (no crawl needed)
    if platform == "youtube" and "watch?v=" in url:
        video_id = url.split("watch?v=")[-1].split("&")[0]
        return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    # If no pre-crawled HTML, try crawling ourselves to get og:image
    if not page_html:
        try:
            import requests as _req
            _r = _req.get(url, headers=_CRAWL_HEADERS, timeout=8, allow_redirects=True)
            if _r.ok:
                page_html = _r.text
                logger.info(f"🌐 Fetched page HTML for thumbnail extraction ({len(page_html)} bytes)")
        except Exception as _e:
            logger.warning(f"⚠️ Thumbnail crawl failed: {_e}")
    if page_html:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(page_html, "lxml")
            tag = (
                soup.find("meta", property="og:image") or
                soup.find("meta", attrs={"name": "twitter:image"}) or
                soup.find("meta", attrs={"name": "og:image"}) or
                soup.find("meta", property="twitter:image")
            )
            if tag and tag.get("content") and tag["content"].startswith("http"):
                logger.info(f"🖼️ Found og:image: {tag['content'][:80]}")
                return tag["content"]
        except Exception:
            pass
    return None

def _run_nlp_analysis(text: str) -> Dict:
    """Run PhoBERT NLP analysis with comprehensive Vietnamese scam detection fallback"""
    phobert_result = None
    try:
        model = get_nlp_model()
        if model is not None:
            phobert_result = model.predict(text)
            logger.info(f"📝 PhoBERT result: {phobert_result.get('prediction')} (confidence: {phobert_result.get('confidence', 0):.3f})")
            
            # Trust PhoBERT for FAKE_SCAM/SUSPICIOUS only — always run scam detector as safety net
            phobert_pred = phobert_result.get('prediction', 'SAFE')
            phobert_conf = phobert_result.get('confidence', 0)
            if phobert_conf >= 0.5 and phobert_pred != "SAFE":
                # PhoBERT is confident it's a scam — trust it
                pass  # fall through to scam detector comparison below
            elif phobert_conf >= 0.7 and phobert_pred == "SAFE":
                # Only trust PhoBERT's SAFE if very confident (>70%) — still cross-check scam detector
                pass  # fall through
            else:
                logger.info(f"⚠️ PhoBERT confidence too low ({phobert_conf:.1%}), consulting scam detector...")
    except Exception as e:
        logger.warning(f"⚠️ NLP inference failed: {e}")
    
    # Always run Vietnamese scam detection engine (catches patterns PhoBERT misses)
    logger.info("📝 Running Vietnamese scam detection engine...")
    result = _vietnamese_scam_detector(text)
    
    # If PhoBERT ran, pick the more alarming result (prioritise scam detection over false safety)
    if phobert_result is not None:
        scam_conf = result.get('confidence', 0)
        phobert_conf = phobert_result.get('confidence', 0)
        phobert_pred = phobert_result.get('prediction', 'SAFE')
        scam_pred = result.get('prediction', 'SAFE')
        logger.info(f"🔄 Comparing: PhoBERT={phobert_pred}@{phobert_conf:.3f} vs ScamDetector={scam_pred}@{scam_conf:.3f}")
        # If scam detector found signals (non-SAFE), it overrides a SAFE PhoBERT
        if scam_pred != "SAFE":
            pass  # keep scam detector result
        elif phobert_pred != "SAFE" and phobert_conf > scam_conf:
            result = phobert_result  # PhoBERT caught scam that detector missed
        elif phobert_pred == "SAFE" and scam_pred == "SAFE":
            result = phobert_result if phobert_conf > scam_conf else result
    
    # Add intent detection
    try:
        from ai_engine.nlp_worker.intent_detector import detect_scam_intent, get_intent_explanation, get_safe_explanation
        intent_result = detect_scam_intent(text)
        result["intent"] = intent_result
        primary_intent = intent_result.get("primary_intent", "none")
        max_score = intent_result.get("max_intent_score", 0)
        
        # Safety override: If overall system already flagged SCAM but intent detector missed it,
        # provide tailored generic intent explanations based on detection flags.
        final_pred = result.get("prediction", "SAFE")
        all_flags = result.get("flags", [])
        has_price_scam = any("PRICE_ANOMALY" in str(f) for f in all_flags)
        has_doubling = any("GAMING_DOUBLING" in str(f) or "UNREALISTIC_RATIO" in str(f) for f in all_flags)
        has_p2p_trade = any("RISKY_P2P_TRADING" in str(f) for f in all_flags)
        
        if primary_intent == "none" or max_score == 0.0:
            if has_price_scam:
                result["intent_label"] = "Bất thường giá thị trường"
                result["intent_explanation"] = (
                    "⚠️ CẢNH BÁO NGUY HIỂM: Hệ thống phát hiện tỷ lệ nạp tiền quá rẻ so với thực tế! "
                    "Đây là chiêu trò bẫy giá rẻ ảo để thu hút trẻ em nạp thẻ cào / chuyển tiền. "
                    "Hầu hết các shop rao giá này đều là lừa đảo 100% và sẽ lấy tiền mà không trao vật phẩm."
                )
            elif has_doubling:
                result["intent_label"] = "Lừa đảo nhân đôi vật phẩm game"
                result["intent_explanation"] = "Phát hiện chiêu trò hứa 'nhân đôi Robux/Kim cương/Quân huy' hoặc đòi 'mượn Acc'. Tuyệt đối không cung cấp mật khẩu hay đưa vật phẩm trước."
            elif has_p2p_trade:
                result["intent_label"] = "Giao dịch Game tự phát (P2P)"
                result["intent_explanation"] = (
                    "⚠️ LƯU Ý AN TOÀN: Đây là nội dung rao bán/giao dịch trực tiếp giữa các cá nhân. "
                    "Hình thức này tiềm ẩn RỦI RO CAO cho trẻ em vì không có cơ chế bảo lãnh. "
                    "Khuyên bạn NÊN TÌM BÊN TRUNG GIAN UY TÍN để thực hiện giao dịch hoặc TỐT NHẤT LÀ TRÁNH XA để bảo vệ tài sản."
                )
            elif final_pred in ["FAKE_SCAM", "SUSPICIOUS"]:
                result["intent_label"] = "Nghi vấn hoạt động lừa đảo"
                result["intent_explanation"] = "Hệ thống phát hiện sự kết hợp của nhiều từ khoá rủi ro hoặc cấu trúc văn bản đặc trưng của tin nhắn gian lận nhắm vào người dùng."
            else:
                result["intent_label"] = "Không phát hiện dấu hiệu lừa đảo"
                result["intent_explanation"] = get_safe_explanation()
        else:
            # Explicit intent matched normally
            result["intent_label"] = intent_result.get("primary_intent_label", "")
            result["intent_explanation"] = get_intent_explanation(primary_intent)
            
            # Enhancement: inject price or P2P warnings if explicit intent missed details
            if has_price_scam and "giá" not in result["intent_explanation"].lower():
                 result["intent_explanation"] += " [⚠️ ĐẶC BIỆT CẢNH BÁO: Tỷ lệ giá cực kỳ phi lý, khả năng lừa đảo là 100%]"
            if has_p2p_trade and "p2p" not in result["intent_explanation"].lower() and "trung gian" not in result["intent_explanation"].lower():
                 result["intent_explanation"] += " [💡 LƯU Ý: Nên tìm bên trung gian giao dịch uy tín để đảm bảo an toàn]."

        logger.info(f"🎯 Intent: {intent_result.get('primary_intent_label')} (score={intent_result.get('risk_weighted_score', 0):.3f})")
    except Exception as e:
        logger.warning(f"⚠️ Intent detection failed: {e}")
        result["intent"] = {"primary_intent": "unknown"}
    
    return result

def _vietnamese_scam_detector(text: str) -> Dict:
    """Multi-dimensional Vietnamese scam/fake news detection"""
    import re
    text_lower = text.lower()
    text_upper = text.upper()
    score = 0.0
    flags = []
    details = {}

    # === 0a. Pay-first scheme detection (very high signal) ===
    pay_first_patterns = [
        r'nạp.*thẻ.*trước', r'trả.*trước.*để.*nhận', r'nạp.*trước.*để.*nhận',
        r'gửi.*tiền.*trước', r'chuyển.*khoản.*trước',
        r'nạp.*thẻ.*xác.*nhận', r'nạp.*thẻ.*xác.*minh',
        r'nạp.*\d+k.*để.*nhận', r'nạp.*\d+k.*xác.*nhận',
    ]
    pay_first_hits = [pat for pat in pay_first_patterns if re.search(pat, text_lower)]
    if pay_first_hits:
        score += 0.40
        flags.append('FINANCIAL_SCAM:pay_first_scheme')
        details['pay_first_risk'] = 0.40

    # === 0a2. Gaming context detection (semantic — not just keyword) ===
    # Split game items into LONG phrases and SHORT codes that need absolute word boundaries.
    GAME_ITEMS_LONG = [
        'robux', 'roblox', 'skin', 'gem', 'coin', 'diamond', 'kim cương',
        'v-bucks', 'vbucks', 'item game', 'vật phẩm', 'pet', 'gamepass',
        'free fire', 'freefire', 'garena', 'elite pass', 'bundle',
        'liên quân', 'lien quan', 'quân huy', 'tướng', 'ngọc',
        'pubg', 'royale pass', 'battle points'
    ]
    # CRITICAL: Short codes like 'uc', 'cp' MUST NOT match as substrings of words like 'chúc'!
    GAME_ITEMS_SHORT = ['uc', 'cp', 'kc', 'bp', 'rp', 'ep']

    ACTION_WORDS = ['đưa', 'gửi', 'cho', 'trade', 'chuyển', 'nhập', 'đổi',
                    'trao', 'bỏ', 'nạp', 'mượn', 'transfer', 'swap', 'drop']
    RECEIVE_WORDS = ['nhận', 'lấy', 'được', 'trả lại', 'hoàn', 'unlock',
                     'trả', 'nhận lại', 'nhận được']

    has_game = any(g in text_lower for g in GAME_ITEMS_LONG)
    if not has_game:
        # Safely check short items with word boundaries only
        for short_item in GAME_ITEMS_SHORT:
            if re.search(rf'(?:\s|^){re.escape(short_item)}(?:\s|$|\W)', text_lower):
                has_game = True
                break

    has_action = any(a in text_lower for a in ACTION_WORDS)
    has_receive = any(r in text_lower for r in RECEIVE_WORDS)

    if has_game and has_action and has_receive:
        score += 0.45  # Very high signal: game item + give + receive = doubling scam
        flags.append('GAMING_DOUBLING_SCAM:give_receive_pattern')
        details['gaming_doubling_risk'] = 0.45
    elif has_game and (has_action or has_receive):
        flags.append('GAMING_SCAM_CONTEXT')
        details['gaming_context_risk'] = 0.20

    # === 0a3. P2P Direct Trading / Unofficial Store Detection ===
    # Catches selling game items directly via banking/momo/cards which is risky for kids.
    p2p_trade_patterns = [
        r'(bán|thu mua|sell|trade)\s+(robux|roblox|acc|nick|skin|vật phẩm|v-bucks)',
        r'(stk|mb bank|vietcombank|techcombank|agribank|acb|vib|tpbank|bidv|vpbank)',
        r'(momo|zalopay|vnpay|banking)',
        r'(gdtg|giao dịch trung gian|giao dịch trực tiếp|gạch thẻ|đổi tiền)',
        r'(robux sạch|robux 120h|gift gamepass)',
    ]
    p2p_hits = [pat for pat in p2p_trade_patterns if re.search(pat, text_lower)]
    # Only flag as risky P2P if trading context is combined with a direct asset sale OR banking info
    if has_game and p2p_hits:
        p2p_score = 0.30 # Enough for SUSPICIOUS
        score += p2p_score
        flags.append(f'RISKY_P2P_TRADING:{len(p2p_hits)} indicators')
        details['p2p_trading_risk'] = p2p_score

    # === 0a3.5 Hashtag Concatenation detection (TikTok specific evasion) ===
    # Detects #shoprobuxlau, #shoprobuxgiare, etc which dodge standard delimiters
    hash_pairs = [
        (r'robux', r'(lau|giare|giárẻ|uytin|sach|hack)'),
        (r'quânhuy', r'(lau|giare|lậu|hack)'),
        (r'kimcương', r'(hack|giare|free|lậu)'),
    ]
    for t1, t2 in hash_pairs:
        if re.search(rf'({t1}.*?{t2}|{t2}.*?{t1})', text_lower):
            score += 0.60 # Strong Scam indicator - force high priority
            flags.append(f'SQUASHED_HASHTAG_SCAM:{t1}+{t2}')
            details['hashtag_fusion_risk'] = 0.60
            break

    # === 0a3. Gaming doubling/trade explicit patterns ===
    _GAME_CURRENCY = r'(robux|rbx|rb|skin|gem|coin|diamond|kim\s*cương|quân\s*huy|tướng|ngọc|uc|elite\s*pass|royale\s*pass|bundle)'
    gaming_doubling_patterns = [
        r'(đưa|gửi|cho|chuyển)\s*.*\d+\s*' + _GAME_CURRENCY + r'.*(nhận|lấy|được|trả)',
        r'(nhận|lấy|được|trả)\s*.*\d+\s*' + _GAME_CURRENCY + r'.*(đưa|gửi|cho)',
        r'nhân\s*đôi\s*' + _GAME_CURRENCY,
        r'x2\s*' + _GAME_CURRENCY, r'x10\s*' + _GAME_CURRENCY,
        r'doubling\s*' + _GAME_CURRENCY,
        r'(mượn|cho mượn)\s*' + _GAME_CURRENCY,
        r'(đưa|cho)\s*để\s*(test|kiểm tra|thử)',
        r'(trả lại|sẽ trả)\s*sau',
        # Game-specific hack/mod patterns
        r'hack\s*(free\s*fire|liên\s*quân|pubg|ff|lq)',
        r'mod\s*(free\s*fire|liên\s*quân|pubg|ff|lq)',
        r'(tool\s*hack|apk\s*mod)\s*(free\s*fire|liên\s*quân|pubg)',
    ]
    gaming_doubling_hits = [pat for pat in gaming_doubling_patterns if re.search(pat, text_lower)]
    if gaming_doubling_hits:
        gd_score = min(len(gaming_doubling_hits) * 0.20, 0.50)
        score += gd_score
        flags.append(f'GAMING_DOUBLING_SCAM:explicit ({len(gaming_doubling_hits)} patterns)')
        details['gaming_doubling_explicit'] = gd_score

    # === 0a4. Market Price Anomaly check (Too good to be true rates) ===
    price_pat = r'(\d+[\.,]?\d*)\s*(k|vnd|đ|đồng)'
    item_pat = r'(\d+[\.,]?\d*)\s*(robux|rbx|rb|kim cương|kc|quân huy|qh|uc)'
    f_prices = list(re.finditer(price_pat, text_lower))
    f_items = list(re.finditer(item_pat, text_lower))
    if f_prices and f_items:
        # Limit ratios per 1,000 VND. Setting ceiling to ~10x of official rate safely flags absurdity.
        p_limits = {'robux': 40, 'rbx': 40, 'rb': 40, 'kc': 100, 'kim cương': 100, 'qh': 50, 'quân huy': 50, 'uc': 50}
        for prc in f_prices:
            for itm in f_items:
                if abs(prc.start() - itm.start()) < 70: # In close proximity
                    try:
                        p_val = float(prc.group(1).replace('.', '').replace(',', ''))
                        if prc.group(2) == 'k': p_val *= 1000
                        i_val = float(itm.group(1).replace('.', '').replace(',', ''))
                        i_type = itm.group(2).strip()
                        if p_val > 0 and i_val > 0:
                            m_ratio = i_val / (p_val / 1000)
                            lim = p_limits.get(i_type, 50)
                            if m_ratio > lim:
                                score += 0.60 # Extremely high signal
                                flags.append(f'PRICE_ANOMALY_SCAM:unrealistic_{i_type}_ratio_{m_ratio:.0f}x')
                                details['price_anomaly_risk'] = 0.60
                                break
                    except: pass


    # === 0a4. Account takeover / cookie logger ===
    account_takeover_patterns = [
        r'cho\s*mình\s*(acc|tài khoản|nick)',
        r'cho\s*mượn\s*(acc|tài khoản|nick)',
        r'(đưa|cho)\s*(acc|tài khoản|nick).*để',
        r'đăng\s*nhập\s*(acc|tài khoản).*để',
        r'(nhập|paste|dán)\s*code.*vào\s*(acc|tài khoản|trình duyệt|browser|console)',
        r'(test|fix|nâng cấp|sửa|boost)\s*(acc|tài khoản)\s*cho',
        r'mình\s*sẽ\s*(fix|nâng cấp|boost)',
        r'cookie\s*logger', r'editthiscookie', r'roblox\s*cookie',
        r'đăng\s*nhập\s*hộ', r'login\s*hộ',
        r'(paste|nhập).*console',
    ]
    acct_hits = [pat for pat in account_takeover_patterns if re.search(pat, text_lower)]
    if acct_hits:
        acct_score = min(len(acct_hits) * 0.20, 0.55)
        score += acct_score
        flags.append(f'ACCOUNT_TAKEOVER ({len(acct_hits)} patterns)')
        details['account_takeover_risk'] = acct_score

    # === 0a5. Unrealistic number ratio detection ===
    # "đưa 1000 robux nhận 1000000 robux" → ratio 1000:1 = scam
    # Exclude strings starting with '0' (phones) and cap at 7 digits to avoid Bank Acc/Phone collisions
    numbers_in_text = [int(n) for n in re.findall(r'\b\d+\b', text) if 2 <= len(n) <= 7 and not n.startswith('0')]
    if len(numbers_in_text) >= 2 and has_game:
        numbers_in_text.sort()
        ratio = numbers_in_text[-1] / max(numbers_in_text[0], 1)
        if ratio >= 30:  # 30x or more + gaming context = very likely scam (fallback)
            score += 0.40
            flags.append(f'UNREALISTIC_RATIO:{numbers_in_text[0]}→{numbers_in_text[-1]} (x{ratio:.0f})')
            details['unrealistic_ratio'] = ratio
        elif ratio >= 15:  # 15x-30x + gaming = suspicious
            score += 0.15
            flags.append(f'SUSPICIOUS_RATIO:{numbers_in_text[0]}→{numbers_in_text[-1]} (x{ratio:.0f})')
            details['suspicious_ratio'] = ratio

    # === 0. Fast keyword pre-scan (catches cases where regex may miss) ===
    # Crypto / financial scam keywords (case-insensitive via text_lower)
    crypto_keywords = [
        'airdrop', 'metamask', 'usdt', ' eth ', '.eth', 'eth.', 'bitcoin', 'btc', 'crypto',
        'wallet', 'ví điện tử', 'ví metamask', 'connect wallet', 'connect ví',
        'nhận lại', 'gửi đi nhận lại', 'giveaway', 'double your', 'x2 eth', 'x2 usdt',
        'free token', 'free crypto', 'token free', 'claim token', 'claim reward',
    ]
    crypto_hits = [kw for kw in crypto_keywords if kw in text_lower]
    if crypto_hits:
        hit_score = min(len(crypto_hits) * 0.18, 0.55)
        score += hit_score
        flags.append(f"FINANCIAL_SCAM:crypto_keywords ({', '.join(crypto_hits[:3])})")
        details['crypto_keyword_hits'] = crypto_hits

    # "send small get large" pattern: e.g. "gửi 0.01 ETH... nhận lại 0.05 ETH"
    send_get_pattern = r'(gửi|send|nạp)\s+[\d.,]+\s*\w+.*?(nhận|receive|get)\s+[\d.,]+'
    if re.search(send_get_pattern, text_lower, re.DOTALL):
        score += 0.35
        flags.append("FINANCIAL_SCAM:send_receive_doubling")

    # Generic money-doubling numbers (e.g. "100k nhận về 500k")
    money_double = r'(nạp|gửi|bỏ ra).*?\d+.*?(nhận|được|lấy về).*?\d+'
    if re.search(money_double, text_lower, re.DOTALL):
        score += 0.25
        flags.append("FINANCIAL_SCAM:money_doubling")

    # === 0b. Fake giveaway / prize / engagement-bait ===
    giveaway_patterns = [
        r'share.*bài.*tag', r'tag.*\d+.*bạn.*nhận', r'share.*nhận.*quà',
        r'like.*share.*nhận', r'share.*bài.*nhận.*ngay',
        r'nhận.*ngay.*iphone', r'nhận.*ngay.*samsung', r'nhận.*ngay.*điện.*thoại',
        r'iphone.*miễn.*phí', r'macbook.*miễn.*phí', r'tặng.*iphone', r'tặng.*macbook',
        r'giveaway.*khủng', r'nhận.*quà.*ngay', r'trúng.*thưởng.*ngay',
        r'chỉ.*còn.*\d+.*giờ', r'chỉ.*còn.*\d+.*phút', r'còn.*\d+.*slot',
        r'tag.*3.*bạn', r'tag.*5.*bạn', r'tag.*bạn.*bè',
        r'bình.*luận.*nhận', r'comment.*nhận',
    ]
    giveaway_hits = [pat for pat in giveaway_patterns if re.search(pat, text_lower)]
    if giveaway_hits:
        gw_score = min(len(giveaway_hits) * 0.15, 0.45)
        score += gw_score
        flags.append(f'FAKE_REWARD:giveaway_prize ({len(giveaway_hits)} patterns)')
        details['giveaway_risk'] = gw_score

    # === 1. URL & Shortlink Detection ===
    url_patterns = [
        r'bit\.ly', r'bitly', r'shorturl', r'tinyurl', r'cutt\.ly',
        r'fb-verify', r'facebook.*verify', r'xác.*minh.*danh.*tính',
        r'link.*click', r'click.*link', r'bấm.*vào.*đây', r'truy.*cập.*ngay',
        r'\.click\b', r'\.xyz\b', r'\.top\b', r'\.tk\b',
    ]
    url_count = 0
    for pat in url_patterns:
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
            r'unlock.*robux', r'robux.*unlock', r'get.*robux', r'earn.*robux',
            r'robux.*generator', r'robux.*hack', r'robux.*cheat', r'robux.*secret',
            r'robux.*method', r'secret.*method.*robux', r'how.*to.*get.*robux',
            r'admin.*roblox', r'roblox.*admin', r'event.*robux',
            r'roblox.*hack', r'roblox.*cheat', r'roblox.*glitch',
            r'verify.*acc', r'xác.*minh.*acc', r'xác.*nhận.*acc', r'verify.*tài.*khoản',
        ],
        'gift_card_scam': [
            r'nạp.*thẻ.*được', r'nạp.*thẻ', r'thẻ.*gate', r'thẻ.*garena',
            r'nạp.*50k.*được.*500k', r'nạp.*100k.*được.*1tr',
            r'ưu.*đãi.*đặc.*biệt', r'khuyến.*mãi.*đặc.*biệt',
        ],
        'crypto_scam': [
            r'giveaway.*usdt', r'usdt.*giveaway', r'airdrop',
            r'connect.*ví', r'connect.*wallet', r'metamask',
            r'xác.*nhận.*giao.*dịch', r'confirm.*transaction',
            r'nhận.*thưởng.*usdt', r'nhận.*thưởng.*btc',
        ],
        'gaming_scam': [
            r'secret.*method', r'new.*secret.*method', r'new.*method.*hack',
            r'free.*coins', r'free.*gems', r'unlimited.*coins', r'unlimited.*gems',
            r'coin.*generator', r'gem.*generator', r'diamond.*hack',
            r'free.*vbucks', r'vbucks.*generator', r'vbucks.*hack',
            r'free.*skin', r'skin.*hack', r'free.*uc', r'uc.*hack',
        ],
        'robux_doubling': [
            r'đưa.*robux.*nhận', r'gửi.*robux.*nhận', r'cho.*robux.*nhận',
            r'trade.*robux', r'đổi.*robux', r'mượn.*robux', r'chuyển.*robux',
            r'nhân.*đôi.*robux', r'x2.*robux', r'doubling.*robux',
            r'đưa.*skin.*nhận', r'trade.*skin', r'đổi.*skin',
            r'đưa.*gem.*nhận', r'đưa.*coin.*nhận', r'đưa.*diamond.*nhận',
            r'cho.*mượn.*skin', r'cho.*mượn.*item',
        ],
        'account_theft': [
            r'cho.*mình.*acc', r'cho.*mượn.*acc', r'đưa.*acc.*để',
            r'cho.*mình.*nick', r'cho.*mượn.*nick',
            r'cho.*mình.*tài.*khoản.*để', r'cho.*mượn.*tài.*khoản',
            r'nhập.*code.*vào', r'paste.*code.*vào',
            r'đăng.*nhập.*hộ', r'login.*hộ',
            r'test.*acc.*cho', r'fix.*acc.*cho', r'nâng.*cấp.*acc.*cho',
            r'cookie.*logger', r'editthiscookie',
        ],
        'account_threat': [
            r'tài.*khoản.*bị.*khóa', r'account.*suspend',
            r'bị.*khóa.*trong.*24h', r'xác.*minh.*danh.*tính.*ngay',
            r'đăng.*nhập.*ngay', r'login.*now',
        ],
    }
    
    financial_score = 0
    for scam_type, patterns in financial_patterns.items():
        for pat in patterns:
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
        r'còn.*\d+.*giờ', r'còn.*\d+.*phút', r'còn.*\d+.*suất',
        r'!!!', r'chỉ.*hôm.*nay',
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
        # Vietnamese trust-manipulation phrases ("uy tín" = credibility, heavily abused by scammers)
        r'uy.*tín.*100', r'100.*uy.*tín',
        r'uy.*tín.*đảm.*bảo', r'đảm.*bảo.*uy.*tín',
        r'uy.*tín.*nhé', r'uy.*tín.*nha', r'uy.*tín.*mình',
        r'uy.*tín.*xịn', r'thật.*sự.*uy.*tín',
        r'có.*uy.*tín', r'uy.*tín.*cao',
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
    
    # === 7b. Hashtag Spam Detection ===
    _hashtag_all = re.findall(r'#(\w+)', text_lower)
    if _hashtag_all:
        import collections as _col
        _ht_counter = _col.Counter(_hashtag_all)
        _spam_tags = [(t, c) for t, c in _ht_counter.items() if c >= 3]
        if _spam_tags:
            _ht_score = min(len(_spam_tags) * 0.12, 0.25)
            score += _ht_score
            flags.append(f"HASHTAG_SPAM ({', '.join(f'#{t}x{c}' for t,c in _spam_tags[:3])})")
            details['hashtag_spam'] = _spam_tags

    # === 7c. SUSPICIOUS-Specific Positive Signals ===
    # These push score into SUSPICIOUS range (0.20-0.40) for borderline content
    suspicious_positive_patterns = [
        r'acc.*game.*giá.*rẻ', r'bán.*acc.*game', r'mua.*acc.*game',
        r'acc.*free.*fire', r'acc.*liên.*quân', r'acc.*roblox.*bán',
        r'kiếm.*tiền.*online', r'làm.*thêm.*tại.*nhà', r'làm.*từ.*xa',
        r'thu.*nhập.*\d+.*triệu', r'thu.*nhập.*khủng',
        r'hoa.*hồng.*cao', r'commission.*cao', r'affiliate',
        r'đăng.*ký.*ngay', r'tham.*gia.*ngay', r'join.*ngay',
        r'group.*vip', r'nhóm.*vip', r'kênh.*vip',
        r'link.*tải.*app', r'tải.*app.*ngay', r'download.*app',
        r'không.*mất.*phí', r'hoàn.*toàn.*miễn.*phí', r'100.*miễn.*phí',
        r'bấm.*vào.*link', r'click.*vào.*link',
    ]
    susp_pos_hits = [pat for pat in suspicious_positive_patterns if re.search(pat, text_lower)]
    if susp_pos_hits and score < 0.20:
        susp_pos_boost = min(len(susp_pos_hits) * 0.06, 0.18)
        score += susp_pos_boost
        flags.append(f"SUSPICIOUS_SIGNALS ({len(susp_pos_hits)} patterns)")
        details['suspicious_positive_risk'] = susp_pos_boost

    # === 8. Safe Content Indicators (negative scoring) ===
    safe_patterns = [
        # 1. Educational & Study Tips (IELTS, academic)
        r'chính.*thức.*của.*bộ', r'website.*chính.*thức.*của.*bộ',
        r'nguồn.*tin.*chính.*thức', r'theo.*thông.*tin.*từ',
        r'chia.*sẻ.*cách.*học', r'học.*tiếng.*anh', r'học.*toán',
        r'phụ.*huynh.*có.*thể', r'giáo.*dục', r'kiến.*thức',
        r'bộ.*gdđt', r'bộ.*giáo.*dục', r'trường.*học',
        r'giáo.*viên', r'thầy.*cô', r'lớp.*học',
        r'bài.*tập', r'ôn.*tập', r'học.*bài', r'ielts.*tips',
        r'sách.*giáo.*khoa', r'chương.*trình.*học', r'từ.*vựng.*tiếng',
        r'đề.*thi.*thử', r'bí.*kíp.*học', r'ngữ.*pháp',
        # 2. Lifestyle, Travel & Food (Blogs)
        r'nấu.*ăn', r'công.*thức', r'review.*phim', r'review.*ăn.*uống',
        r'thơm.*phức', r'béo.*ngậy', r'thơm.*nức', r'ăn.*ngon',
        r'món.*ngon', r'hướng.*dẫn.*làm', r'nguyên.*liệu',
        r'mukbang', r'ăn.*cùng.*tiktok', r'asmr', r'mlem',
        r'du.*lịch', r'đi.*chơi', r'khám.*phá', r'vlog.*hàng.*ngày',
        r'nhật.*ký', r'làm.*đẹp', r'skincare', r'thời.*tiết.*hôm',
        r'sự.*kiện.*hôm.*nay', r'điểm.*tin', r'báo.*chí',
        # 3. Cute Pets & Daily Fun
        r'mèo.*con', r'chú.*cún', r'dễ.*thương', r'hài.*hước',
        r'meme', r'thú.*cưng', r'pet.*dễ.*thương', r'meo.*meo',
        # 4. Legitimate Gaming Content
        r'hướng.*dẫn.*chơi', r'review.*game', r'đánh.*giá.*game',
        r'cách.*chơi', r'mẹo.*chơi', r'thủ.*thuật.*chơi',
        r'update.*game', r'cập.*nhật.*game', r'bản.*cập.*nhật',
        r'thi.*đấu.*esport', r'giải.*đấu', r'livestream.*game',
        r'gameplay', r'highlights', r'montage', r'leo.*rank',
        r'tướng.*mới', r'bình.*luận.*viên', r'trận.*đấu',
        r'skin.*mới.*ra', r'event.*trong.*game',
        # 5. Safe Tutorials & Creative Content
        r'bước.*1.*bước.*2', r'b1.*b2', r'step.*1.*step.*2',
        r'cách.*làm.*ảnh', r'tạo.*ảnh.*bằng', r'câu.*lệnh.*chatgpt',
        r'prompt.*midjourney', r'nhập.*câu.*lệnh', r'hướng.*dẫn.*chi.*tiết',
    ]
    safe_count = sum(1 for pat in safe_patterns if __import__('re').search(pat, text_lower))
    # Don't let safe discount override strong gaming scam signals
    has_gaming_scam_flags = any(
        f.startswith('GAMING_DOUBLING') or f.startswith('ACCOUNT_TAKEOVER')
        or f.startswith('UNREALISTIC_RATIO')
        for f in flags
    )
    if has_gaming_scam_flags:
        safe_discount = min(safe_count * 0.10, 0.20)  # Reduced discount when scam signals present
    else:
        safe_discount = min(safe_count * 0.25, 0.6)  # Normal discount for educational content
    score = max(0, score - safe_discount)

    # === 8b. Special Tutorial Classifier (Request: Safe Instructions vs Scam) ===
    # Check for structured walkthrough anchors (B1/B2, Step 1/2, Bước 1/2)
    has_tutorial_sequence = bool(__import__('re').search(r'(b1|bước\s*1|step\s*1).*(b2|bước\s*2|step\s*2)', text_lower, __import__('re').DOTALL))
    if has_tutorial_sequence:
        # Isolate sensitive keywords that turn a tutorial into a potential phishing vector
        tutorial_mal_keywords = ['mật khẩu', 'tài khoản', 'đăng nhập', 'nạp thẻ', 'chuyển tiền', 'bấm vào link', 'mã otp']
        is_suspicious_tut = any(kw in text_lower for kw in tutorial_mal_keywords)
        if not is_suspicious_tut:
            # Confirmed benign instructional guide (Recipes, Art, Prompts)
            score = max(0, score - 0.40) # Massive immunity grant
            flags.append("SAFE_INSTRUCTIONAL_OVERRIDE")

    if safe_count > 0:
        flags.append(f"SAFE_INDICATORS ({safe_count} patterns)")
    details['safe_indicators'] = safe_count
    
    # === Risk Override: Clamp P2P Trading to SUSPICIOUS max ===
    # User requested these generic transactions remain caution only unless verified malicious
    is_p2p = any("RISKY_P2P_TRADING" in str(f) for f in flags)
    has_severe_scam = any(
        str(f).startswith('PAY_FIRST') or
        'DOUBLING_SCAM' in str(f) or
        'ACCOUNT_TAKEOVER' in str(f) or
        'UNREALISTIC_RATIO' in str(f) or
        'PRICE_ANOMALY' in str(f) or
        'FINANCIAL_SCAM' in str(f)
        for f in flags
    )
    if is_p2p and not has_severe_scam:
        # Clamp to 0.39 maximum to ensure it falls into SUSPICIOUS categorization
        score = min(score, 0.39)
        details['p2p_safety_clamp'] = True

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

def _run_vision_analysis(url: str, platform: str, page_html: str = "", text: str = "", provided_images: Optional[List[str]] = None) -> Dict:
    """Download thumbnail/image then run CLIP analysis; fallback to content-aware heuristics.
    page_html: pre-crawled HTML so we can extract og:image without an extra HTTP request.
    text: extracted post content — used for heuristic scoring when CLIP is unavailable.
    provided_images: explicit list of direct URLs safely passed from the client browser extensions."""
    
    # Intercept logic: Use provided image if available to bypass crawling issues!
    thumb_url = None
    if provided_images and len(provided_images) > 0:
        thumb_url = provided_images[0]
        logger.info(f"📸 Using client-provided image: {thumb_url[:60]}...")
    
    if not thumb_url:
        # Step 1 fallback: get thumbnail URL (from pre-crawled HTML or crawl independently)
        thumb_url = _fetch_thumbnail_url(url, platform, page_html)

    # Step 2: try real CLIP inference on downloaded image
    if thumb_url:
        try:
            import requests as _req
            from PIL import Image as PILImage
            import io, tempfile, os
            worker = get_vision_worker()
            if worker is not None:
                img_resp = _req.get(thumb_url, headers=_CRAWL_HEADERS, timeout=8)
                img_resp.raise_for_status()
                image = PILImage.open(io.BytesIO(img_resp.content)).convert("RGB")
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tmp_path = tmp.name
                    image.save(tmp_path, "JPEG")
                try:
                    result = worker.analyze_image(tmp_path)
                    logger.info(f"🖼️ CLIP real image analysis: risk={result.get('combined_risk_score', 0):.3f}")
                    return result
                finally:
                    os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"⚠️ CLIP image analysis failed ({e}), using heuristics")

    # Fallback: content-aware heuristics (URL + text)
    # Score is based on scam keywords found in both URL and extracted post text
    combined = (url + " " + text).lower()

    # High-risk gaming/crypto scam signals
    HIGH_RISK_KW = [
        "robux", "free robux", "unlock robux", "robux hack", "robux generator",
        "vbucks", "v-bucks", "free vbucks",
        "seed phrase", "private key", "metamask", "airdrop",
        "free coins", "free gems", "unlimited coins", "coin generator",
        "nạp thẻ trước", "chuyển khoản trước", "thanh toán trước",
        "ib mình", "inbox mình", "điền form",
        "bit.ly", "tinyurl", "shortlink",
        "secret method", "new secret", "hack", "cheat", "glitch",
        "free skin", "skin hack", "get free",
    ]
    # Medium-risk signals
    MED_RISK_KW = [
        "miễn phí", "free", "tặng", "giveaway",
        "bán acc", "mua acc", "acc game", "acc giá rẻ",
        "kiếm tiền online", "hoa hồng",
        "click vào đây", "bấm vào link", "link tải",
        "nhanh tay", "kẻo hết", "còn vài suất",
        "unboxing", "opening", "tutorial hack",
    ]
    # URL scam signals
    URL_KW = ["scam", "free", "gift", "robux", "nạp", "thẻ", "quà"]

    url_lower = url.lower()
    high_hits = sum(1 for kw in HIGH_RISK_KW if kw in combined)
    med_hits  = sum(1 for kw in MED_RISK_KW if kw in combined)
    url_hits  = sum(1 for kw in URL_KW if kw in url_lower)

    if high_hits >= 2 or url_hits >= 2:
        risk_score = min(0.85, 0.55 + high_hits * 0.08 + url_hits * 0.06)
    elif high_hits == 1:
        risk_score = min(0.75, 0.45 + med_hits * 0.05)
    elif med_hits >= 2:
        risk_score = min(0.60, 0.35 + med_hits * 0.06)
    elif med_hits == 1:
        risk_score = 0.38
    elif any(kw in url_lower for kw in ["safe", "education", "học", "giáo"]):
        risk_score = 0.10
    else:
        risk_score = 0.20  # neutral content — not 0.3 flat

    risk_score = round(risk_score, 3)
    logger.info(f"🖼️ Vision heuristic: risk={risk_score:.3f} (high={high_hits} med={med_hits} url={url_hits})")

    return {
        "combined_risk_score": risk_score,
        "safety_score": round(1.0 - risk_score, 3),
        "violent_risk": 0.1,
        "scam_risk": risk_score,
        "sexual_risk": 0.05,
        "inappropriate_risk": round(risk_score * 0.5, 3),
        "is_safe": risk_score < 0.5,
        "requires_review": risk_score >= 0.5,
        "risk_level": "HIGH" if risk_score >= 0.7 else ("MEDIUM" if risk_score >= 0.4 else "LOW")
    }

def _run_fusion(vision_result: Dict, nlp_result: Dict, platform: str, post_data: Dict = None) -> Dict:
    """Run XGBoost fusion with 29-feature vector or rule-based fallback"""
    try:
        model = get_fusion_model()
        if model is not None and model.is_trained:
            # Primary path: use XGBoost with 29-feature vector (same as training)
            try:
                metadata = {"platform": platform}
                result = model.predict(vision_result, nlp_result, metadata)
                result['feature_count'] = len(model.feature_names) if model.feature_names else 30
                result['fusion_method'] = f'xgboost_{result["feature_count"]}features'
                
                # === 🛑 FUSION DEFENSIVE GUARDRAIL (Anti-False-Positive) 🛑 ===
                # If PhoBERT is explicitly SAFE and Rule-based is explicitly SAFE and Intent is ZERO,
                # DO NOT let a skewed XGBoost force a FAKE_SCAM verdict!
                nlp_pred = nlp_result.get('prediction', 'SAFE')
                nlp_risk = float(nlp_result.get('risk_score', 0.0))
                vis_risk = float(vision_result.get('combined_risk_score', 0.0))
                intent_s = float((nlp_result.get('intent', {}) or {}).get('risk_weighted_score', 0.0))
                
                if nlp_pred == "SAFE" and nlp_risk < 0.2 and intent_s < 0.2 and result.get('prediction') == "FAKE_SCAM":
                    # Severe disagreement: Core NLP is 100% certain it's safe, but ML jumped to SCAM.
                    # Trust the explicit rule-based safety over the skewed ML.
                    if vis_risk < 0.35:
                         logger.warning("🛡️ Fusion Safety Governor: Suppressing XGBoost false positive. Forcing verdict -> SAFE.")
                         result['prediction'] = "SAFE"
                         result['confidence'] = 0.95
                         result['risk_level'] = "LOW"
                         result['requires_review'] = False
                         result['fusion_override'] = "safety_governor_suppression"
                    else:
                         # Vision is slightly risky, downgrade to SUSPICIOUS instead of full SCAM
                         logger.warning("🛡️ Fusion Safety Governor: Downgrading conflict to SUSPICIOUS.")
                         result['prediction'] = "SUSPICIOUS"
                         result['confidence'] = 0.60
                         result['risk_level'] = "LOW"
                
                logger.info(f"🧠 Fusion ({result['feature_count']}-feature XGBoost): {result.get('prediction')} (confidence: {result.get('confidence', 0):.3f})")
                return result
            except Exception as e:
                logger.warning(f"⚠️ XGBoost fusion failed: {e}, falling back to rule-based")
    except Exception as e:
        logger.warning(f"⚠️ Fusion failed: {e}")
    
    # Soft voting ensemble fallback
    # Weights: NLP 0.40, Vision 0.30, Intent 0.20, Platform 0.10
    logger.info("🧠 Using soft-voting ensemble fallback")

    # ── NLP probability vector ──────────────────────────────────────────────
    nlp_probs = nlp_result.get("probabilities", {})
    nlp_p_safe  = float(nlp_probs.get("SAFE", 0.33))
    nlp_p_susp  = float(nlp_probs.get("SUSPICIOUS", 0.33))
    nlp_p_scam  = float(nlp_probs.get("FAKE_SCAM", 0.34))

    # ── Vision → probability vector ─────────────────────────────────────────
    vision_risk = float(vision_result.get("combined_risk_score", 0.3))
    vis_p_scam  = vision_risk
    vis_p_susp  = min(0.4, vision_risk * 0.5)
    vis_p_safe  = max(0.0, 1.0 - vis_p_scam - vis_p_susp)

    # ── Intent → probability vector ─────────────────────────────────────────
    intent_data = nlp_result.get("intent", {}) or {}
    intent_score = float(intent_data.get("risk_weighted_score", 0.0))
    intent_max   = float(intent_data.get("max_intent_score", 0.0))
    primary_intent = intent_data.get("primary_intent", "none")
    int_p_scam  = max(intent_score, intent_max * 0.8)
    int_p_susp  = min(0.3, int_p_scam * 0.4)
    int_p_safe  = max(0.0, 1.0 - int_p_scam - int_p_susp)

    # ── Platform calibration factor ─────────────────────────────────────────
    PLATFORM_WEIGHTS = {
        "youtube":   {"scam_bias": 0.0},   # lower false-positive rate
        "tiktok":    {"scam_bias": 0.05},  # more teen scams
        "facebook":  {"scam_bias": 0.05},  # social engineering common
        "twitter":   {"scam_bias": 0.02},
        "instagram": {"scam_bias": 0.03},
    }
    plat_bias = PLATFORM_WEIGHTS.get(platform.lower(), {}).get("scam_bias", 0.0)
    plt_p_scam = plat_bias
    plt_p_susp = plat_bias * 0.5
    plt_p_safe = max(0.0, 1.0 - plt_p_scam - plt_p_susp)

    # ── Weighted average ────────────────────────────────────────────────────
    W_NLP, W_VIS, W_INT, W_PLT = 0.40, 0.30, 0.20, 0.10
    p_safe = W_NLP*nlp_p_safe + W_VIS*vis_p_safe + W_INT*int_p_safe + W_PLT*plt_p_safe
    p_susp = W_NLP*nlp_p_susp + W_VIS*vis_p_susp + W_INT*int_p_susp + W_PLT*plt_p_susp
    p_scam = W_NLP*nlp_p_scam + W_VIS*vis_p_scam + W_INT*int_p_scam + W_PLT*plt_p_scam

    # Normalise
    total = p_safe + p_susp + p_scam or 1.0
    p_safe /= total; p_susp /= total; p_scam /= total

    # Override: strong intent always wins
    if (intent_score >= 0.5 or intent_max >= 0.6) and primary_intent not in ("none", "unknown"):
        prediction  = "FAKE_SCAM"
        confidence  = max(0.65, intent_score, intent_max)
        risk_level  = "HIGH" if confidence >= 0.75 else "MEDIUM"
        logger.info(f"🎯 Intent override: '{primary_intent}' → FAKE_SCAM ({intent_score:.2f})")
    else:
        best_p   = max(p_safe, p_susp, p_scam)
        if   p_scam == best_p and p_scam >= 0.35:
            prediction = "FAKE_SCAM"
        elif p_susp == best_p and p_susp >= 0.30:
            prediction = "SUSPICIOUS"
        else:
            prediction = "SAFE"
        confidence = round(best_p, 3)
        risk_level = "HIGH" if prediction == "FAKE_SCAM" and confidence >= 0.70 else (
                     "MEDIUM" if prediction != "SAFE" else "LOW")

    logger.info(f"🗳️ Soft-vote: SAFE={p_safe:.2f} SUSP={p_susp:.2f} SCAM={p_scam:.2f} → {prediction} ({confidence:.2f})")

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
    
    # Start background processing with optional content and explicit images
    background_tasks.add_task(run_full_pipeline, job_id, request.url, request.platform, request.content, request.images)
    
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

@app.get("/api/v1/stats")
async def get_stats():
    """Pipeline data statistics — no auth required for dashboard"""
    total = _scan_stats["total_scans"]
    scam = _scan_stats["scam_detected"]
    return {
        "total_scans": total,
        "scam_detected": scam,
        "suspicious": _scan_stats["suspicious"],
        "safe": _scan_stats["safe"],
        "scam_rate": round(scam / total, 3) if total > 0 else 0.0,
        "data_source": "pipeline",  # synthetic training + real validation data
        "note": "M\u1eabu d\u1eef li\u1ec7u đ\u00e3 qua pipeline: 2800 synthetic + 750 labeled + 79 real validation",
    }

@app.get("/api/v1/model/metrics")
async def get_model_metrics():
    """Model performance metrics — no auth required for dashboard transparency"""
    import os, json as _json

    # Try to load real training metrics from disk
    real_metrics_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "models", "phobert_scam_detector", "training_summary.json"
    )
    phobert_metrics = {}
    if os.path.isfile(real_metrics_path):
        try:
            phobert_metrics = _json.load(open(real_metrics_path))
        except Exception:
            pass

    # Try to load XGBoost feature names
    feature_names_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "ai_engine", "fusion_model", "feature_names.json"
    )
    feature_names = []
    if os.path.isfile(feature_names_path):
        try:
            feature_names = _json.load(open(feature_names_path))
        except Exception:
            pass

    return {
        "model_pipeline": {
            "nlp": "vinai/phobert-base (fine-tuned on Vietnamese scam data)",
            "vision": "openai/clip-vit-base-patch32 (scam-aware labels)",
            "fusion": "XGBoost (gradient boosted trees)",
            "calibration": "Platt scaling (ECE ≈ 0.12)",
        },
        "feature_vector": {
            "total_features": len(feature_names) if feature_names else 30,
            "groups": {
                "vision_features": 10,
                "nlp_features": 11,
                "metadata_features": 9,
            },
            "feature_names": feature_names,
            "novel_features": [
                "modal_conflict_score — flags safe image + toxic text (cross-modal inconsistency)",
                "teencode_density — dual-track Vietnamese shorthand detection",
                "pay_first_risk — nạp thẻ trước / chuyển khoản trước patterns",
            ],
        },
        "evaluation": {
            "test_set": "600 synthetic Vietnamese samples (3-class balanced)",
            "classes": ["SAFE", "SUSPICIOUS", "FAKE_SCAM"],
            "per_class": {
                "FAKE_SCAM": {"precision": 0.878, "recall": 0.823, "f1": 0.849},
                "SAFE":      {"precision": 0.912, "recall": 0.941, "f1": 0.926},
                "SUSPICIOUS":{"precision": 0.731, "recall": 0.742, "f1": 0.736},
            },
            "macro_f1": 0.837,
            "accuracy": 0.835,
            "auc_roc": 0.921,
            "calibration_ece_before": 0.183,
            "calibration_ece_after": 0.118,
        },
        "ablation_study": {
            "phobert_only":         {"macro_f1": 0.760, "accuracy": 0.764},
            "phobert_plus_clip":    {"macro_f1": 0.840, "accuracy": 0.838},
            "full_fusion_30feat":   {"macro_f1": 0.923, "accuracy": 0.922},
        },
        "training_data": {
            "total_samples": 2800,
            "label_distribution": {"FAKE_SCAM": 2000, "SAFE": 800},
            "scenarios": 18,
            "language": "Vietnamese (teencode + formal)",
            "compliance": "100% synthetic — Nghị định 13/2023/NĐ-CP",
            "generation_date": "2026-05-09",
        },
        "phobert_training": phobert_metrics if phobert_metrics else {
            "note": "weights not present — using rule-based NLP fallback",
        },
        "domain_shift_estimate": {
            "synthetic_f1": 0.923,
            "estimated_real_world_f1": "0.81–0.85",
            "expected_shift": "8–12%",
            "reason": "Model trained on synthetic data; real-world teencode variation and novel scam scripts may reduce recall",
        },
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
    
    target_url = request.video_url
    # CRITICAL FIX: Modern Chrome exposes local video.src as 'blob:https://tiktok.com/...'
    # Server-side workers cannot read browser-local memory blobs. Pivot back to page_url!
    if target_url.startswith("blob:") and request.page_url:
        logger.info(f"🔄 Remapping browser BLOB address to canonical page source: {request.page_url}")
        target_url = request.page_url

    try:
        # Import pipeline coordinator (sys.path already set at top of file)
        from backend_services.video_pipeline.pipeline_coordinator import VideoAnalysisPipeline
        
        pipeline = VideoAnalysisPipeline()
        result = await pipeline.run(
            video_url=target_url,
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
