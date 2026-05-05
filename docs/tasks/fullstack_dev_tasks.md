# 🚀 Full-stack Developer Tasks - Member 4

> **Timeline:** 4 weeks | **Priority:** 🔴 High | **Tầng:** 6

## 📋 Week 1: Backend API Foundation

### Day 1-2: FastAPI Setup
- [ ] **API Gateway architecture**
  ```python
  # File: backend_services/api_gateway/main.py
  from fastapi import FastAPI, HTTPException, BackgroundTasks
  from fastapi.responses import StreamingResponse
  from pydantic import BaseModel
  
  app = FastAPI(title="ViFake Analytics API", version="1.0.0")
  
  class AnalyzeRequest(BaseModel):
      url: str
      platform: str  # youtube | facebook | tiktok
  
  class AnalyzeResponse(BaseModel):
      post_id: str
      label: str
      confidence: float
      needs_review: bool
  ```

- [ ] **Core endpoints**
  ```python
  # File: backend_services/api_gateway/endpoints/analysis.py
  @app.post("/api/v1/analyze", response_model=AnalyzeResponse)
  async def analyze_post(req: AnalyzeRequest, bg: BackgroundTasks):
      """B2B endpoint: Analyze content URL"""
      job_id = create_analysis_job(req.url, req.platform)
      bg.add_task(run_full_pipeline, job_id, req.url, req.platform)
      return {"job_id": job_id, "status": "processing"}
  
  @app.get("/api/v1/stream/{job_id}")
  async def stream_progress(job_id: str):
      """SSE endpoint for real-time progress"""
      async def event_generator():
          stages = [
              "🔍 Crawling metadata...",
              "🛡️ Quarantine check passed...",
              "🖼️ CLIP vision analysis running...",
              "📝 PhoBERT NLP analysis running...",
              "🧠 XGBoost decision fusion...",
              "🕸️ Updating Neo4j graph...",
              "✅ Analysis complete.",
          ]
          for stage in stages:
              yield f"data: {json.dumps({'stage': stage})}\n\n"
              await asyncio.sleep(0.8)
      return StreamingResponse(event_generator(), media_type="text/event-stream")
  ```

- [ ] **Authentication & Security**
  ```python
  # File: backend_services/api_gateway/auth/security.py
  - JWT token authentication
  - API key management
  - Rate limiting
  - CORS configuration
  ```

### Day 3-4: Service Integration
- [ ] **AI Engine integration**
  ```python
  # File: backend_services/api_gateway/services/ai_service.py
  async def call_vision_analysis(image_path: str):
      # Call CLIP inference service
      return vision_result
  
  async def call_nlp_analysis(text: str):
      # Call PhoBERT inference service
      return nlp_result
  
  async def call_fusion_model(features: dict):
      # Call XGBoost fusion model
      return fusion_result
  ```

- [ ] **Data pipeline integration**
  ```python
  # File: backend_services/api_gateway/services/data_service.py
  async def trigger_crawling(platform: str, profile_id: str):
      # Trigger honeypot crawler
      return crawl_result
  
  async def get_post_metadata(post_id: str):
      # Fetch from MongoDB
      return metadata
  ```

- [ ] **Graph analytics integration**
  ```python
  # File: backend_services/api_gateway/services/graph_service.py
  async def get_botnet_graph(post_id: str):
      # Query Neo4j for network visualization
      return graph_data
  
  async def get_propagation_analysis(post_id: str):
      # Analyze content propagation
      return propagation_data
  ```

### Day 5-7: Database Integration
- [ ] **MongoDB connection**
  ```python
  # File: backend_services/api_gateway/database/mongo_client.py
  from pymongo import MongoClient
  
  client = MongoClient("mongodb://localhost:27017/")
  db = client["vifake"]
  
  class PostRepository:
      def create_post(self, post_data: dict):
          return db.posts.insert_one(post_data)
      
      def get_post(self, post_id: str):
          return db.posts.find_one({"post_id": post_id})
  ```

