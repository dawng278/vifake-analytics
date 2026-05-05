# ViFake Analytics - Vietnamese Child Scam Detection System

![ViFake Analytics](https://img.shields.io/badge/ViFake-Analytics-blue)
![Python](https://img.shields.io/badge/Python-3.8+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Active-success)

## 🎯 Project Overview

**ViFake Analytics** is a comprehensive AI-powered system designed to detect and prevent child-targeted scams on Vietnamese social media platforms. The system uses multi-modal AI analysis (vision, NLP, graph analytics) to identify malicious content targeting children, with a Privacy-by-Design architecture ensuring complete ethical compliance.

### 🌟 Key Features

- **Multi-modal AI Analysis**: Combines vision (CLIP), NLP (PhoBERT), and fusion models (XGBoost)
- **Vietnamese Language Optimization**: PhoBERT fine-tuned on 750+ Vietnamese scam scenarios
- **Real-time Processing**: FastAPI-based B2B2C API with streaming support
- **Graph Analytics**: Neo4j-powered botnet detection and network analysis
- **Privacy-by-Design**: Zero-trust RAM processing, no persistent storage of harmful content
- **Ethical AI**: 100% synthetic data training, compliant with Nghị định 13/2023/NĐ-CP (Vietnam Personal Data Protection)
- **Web Interface**: Modern Vietnamese-language dashboard for local testing
- **Extension Ready**: Foundation for browser extension development

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     ViFake Analytics                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │   Client     │    │  Web UI      │    │  Extension   │   │
│  │  (B2B/B2C)   │    │  (Testing)   │    │  (Future)    │   │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘   │
│         │                    │                    │           │
│         └────────────────────┼────────────────────┘           │
│                              │                                 │
│                    ┌─────────▼──────────┐                    │
│                    │   API Gateway      │                    │
│                    │   (FastAPI)         │                    │
│                    └─────────┬──────────┘                    │
│                              │                                 │
│         ┌────────────────────┼────────────────────┐          │
│         │                    │                    │          │
│  ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐    │
│  │ AI Engine   │    │ Data Pipeline│    │ Graph       │    │
│  │             │    │             │    │ Analytics    │    │
│  │ • Vision    │    │ • Crawling  │    │ • Botnet     │    │
│  │ • NLP       │    │ • Processing│    │ • Community  │    │
│  │ • Fusion    │    │ • Storage   │    │ • Pattern    │    │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    │
│         │                    │                    │          │
│  ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐    │
│  │  PhoBERT    │    │  MongoDB    │    │  Neo4j      │    │
│  │  + CLIP     │    │  + MLflow   │    │  + Chroma   │    │
│  │  + XGBoost  │    │             │    │             │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Component Architecture

#### 1. **AI Engine** (`ai_engine/`)
- **Vision Worker**: CLIP FP16 model for image risk scoring
- **NLP Worker**: PhoBERT inference with ONNX optimization
- **RAG Setup**: ChromaDB vector database for scam pattern indexing
- **Fusion Model**: XGBoost meta-learner for multi-modal decision fusion
- **Synthetic Data Generator**: Vietnamese child scam scenario generation
- **Perturbation Engine**: Realistic data augmentation
- **Active Learning**: Human-in-the-loop system for 2026 pattern updates

#### 2. **Backend Services** (`backend_services/`)
- **API Gateway**: FastAPI B2B2C API with authentication and streaming
- **AI Service Integration**: Service layer for AI model communication
- **Data Service Integration**: MongoDB and data pipeline communication
- **Graph Service Integration**: Neo4j graph analytics communication

#### 3. **Data Pipeline** (`data_pipeline/`)
- **Dataset Processing**: Meta Natural Reasoning dataset processor
- **Data Storage**: Synthetic data management and organization

#### 4. **Graph Analytics** (`graph_analytics/`)
- **Graph Simulation**: Synthetic social graph generation for botnet detection
- **Network Analysis**: Community detection and pattern analysis

#### 5. **Web Interface** (`web_interface/`)
- **Testing Dashboard**: Vietnamese-language web interface
- **Real-time Monitoring**: Progress tracking and system status
- **Sample Testing**: Built-in test scenarios

## 📋 Model Card — PhoBERT Scam Detector

### Model Details
- **Base Model**: `vinai/phobert-base`
- **Task**: Vietnamese text classification (scam detection)
- **Architecture**: Transformer encoder (RoBERTa-based) with classification head
- **Input**: Vietnamese text, max 256 tokens
- **Output**: 4-class probability distribution

### Training Data
| Property | Value |
|----------|-------|
| Source | 100% synthetic (GPT-generated) |
| Total samples | ~750 |
| Train split | ~600 (80%) |
| Validation split | ~75 (10%) |
| Test split | ~75 (10%) |
| Scenarios | Robux phishing, gift card scams, malicious links, account theft |
| Age groups | 8-10, 11-13, 14-17 |
| Language | Vietnamese only |

### Evaluation Results (Synthetic Test Set)
| Metric | Score |
|--------|-------|
| Accuracy | 0.92 |
| Precision (macro) | 0.91 |
| Recall (macro) | 0.93 |
| F1 Score (macro) | 0.92 |

### Known Limitations & Failure Modes
- **Synthetic-to-Real Gap**: Model trained entirely on synthetic data; real-world performance unknown
- **Domain Shift**: Scam patterns evolve rapidly; model may miss novel scam types
- **Language Coverage**: Vietnamese only; code-switching (Vi-En) not well tested
- **Adversarial Robustness**: Not tested against intentionally obfuscated scam text
- **Bias Assessment**: Not yet evaluated for demographic or dialectal bias

### Intended Use
- **Primary**: Assist content moderators in flagging potential scam content targeting Vietnamese children
- **Out of Scope**: Not intended as sole decision-maker; human review required for high-stakes cases
- **Users**: Trained content moderators, child safety organizations

### Ethical Considerations
- Training data contains no real personal information
- Model should not be used for surveillance or profiling
- Decisions affecting children must involve human oversight

## 🤖 AI/ML Models

### Vision Model (CLIP)
- **Model**: OpenAI CLIP ViT-B/32 (FP16 optimized)
- **Purpose**: Multi-modal image-text analysis
- **Features**: Risk scoring, safety assessment, GPU memory management
- **Optimization**: FP16 for memory-constrained GPUs (RTX 2050 4GB)

### NLP Model (PhoBERT)
- **Model**: VinAI PhoBERT-base
- **Training**: Fine-tuned on ~600 synthetic Vietnamese child scam conversations
- **Performance**: 92% accuracy on ~150-sample synthetic test set
- **⚠️ Important Caveat**: This accuracy is measured on synthetic data only. Real-world validation is PENDING — synthetic-to-real domain gap has not been measured. Requires annotation of 200+ real posts for proper evaluation.
- **Features**: ONNX optimization, batch prediction, feature extraction
- **Labels**: SAFE, FAKE_TOXIC, FAKE_SCAM, FAKE_MISINFO

### Fusion Model (XGBoost)
- **Model**: XGBoost classifier
- **Purpose**: Multi-modal decision fusion
- **Features**: Cross-validation, SHAP explainability, feature engineering
- **Input**: Vision + NLP + metadata features

### RAG System (ChromaDB)
- **Purpose**: Vector database for scam pattern indexing
- **Embedding**: PhoBERT-based embeddings
- **Features**: Similarity search, pattern matching

## 📊 Data Pipeline

### Data Generation
1. **Synthetic Data**: 750+ Vietnamese child scam scenarios
2. **Age Groups**: 8-10, 11-13, 14-17 years
3. **Scam Types**: Robux phishing, gift card scams, malicious links, account theft
4. **Perturbation**: Realistic data augmentation
5. **Labels**: Multi-class classification with confidence scores

### Data Storage
- **MongoDB**: Metadata, posts, user interactions, audit logs
- **Neo4j**: Graph data for botnet detection
- **ChromaDB**: Vector embeddings for RAG
- **MLflow**: Model tracking and experiment management

## 🌐 API Gateway

### API Versioning Policy
- **Current Version**: `/api/v1/` (active development)
- **Deprecation Policy**: Minimum 6 months notice before deprecating any endpoint
- **Migration Path**: `/api/v2/` will run in parallel with `/api/v1/` for at least 3 months
- **Breaking Changes**: Will only occur on major version bumps
- **Sunset Header**: Deprecated endpoints will return `Sunset` HTTP header with deprecation date

### Endpoints

#### Authentication
- **Method**: Bearer token authentication
- **Setup**: Generate your token via environment variable `AUTH_TOKEN` in `.env` file
- **⚠️ Security**: Never commit real tokens to version control. Use `.env.example` as template.

#### Core Endpoints
- `POST /api/v1/analyze` - Submit content for analysis
- `GET /api/v1/stream/{job_id}` - Real-time progress streaming (SSE)
- `GET /api/v1/job/{job_id}` - Get job status
- `GET /api/v1/result/{job_id}` - Get final analysis result
- `GET /api/v1/health` - System health check
- `GET /api/v1/stats` - System statistics

### Features
- **Background Processing**: Async job management
- **Real-time Updates**: Server-sent events
- **Rate Limiting**: Prevent abuse
- **CORS Support**: Cross-origin requests
- **Error Handling**: Comprehensive error recovery
- **Service Integration**: AI, Data, Graph services

## 🎨 Web Interface

### Features
- **Vietnamese Language**: Full Vietnamese UI
- **Real-time Progress**: 6-stage analysis tracking
- **System Status**: Component health monitoring
- **Sample Testing**: Built-in test scenarios
- **Responsive Design**: Mobile and desktop compatible

### Access
- **Local Server**: `http://localhost:8080`
- **API Docs**: `http://localhost:8000/docs`

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- MongoDB (required for metadata storage; falls back to in-memory mock for dev testing)
- Neo4j (required for graph analytics; falls back to mock graph data for dev testing)
- GPU with 4GB+ VRAM (required for CLIP vision model; falls back to CPU inference with reduced performance)

### Installation

```bash
# Clone repository
git clone https://github.com/dawng278/vifake-analytics.git
cd vifake-analytics

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your configuration

# Initialize system
python scripts/setup/init_complete_system.py
```

### Running the System

#### Start API Gateway
```bash
cd backend_services/api_gateway
python3 main.py
```

#### Start Web Interface
```bash
cd web_interface
python3 start_server.py
```

#### Access
- **API Documentation**: http://localhost:8000/docs
- **Web Interface**: http://localhost:8080

## 🧪 Testing Strategy

### Current State
- **Manual Testing**: curl commands and web interface for endpoint verification
- **Limitation**: No automated test suite implemented yet

### Planned Testing Infrastructure
```bash
# Unit tests (target: 70% coverage on core modules)
pytest tests/ --cov=ai_engine --cov=backend_services --cov-report=html

# Integration tests (API endpoints with mock AI responses)
pytest tests/integration/ -v

# Model regression tests (F1 score must not drop >2% after retrain)
pytest tests/model/ --model-version latest
```

### Test Coverage Targets
| Component | Target | Status |
|-----------|--------|--------|
| API Gateway endpoints | 90% | PENDING |
| AI Engine core modules | 70% | PENDING |
| Data Pipeline processors | 70% | PENDING |
| Model inference | 85% | PENDING |

## 🧪 Manual Testing

### API Testing
```bash
# Health check
curl http://localhost:8000/api/v1/health

# Submit analysis (replace $TOKEN with your AUTH_TOKEN from .env)
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://youtube.com/watch?v=test123",
    "platform": "youtube",
    "priority": "normal"
  }'
```

### Web Interface Testing
1. Open http://localhost:8000/docs
2. Authenticate with your token from `.env`
3. Test with sample URLs
4. Monitor real-time progress

## 🔒 Security & Privacy

### Privacy-by-Design Principles
- **Zero-trust Processing**: RAM-only content analysis
- **No Persistent Storage**: No harmful content saved
- **Synthetic Training**: 100% synthetic data used
- **Data Minimization**: Only necessary data processed

### Legal Compliance (Vietnam)
- **Nghị định 13/2023/NĐ-CP**: Compliance with Vietnam Personal Data Protection Decree (effective July 2023)
- **Child Safety**: Specific focus on protecting children per Vietnamese child protection laws
- **Transparency**: SHAP explainability for all model decisions
- **Audit Logging**: Full traceability and monitoring
- **GDPR**: Architecture is also GDPR-compatible for potential EU expansion

### Security Features
- **Authentication**: Bearer token-based API access
- **Rate Limiting**: Prevent abuse and DoS attacks
- **Input Validation**: Pydantic model validation
- **Error Handling**: No sensitive data in errors

## 📁 Project Structure

```
vifake-analytics/
├── ai_engine/                 # AI/ML components
│   ├── vision_worker/        # CLIP vision analysis
│   ├── nlp_worker/           # PhoBERT NLP analysis
│   ├── fusion_model/         # XGBoost fusion model
│   ├── synthetic_data/       # Data generation
│   ├── perturbation_engine/  # Data augmentation
│   ├── active_learning/      # Human-in-the-loop
│   └── phobert_training/     # Model training
├── backend_services/         # Backend services
│   └── api_gateway/          # FastAPI API
│       ├── main.py           # Main API application
│       └── services/         # Service integrations
├── data_pipeline/            # Data processing
│   └── dataset_processing/   # Dataset processors
├── graph_analytics/          # Graph analytics
│   └── graph_simulation/     # Botnet detection
├── web_interface/            # Web testing interface
│   ├── index.html            # Main UI
│   ├── start_server.py       # Server script
│   └── test_interface.py     # Test script
├── data/                     # Data storage
│   └── synthetic/            # Synthetic data
├── models/                   # Model artifacts
│   └── phobert_scam_detector/ # Trained models
├── docs/                     # Documentation
│   ├── tasks/                # Task definitions
│   ├── VIFAKE_ARCHITECTURE_2.md
│   └── ethical_compliance_justification.md
├── scripts/                  # Utility scripts
│   └── setup/                # Setup scripts
├── deploy/                   # Deployment scripts
├── infrastructure/           # Infrastructure
│   └── docker/              # Docker configuration
├── requirements.txt          # Python dependencies
├── .env.example             # Environment template
├── .gitignore               # Git ignore rules
└── README.md               # Project README
```

## 🎯 Use Cases

### Target B2B Integration (Planned)
- **Target Platforms**: YouTube, Facebook, TikTok API integration
- **Target Customers**: Content moderation for enterprises operating in Vietnam
- **Educational Institutions**: School safety monitoring partnerships

### B2C Application
- **Browser Extension**: Real-time scam detection for parents
- **Mobile App**: On-the-go safety checking
- **Web Dashboard**: Parental control interface

### Research & Development
- **Academic Research**: Vietnamese NLP and scam pattern analysis
- **Model Improvement**: Continuous learning and pattern updates
- **Ethical AI**: Privacy-by-Design case study

## 📈 Performance Metrics

### Model Performance (Synthetic Evaluation Only)
- **PhoBERT Accuracy**: 92% on ~150-sample synthetic test set
- **⚠️ Real-world performance**: NOT YET MEASURED — requires annotated real data
- **Processing Speed**: <2 seconds per analysis (with GPU)
- **Memory Usage**: Optimized for 4GB GPU (FP16)

### System Metrics
- **API Response Time**: <500ms (health check)
- **Job Processing**: Real-time streaming via SSE
- **Data Coverage**: 750+ synthetic Vietnamese scam scenarios
- **Platform Support**: YouTube, Facebook, TikTok (URL-based analysis)

## 🗺️ Roadmap

### Phase 1: Foundation ✅ (Prototype Complete)
- [x] AI/ML model development (synthetic training only — real-world validation pending)
- [x] Data pipeline implementation (synthetic data generation pipeline)
- [x] API Gateway development (local dev environment)
- [x] Web interface creation (local testing dashboard)
- [x] Ethical compliance documentation (internal draft — pending independent review)

### Phase 2: Extension & Cloud Deployment (Next)
- [ ] Cloud API deployment (extensions cannot call localhost — requires hosted API)
- [ ] Chrome Extension (calls cloud API, not localhost)
- [ ] Firefox Extension
- [ ] Mobile App (React Native)
- [ ] Desktop App (Electron)

### Phase 3: Production Deployment
- [ ] Cloud infrastructure setup
- [ ] CI/CD pipeline
- [ ] Monitoring and alerting
- [ ] Load testing and optimization

### Phase 4: Advanced Features
- [ ] Real-time social media monitoring
- [ ] Advanced graph analytics
- [ ] Multi-language support
- [ ] Community reporting system

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 📞 Contact

- **Repository**: https://github.com/dawng278/vifake-analytics
- **Issues**: https://github.com/dawng278/vifake-analytics/issues

## 🙏 Acknowledgments

- **VinAI**: PhoBERT model
- **OpenAI**: CLIP model
- **Vietnamese AI Community**: Support and guidance
- **Child Safety Organizations**: Ethical guidance

---

**ViFake Analytics - Bảo vệ trẻ em Việt Nam trực tuyến** 🛡️

*Privacy-by-Design • Ethical AI • 100% Synthetic Data Training*
