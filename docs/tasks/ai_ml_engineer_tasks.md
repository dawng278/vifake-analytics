# 🤖 AI/ML Engineer Tasks - Member 2

> **Timeline:** 4 weeks | **Priority:** 🔴 High | **Tầng:** 3-5

## 📋 Week 1: AI Engine Foundation

### Day 1-2: Vision Worker Setup
- [ ] **CLIP FP16 Implementation**
  ```python
  # File: ai_engine/vision_worker/clip_inference.py
  - Load CLIP model with FP16 (RTX 2050 4GB VRAM)
  - Zero-shot classification setup
  - Memory optimization (no gradients, cleanup)
  ```

- [ ] **Vision risk scoring**
  ```python
  # File: ai_engine/vision_worker/clip_inference.py
  CANDIDATE_LABELS = [
      "child-safe cartoon content",
      "violent or disturbing content targeting children",
      "scam or phishing content",
      "sexual content",
      "normal educational content",
  ]
  
  def get_vision_risk_score(image_path: str) -> float:
      # Aggregate risk labels into single score
  ```

- [ ] **GPU memory management**
  ```python
  # File: ai_engine/vision_worker/kill_switch.py
  - Emergency VRAM clearing
  - Batch processing optimization
  - OOM prevention
  ```

### Day 3-4: NLP Worker Setup
- [ ] **PhoBERT ONNX conversion**
  ```bash
  # Convert PhoBERT to ONNX (one-time setup)
  optimum-cli export onnx \
    --model vinai/phobert-base \
    --task text-classification \
    ai_engine/nlp_worker/phobert_onnx/
  ```

- [ ] **PhoBERT inference implementation**
  ```python
  # File: ai_engine/nlp_worker/phobert_inference.py
  - ONNX model loading
  - Fast CPU inference
  - Batch processing support
  ```

- [ ] **RAG vector database setup**
  ```python
  # File: ai_engine/nlp_worker/rag_setup.py
  - Chroma vector store
  - Vietnamese embeddings
  - Scam pattern indexing
  ```

### Day 5-7: Fusion Model Development
- [ ] **XGBoost meta-learner**
  ```python
  # File: ai_engine/fusion_model/xgboost_fusion.py
  LABELS = ["SAFE", "FAKE_TOXIC", "FAKE_SCAM", "FAKE_MISINFO"]
  
  class FusionClassifier:
      def predict(self, vision_score, nlp_features):
          # Multi-modal decision fusion
  ```

- [ ] **Feature engineering**
  ```python
  # File: ai_engine/fusion_model/feature_engineering.py
  def extract_features(vision_result, nlp_result, metadata):
      # Combine multi-modal features
      return feature_vector
  ```

- [ ] **Model training pipeline**
  ```python
  # File: ai_engine/fusion_model/train_model.py
  - Cross-validation setup
  - Hyperparameter tuning
  - Model evaluation metrics
  ```

## 📋 Week 2: Advanced AI Features

### Day 8-10: Model Optimization
- [ ] **Quantization & optimization**
  ```python
  # File: ai_engine/optimization/model_quantization.py
  - INT8 quantization for inference
  - TensorRT optimization (GPU)
  - ONNX runtime optimization
  ```

- [ ] **Batch processing**
  ```python
  # File: ai_engine/processing/batch_inference.py
  - Parallel processing
  - Memory-efficient batching
  - Queue management
  ```

- [ ] **Performance benchmarking**
  ```python
  # File: ai_engine/benchmark/model_performance.py
  - Latency measurement
  - Throughput testing
  - Resource utilization
  ```

### Day 11-14: Active Learning Setup
- [ ] **Uncertainty sampling**
  ```python
  # File: ai_engine/mlops/uncertainty_sampling.py
  def get_uncertainty_score(predictions):
      # Calculate prediction uncertainty
      return uncertainty_score
  ```

- [ ] **Human review queue**
  ```python
  # File: ai_engine/mlops/review_queue.py
  def push_to_review(post_id, ai_result, confidence):
      # Queue items with 40-60% confidence
  ```

- [ ] **MLflow integration**
  ```python
  # File: ai_engine/mlops/mlflow_tracking.py
  - Experiment tracking
  - Model versioning
  - Performance logging
  ```

## 📋 Week 3: MLOps Pipeline

### Day 15-17: Automated Retraining
- [ ] **Retraining trigger logic**
  ```python
  # File: ai_engine/mlops/auto_retrain.py
  def check_retrain_trigger():
      # Check if 500+ new labeled samples
      if count >= RETRAIN_THRESHOLD:
          trigger_retrain()
  ```