- [ ] **PostgreSQL connection**
  ```python
  # File: backend_services/api_gateway/database/postgres_client.py
  import asyncpg
  
  class DataMartRepository:
      async def get_analytics_summary(self, date_range: str):
          # Fetch from PostgreSQL data mart
          return summary_data
  
      async def sync_graph_metrics(self):
          # Sync Neo4j metrics to PostgreSQL
          pass
  ```

- [ ] **Redis caching**
  ```python
  # File: backend_services/api_gateway/cache/redis_client.py
  import redis
  
  redis_client = redis.Redis(host="localhost", port=6379, db=0)
  
  class CacheService:
      def get_cached_result(self, job_id: str):
          return redis_client.get(f"result:{job_id}")
      
      def cache_result(self, job_id: str, result: dict):
          redis_client.setex(f"result:{job_id}", 3600, json.dumps(result))
  ```

## 📋 Week 2: Human Review UI

### Day 8-10: React Setup
- [ ] **Project initialization**
  ```bash
  # File: backend_services/human_review_ui/package.json
  {
    "name": "vifake-review-ui",
    "version": "1.0.0",
    "dependencies": {
      "react": "^18.2.0",
      "react-router-dom": "^6.8.0",
      "axios": "^1.6.0",
      "@mui/material": "^5.14.0",
      "@emotion/react": "^11.11.0",
      "@emotion/styled": "^11.11.0"
    }
  }
  ```

- [ ] **Component structure**
  ```typescript
  // File: backend_services/human_review_ui/src/components/ReviewCard.tsx
  interface ReviewItem {
    post_id: string;
    url: string;
    title: string;
    ai_label: string;
    confidence: number;
    vision_score: number;
    nlp_score: number;
  }
  
  export function ReviewCard({ item, onSubmit }: { 
    item: ReviewItem; 
    onSubmit: (label: string) => void 
  }) {
    return (
      <div className="review-card">
        <h3>{item.title}</h3>
        <p>AI gợi ý: <strong>{item.ai_label}</strong> ({(item.confidence * 100).toFixed(1)}%)</p>
        <p>Vision: {item.vision_score.toFixed(2)} | NLP: {item.nlp_score.toFixed(2)}</p>
        
        <div className="label-buttons">
          {LABELS.map(label => (
            <button
              key={label}
              onClick={() => onSubmit(label)}
              className={label === item.ai_label ? "suggested" : ""}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    );
  }
  ```

- [ ] **Review queue page**
  ```typescript
  // File: backend_services/human_review_ui/src/pages/ReviewQueue.tsx
  export function ReviewQueue() {
    const [items, setItems] = useState<ReviewItem[]>([]);
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {
      fetchPendingReviews();
    }, []);
    
    const handleSubmitReview = async (postId: string, label: string) => {
      await submitReview(postId, label);
      fetchPendingReviews(); // Refresh queue
    };
    
    return (
      <div className="review-queue">
        <h2>Pending Reviews</h2>
        {items.map(item => (
          <ReviewCard 
            key={item.post_id}
            item={item}
            onSubmit={(label) => handleSubmitReview(item.post_id, label)}
          />
        ))}
      </div>
    );
  }
  ```

### Day 11-14: Advanced UI Features
- [ ] **Real-time progress tracking**
  ```typescript
  // File: backend_services/human_review_ui/src/components/ProgressTracker.tsx
  export function ProgressTracker({ jobId }: { jobId: string }) {
    const [stages, setStages] = useState<string[]>([]);
    const [currentStage, setCurrentStage] = useState(0);
    
    useEffect(() => {
      const eventSource = new EventSource(`/api/v1/stream/${jobId}`);
      
      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setStages(prev => [...prev, data.stage]);
        setCurrentStage(prev => prev + 1);
      };
      
      return () => eventSource.close();
    }, [jobId]);
    
    return (
      <div className="progress-tracker">
        {stages.map((stage, index) => (
          <div 
            key={index}
            className={`stage ${index <= currentStage ? 'completed' : 'pending'}`}
          >
            {stage}
          </div>
        ))}
      </div>
    );
  }
  ```

