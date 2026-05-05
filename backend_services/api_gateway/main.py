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
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

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
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security
security = HTTPBearer()

# Global job storage (in production, use Redis/database)
active_jobs = {}
job_results = {}

# Pydantic models
class AnalyzeRequest(BaseModel):
    """Request model for content analysis"""
    url: str = Field(..., description="URL to analyze")
    platform: str = Field(..., description="Platform: youtube | facebook | tiktok")
    priority: str = Field(default="normal", description="Priority: low | normal | high")
    
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

# Authentication
async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify JWT token or API key"""
    token = credentials.credentials
    
    # Simple token validation (in production, use proper JWT verification)
    valid_tokens = {
        "demo-token-123": {"user": "demo", "permissions": ["analyze"]},
        "test-token-456": {"user": "test", "permissions": ["analyze", "admin"]}
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
async def run_full_pipeline(job_id: str, url: str, platform: str):
    """Run complete analysis pipeline"""
    try:
        start_time = datetime.now()
        
        # Stage 1: Crawling metadata
        update_job_progress(job_id, 10.0, "🔍 Crawling metadata...")
        await asyncio.sleep(1)  # Simulate crawling
        
        # Stage 2: Quarantine check
        update_job_progress(job_id, 20.0, "🛡️ Quarantine check passed...")
        await asyncio.sleep(0.5)
        
        # Stage 3: Vision analysis
        update_job_progress(job_id, 40.0, "🖼️ CLIP vision analysis running...")
        await asyncio.sleep(2)  # Simulate vision processing
        
        # Stage 4: NLP analysis
        update_job_progress(job_id, 60.0, "📝 PhoBERT NLP analysis running...")
        await asyncio.sleep(1.5)  # Simulate NLP processing
        
        # Stage 5: Fusion decision
        update_job_progress(job_id, 80.0, "🧠 XGBoost decision fusion...")
        await asyncio.sleep(1)  # Simulate fusion
        
        # Stage 6: Graph update
        update_job_progress(job_id, 90.0, "🕸️ Updating Neo4j graph...")
        await asyncio.sleep(0.5)  # Simulate graph update
        
        # Generate result
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Mock analysis result (in production, get from actual AI models)
        result = {
            "label": "SAFE" if url.endswith("safe") else "FAKE_SCAM",
            "confidence": 0.92 if url.endswith("safe") else 0.87,
            "risk_level": "LOW" if url.endswith("safe") else "HIGH",
            "needs_review": not url.endswith("safe"),
            "analysis_details": {
                "vision_risk": 0.1 if url.endswith("safe") else 0.8,
                "nlp_risk": 0.05 if url.endswith("safe") else 0.9,
                "fusion_score": 0.92 if url.endswith("safe") else 0.87,
                "platform_specific": {
                    "platform": platform,
                    "content_type": "video" if platform == "youtube" else "post"
                }
            },
            "processing_time": processing_time,
            "created_at": datetime.now().isoformat()
        }
        
        # Complete job
        complete_job(job_id, result)
        
    except Exception as e:
        fail_job(job_id, str(e))

# API Endpoints
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
    
    # Start background processing
    background_tasks.add_task(run_full_pipeline, job_id, request.url, request.platform)
    
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

# Run server
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
