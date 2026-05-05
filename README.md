# 🛡️ ViFake Analytics — AI-Powered Child Safety Platform

> **Mission:** Phát hiện, phân tích và truy vết nội dung AI-generated độc hại nhắm vào trẻ em trên mạng xã hội — chạy **hoàn toàn local**, xuất API cho B2B2C.

## 📋 Tổng Quan

ViFake Analytics là hệ thống multi-tier architecture với 6 tầng chính:
1. **Data Ingestion & Quarantine** - Honeypot stealth crawling
2. **Local Big Data Stack** - MinIO + MongoDB + PySpark
3. **Multi-modal AI Engine** - CLIP + PhoBERT + XGBoost
4. **Graph Analytics & Visualization** - Neo4j + Metabase
5. **Active Learning & MLOps** - Human review + MLflow
6. **Backend API & Human Review UI** - FastAPI + React

## 🏗️ Cấu Trúc Thư Mục

```
vifake-analytics/
├── 📁 data_pipeline/
│   ├── honeypot_stealth/          # Tầng 1: Stealth crawling
│   └── spark_etl/                 # Tầng 2: Big Data processing
├── 📁 ai_engine/
│   ├── vision_worker/             # Tầng 3: CLIP FP16
│   ├── nlp_worker/                # Tầng 3: PhoBERT ONNX
│   ├── fusion_model/              # Tầng 3: XGBoost meta-learner
│   └── mlops/                     # Tầng 5: Active learning
├── 📁 graph_analytics/
│   ├── cypher_scripts/            # Tầng 4: Neo4j queries
│   └── metabase_dash/             # Tầng 4: Dashboard SQL
├── 📁 backend_services/
│   ├── api_gateway/               # Tầng 6: FastAPI
│   └── human_review_ui/           # Tầng 6: React UI
├── 📁 infrastructure/
│   ├── docker/                    # Docker Compose
│   ├── monitoring/                # Prometheus + Grafana
│   └── security/                  # Security configs
├── 📁 docs/
│   ├── tasks/                     # Team member tasks
│   ├── api/                       # API documentation
│   └── deployment/                # Deployment guides
└── 📁 scripts/
    ├── setup/                     # Environment setup
    ├── data/                      # Data utilities
    └── demo/                      # Demo automation
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.9+
- Node.js 18+
- CUDA 11.8 (for GPU inference)

### Installation
```bash
# Clone repository
git clone <repository-url>
cd vifake-analytics

# Setup environment
cp .env.example .env
# Edit .env with your configurations

# Start infrastructure
docker-compose up -d

# Install Python dependencies
pip install -r requirements.txt

# Initialize databases
python scripts/setup/init_databases.py

# Start services
python scripts/start_services.py
```

### Demo
```bash
# Run demo stream
python scripts/demo/run_demo.py

# Access UI
- API Gateway: http://localhost:8000
- Human Review UI: http://localhost:3000
- Metabase Dashboard: http://localhost:3001
- Neo4j Bloom: http://localhost:7474
```

## 🎯 Tính Năng Chính

### 🔍 Multi-Modal Detection
- **Vision:** CLIP FP16 trên RTX 2050 (4GB VRAM)
- **Text:** PhoBERT ONNX + RAG vector search
- **Fusion:** XGBoost meta-learner với active learning

### 🛡️ Zero-Trust Quarantine
- Real-time NSFW detection trên RAM
- Không ghi nội dung độc hại vào disk
- Automatic violation logging

### 🕸️ Graph Analytics
- Neo4j propagation network analysis
- Botnet detection với PageRank + Louvain
- Real-time visualization với Neo4j Bloom

### 📊 Dashboard & Analytics
- Metabase real-time dashboard
- Custom metrics và alerts
- Export reports cho B2B clients

### 🔄 MLOps Pipeline
- Active learning với human review
- MLflow tracking và model versioning
- Automatic retrain triggers

## 🏆 Team Structure

| Member | Role | Responsibilities |
|---|---|---|
| **Member 1** | Data Engineer | Tầng 1-2: Honeypot crawling, PySpark ETL |
| **Member 2** | AI/ML Engineer | Tầng 3-5: AI models, MLOps, active learning |
| **Member 3** | Graph Analyst | Tầng 4: Neo4j, Metabase, botnet detection |
| **Member 4** | Full-stack Dev | Tầng 6: FastAPI, React UI, deployment |

## 📚 Documentation

- [Architecture Overview](docs/architecture.md)
- [API Reference](docs/api/)
- [Deployment Guide](docs/deployment/)
- [Team Tasks](docs/tasks/)
- [Security Guidelines](docs/security.md)

## 🔒 Security & Compliance

- **Zero-Trust Architecture:** Không lưu nội dung độc hại
- **Local Processing:** Mọi data xử lý offline
- **Encryption:** End-to-end encryption cho data in transit
- **Audit Trail:** Full logging cho compliance

## 📞 Support

- Technical issues: Create GitHub issue
- Security concerns: security@vifake-analytics.com
- Business inquiries: contact@vifake-analytics.com

---

**License:** MIT License  
**Version:** 1.0.0  
**Last Updated:** 2024