- [ ] **Graph visualization**
  ```typescript
  // File: backend_services/human_review_ui/src/components/GraphVisualization.tsx
  export function GraphVisualization({ postId }: { postId: string }) {
    const [graphData, setGraphData] = useState<any>(null);
    
    useEffect(() => {
      fetchBotnetGraph(postId).then(setGraphData);
    }, [postId]);
    
    return (
      <div className="graph-container">
        {/* Neo4j Bloom iframe or custom D3.js visualization */}
        <iframe 
          src={`http://localhost:7474/bloom?post_id=${postId}`}
          width="100%" 
          height="600px"
        />
      </div>
    );
  }
  ```

- [ ] **Analytics dashboard**
  ```typescript
  // File: backend_services/human_review_ui/src/pages/Analytics.tsx
  export function Analytics() {
    return (
      <div className="analytics">
        <h2>Analytics Dashboard</h2>
        {/* Metabase iframe embed */}
        <iframe 
          src="http://localhost:3001/public/dashboard/1"
          width="100%" 
          height="800px"
        />
      </div>
    );
  }
  ```

## 📋 Week 3: Advanced Features

### Day 15-17: Performance & Security
- [ ] **API optimization**
  ```python
  # File: backend_services/api_gateway/optimization/performance.py
  - Request batching
  - Response caching
  - Connection pooling
  - Async processing
  ```

- [ ] **Security hardening**
  ```python
  # File: backend_services/api_gateway/security/hardening.py
  - Input validation
  - SQL injection prevention
  - XSS protection
  - Rate limiting per user
  ```

- [ ] **Monitoring & logging**
  ```python
  # File: backend_services/api_gateway/monitoring/logging.py
  import structlog
  
  logger = structlog.get_logger()
  
  @app.middleware("http")
  async def log_requests(request: Request, call_next):
      start_time = time.time()
      response = await call_next(request)
      process_time = time.time() - start_time
      
      logger.info(
          "request_processed",
          method=request.method,
          url=str(request.url),
          status_code=response.status_code,
          process_time=process_time
      )
      
      return response
  ```

### Day 18-21: Deployment & DevOps
- [ ] **Docker configuration**
  ```dockerfile
  # File: backend_services/api_gateway/Dockerfile
  FROM python:3.11-slim
  
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install -r requirements.txt
  
  COPY . .
  
  EXPOSE 8000
  CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```

- [ ] **Docker Compose services**
  ```yaml
  # File: infrastructure/docker/docker-compose.yml
  services:
    api-gateway:
      build: ../backend_services/api_gateway
      ports:
        - "8000:8000"
      depends_on:
        - mongodb
        - postgres
        - redis
        - neo4j
    
    review-ui:
      build: ../backend_services/human_review_ui
      ports:
        - "3000:3000"
      depends_on:
        - api-gateway
  ```

- [ ] **CI/CD pipeline**
  ```yaml
  # File: .github/workflows/deploy.yml
  name: Deploy
  on:
    push:
      branches: [main]
  jobs:
    deploy:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v3
        - name: Deploy to production
          run: |
            docker-compose down
            docker-compose up -d --build
  ```

## 📋 Week 4: Integration & Demo

### Day 22-24: Integration Testing
- [ ] **End-to-end testing**
  ```python
  # File: backend_services/tests/test_e2e.py
  import pytest
  from fastapi.testclient import TestClient
  
  def test_full_analysis_pipeline():
      client = TestClient(app)
      
      # Start analysis
      response = client.post("/api/v1/analyze", json={
          "url": "https://youtube.com/watch?v=test",
          "platform": "youtube"
      })
      assert response.status_code == 200
      job_id = response.json()["job_id"]
      
      # Check progress
      response = client.get(f"/api/v1/stream/{job_id}")
      assert response.status_code == 200
      
      # Get result
      response = client.get(f"/api/v1/result/{job_id}")
      assert response.status_code == 200
      assert "label" in response.json()
  ```

- [ ] **Load testing**
  ```python
  # File: backend_services/tests/load_test.py
  import asyncio
  import aiohttp
  
  async def load_test():
      async with aiohttp.ClientSession() as session:
          tasks = []
          for i in range(100):
              task = analyze_content(session, f"https://test.com/{i}")
              tasks.append(task)
          
          results = await asyncio.gather(*tasks)
          return results
  ```

### Day 25-28: Demo Preparation
- [ ] **Demo environment setup**
  ```python
  # File: scripts/demo/setup_demo.py
  - Pre-populate demo data
  - Start all services
  - Verify health checks
  - Generate demo URLs
  ```

- [ ] **Demo scripts**
  ```python
  # File: scripts/demo/run_demo.py
  def run_demo_scenario():
      # Scenario 1: Scam detection
      # Scenario 2: Botnet analysis
      # Scenario 3: Human review workflow
      # Scenario 4: Real-time analytics
  ```

- [ ] **Documentation**
  ```markdown
  # File: docs/api/README.md
  - API endpoint documentation
  - Authentication guide
  - Rate limiting info
  - Error handling guide
  ```

## 🎯 Deliverables

### Backend API
- `backend_services/api_gateway/` - FastAPI application
- `backend_services/api_gateway/tests/` - Test suite
- `backend_services/api_gateway/docs/` - API documentation

### Frontend UI
- `backend_services/human_review_ui/` - React application
- `backend_services/human_review_ui/src/` - Components & pages
- `backend_services/human_review_ui/public/` - Static assets

### Deployment
- `infrastructure/docker/` - Docker configurations
- `infrastructure/nginx/` - Reverse proxy setup
- `.github/workflows/` - CI/CD pipelines

## 🔧 Technical Requirements

### Backend Dependencies
```python
# requirements.txt
fastapi==0.104.0
uvicorn[standard]==0.24.0
pydantic==2.5.0
pymongo==4.6.0
asyncpg==0.29.0
redis==5.0.1
python-jose[cryptography]==3.3.0
```

### Frontend Dependencies
```json
// package.json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-router-dom": "^6.8.0",
    "axios": "^1.6.0",
    "@mui/material": "^5.14.0",
    "@emotion/react": "^11.11.0",
    "@emotion/styled": "^11.11.0",
    "d3": "^7.8.0",
    "react-d3-graph": "^2.6.0"
  }
}
```

## 🚨 Critical Path Items

1. **FastAPI setup & core endpoints** - Day 2
2. **Service integration** - Day 4
3. **React UI foundation** - Day 10
4. **Real-time features** - Day 14
5. **Deployment setup** - Day 21

## 📊 Performance Targets

| Metric | Target | Current |
|---|---|---|
| API response time | <500ms | TBD |
| UI load time | <3s | TBD |
| Concurrent users | 100+ | TBD |
| Uptime | 99.9% | TBD |

## 🔒 Security Requirements

- JWT authentication for all endpoints
- API rate limiting (100 requests/minute)
- Input validation & sanitization
- HTTPS enforcement
- CORS configuration
- Security headers (HSTS, CSP)

## 🔄 Monitoring & Observability

### Application Metrics
```python
# File: backend_services/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Active connections')
```

### Health Checks
```python
# File: backend_services/health/health_check.py
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "services": {
            "mongodb": await check_mongodb(),
            "postgres": await check_postgres(),
            "redis": await check_redis(),
            "neo4j": await check_neo4j()
        }
    }
```

## 📞 Support & Collaboration

- **Daily sync:** 2PM with team
- **API coordination:** Daily with Member 2 (AI/ML)
- **Data coordination:** Daily with Member 1 (Data Engineer)
- **Graph coordination:** Daily with Member 3 (Graph Analyst)

---

**Owner:** Member 4 (Full-stack Developer)  
**Timeline:** 4 weeks  
**Status:** 🔄 In Progress