- [ ] **Hot model swapping**
  ```python
  # File: ai_engine/mlops/model_swapping.py
  def atomic_model_swap(new_model_path):
      # Zero downtime model update
  ```

- [ ] **Data validation**
  ```python
  # File: ai_engine/mlops/data_validation.py
  - Feature distribution checks
  - Data quality validation
  - Drift detection
  ```

### Day 18-21: Model Monitoring
- [ ] **Performance monitoring**
  ```python
  # File: ai_engine/monitoring/model_monitoring.py
  - Real-time inference metrics
  - Model drift detection
  - Alert system
  ```

- [ ] **Explainability**
  ```python
  # File: ai_engine/explainability/shap_analysis.py
  - Feature importance analysis
  - Decision explanation
  - Error analysis
  ```

## 📋 Week 4: Integration & Demo

### Day 22-24: API Integration
- [ ] **AI service endpoints**
  ```python
  # File: ai_engine/api/ai_service.py
  @app.post("/api/v1/analyze")
  async def analyze_content(request):
      # Multi-modal analysis endpoint
  ```

- [ ] **Model serving**
  ```python
  # File: ai_engine/serving/model_server.py
  - FastAPI model server
  - Request batching
  - Response caching
  ```

### Day 25-28: Demo Preparation
- [ ] **Demo models**
  ```python
  # File: ai_engine/demo/demo_models.py
  - Pre-trained demo models
  - Sample predictions
  - Performance showcase
  ```

- [ ] **Testing & validation**
  ```python
  # File: ai_engine/tests/test_pipeline.py
  - Unit tests (>90%)
  - Integration tests
  - Performance tests
  ```

## 🎯 Deliverables

### AI Models
- `ai_engine/vision_worker/` - CLIP FP16 implementation
- `ai_engine/nlp_worker/` - PhoBERT ONNX + RAG
- `ai_engine/fusion_model/` - XGBoost meta-learner

### MLOps Pipeline
- `ai_engine/mlops/` - Active learning & retraining
- `ai_engine/monitoring/` - Model monitoring
- `ai_engine/api/` - Model serving endpoints

### Documentation
- Model architecture docs
- Training procedures
- Performance benchmarks
- API documentation

## 🔧 Technical Requirements

### Dependencies
```python
# requirements.txt
torch==2.1.0
transformers==4.36.0
optimum[onnxruntime]==1.16.0
xgboost==2.0.0
mlflow==2.8.0
chromadb==0.4.18
```

### Hardware Requirements
- GPU: RTX 2050 (4GB VRAM minimum)
- CPU: Intel Core i5+ (for PhoBERT ONNX)
- RAM: 16GB+ (for batch processing)
- Storage: SSD 100GB+ (for models)

## 🚨 Critical Path Items

1. **CLIP FP16 implementation** - Day 2
2. **PhoBERT ONNX setup** - Day 4
3. **XGBoost fusion model** - Day 7
4. **Active learning pipeline** - Day 14
5. **API integration** - Day 24

## 📊 Model Performance Targets

| Metric | Target | Current |
|---|---|---|
| Vision inference latency | <200ms | TBD |
| NLP inference latency | <100ms | TBD |
| Fusion accuracy | >90% | TBD |
| Memory usage | <4GB VRAM | TBD |
| Model retrain time | <30min | TBD |

## 🔄 Continuous Integration

### Model Training Pipeline
```yaml
# .github/workflows/model_training.yml
name: Model Training
on:
  push:
    paths: ['ai_engine/**']
jobs:
  train:
    runs-on: gpu
    steps:
      - uses: actions/checkout@v3
      - name: Train models
        run: python ai_engine/fusion_model/train_model.py
      - name: Upload to MLflow
        run: mlflow models log-model ...
```

### Quality Gates
- Model accuracy >90%
- Inference latency <300ms
- Memory usage <4GB VRAM
- Test coverage >90%

## 📞 Support & Collaboration

- **Daily sync:** 10AM with team
- **Model review:** Weekly with Member 3 (Graph Analyst)
- **API coordination:** Daily with Member 4 (Full-stack)
- **Data coordination:** Daily with Member 1 (Data Engineer)

---

**Owner:** Member 2 (AI/ML Engineer)  
**Timeline:** 4 weeks  
**Status:** 🔄 In Progress
