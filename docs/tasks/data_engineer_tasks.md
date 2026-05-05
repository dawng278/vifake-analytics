# 🔧 Data Engineer Tasks - Member 1

> **Timeline:** 4 weeks | **Priority:** 🔴 High | **Tầng:** 1-2

## 📋 Week 1: Foundation Setup

### Day 1-2: Environment & Infrastructure
- [ ] **Setup Docker Compose**
  ```bash
  # File: infrastructure/docker/docker-compose.yml
  - MinIO (S3-compatible storage)
  - MongoDB (metadata store)
  - PostgreSQL (data mart for Metabase)
  - Redis (cache & queue)
  - Neo4j (graph database)
  ```

- [ ] **Configure MinIO buckets**
  ```python
  # File: data_pipeline/spark_etl/minio_setup.py
  - raw-media/ (youtube, facebook, tiktok)
  - processed/ (frames, audio_text, features)
  - models/ (AI model checkpoints)
  ```

- [ ] **Setup MongoDB schema**
  ```python
  # File: data_pipeline/spark_etl/mongo_schema.py
  - Posts collection with indexes
  - Review queue collection
  - MLflow tracking collection
  ```

### Day 3-4: Honeypot Account Setup
- [ ] **Create honeypot profiles**
  ```python
  # File: data_pipeline/honeypot_stealth/account_profile.py
  HONEYPOT_PROFILES = [
      {
          "username": "kiduser_vn_01",
          "age_signal": 10,
          "interests": ["minecraft", "roblox", "cartoon"],
          "platform": "youtube",
      },
      # Add 2 more profiles for rotation
  ]
  ```

- [ ] **Implement stealth crawler**
  ```python
  # File: data_pipeline/honeypot_stealth/crawler.py
  - Playwright stealth integration
  - Gaussian delay (μ=2s, σ=0.8s)
  - Mobile user agent rotation
  - Session persistence
  ```

- [ ] **Anti-ban strategy**
  ```python
  # File: data_pipeline/honeypot_stealth/anti_ban.py
  - Request cap: 50 items/hour/profile
  - Profile rotation logic
  - Error handling & retry
  ```

### Day 5-7: Zero-Trust Quarantine
- [ ] **Implement RAM quarantine filter**
  ```python
  # File: data_pipeline/honeypot_stealth/quarantine_filter.py
  - NSFW detection with MobileNet
  - In-memory processing only
  - Violation logging (no content storage)
  ```

- [ ] **Test quarantine pipeline**
  ```bash
  # Run end-to-end test
  python data_pipeline/honeypot_stealth/test_quarantine.py
  ```

## 📋 Week 2: PySpark ETL Implementation

### Day 8-10: Dual-Track Processing
- [ ] **Setup PySpark environment**
  ```python
  # File: data_pipeline/spark_etl/spark_session.py
  - Memory allocation (8GB driver, 10GB executor)
  - MinIO connector setup
  - MongoDB connector setup
  ```

- [ ] **Implement Track A (NLP)**
  ```python
  # File: data_pipeline/spark_etl/dual_track_pipeline.py
  def clean_for_nlp(text: str) -> str:
      # Remove HTML tags, normalize whitespace
      # KEEP ORIGINAL TEXT for PhoBERT
  ```

- [ ] **Implement Track B (Leetspeak)**
  ```python
  # File: data_pipeline/spark_etl/dual_track_pipeline.py
  LEETSPEAK_MAP = {
      '0': 'o', '1': 'i', '3': 'e', '4': 'a',
      '5': 's', '7': 't', '@': 'a', '$': 's',
  }
  
  def leetspeak_score(text: str) -> float:
      # Decode leetspeak for scam detection
      # DO NOT pass to NLP pipeline
  ```

### Day 11-14: Data Pipeline Integration
- [ ] **ETL pipeline orchestration**
  ```python
  # File: data_pipeline/spark_etl/run_etl.py
  - Extract from MongoDB
  - Transform with dual-track
  - Load to MinIO + PostgreSQL
  - Error handling & logging
  ```

- [ ] **Data quality checks**
  ```python
  # File: data_pipeline/spark_etl/data_quality.py
  - Schema validation
  - Duplicate detection
  - Missing value handling
  ```

- [ ] **Performance optimization**
  ```python
  # File: data_pipeline/spark_etl/optimization.py
  - Partitioning strategy
  - Caching frequent data
  - Parallel processing
  ```

## 📋 Week 3: Advanced Features

### Day 15-17: Real-time Processing
- [ ] **Streaming ETL**
  ```python
  # File: data_pipeline/spark_etl/streaming_etl.py
  - Kafka integration (optional)
  - Real-time feature extraction
  - Low-latency processing
  ```

- [ ] **Data versioning**
  ```python
  # File: data_pipeline/spark_etl/versioning.py
  - DVC integration
  - Dataset snapshots
  - Rollback capability
  ```

### Day 18-21: Monitoring & Maintenance
- [ ] **Pipeline monitoring**
  ```python
  # File: data_pipeline/spark_etl/monitoring.py
  - Health checks
  - Performance metrics
  - Alert integration
  ```

- [ ] **Data retention policies**
  ```python
  # File: data_pipeline/spark_etl/retention.py
  - Automated cleanup
  - Archive old data
  - Compliance logging
  ```

## 📋 Week 4: Integration & Demo

### Day 22-24: Integration Testing
- [ ] **End-to-end pipeline testing**
  ```bash
  # Test full pipeline
  python scripts/test/full_pipeline_test.py
  ```

- [ ] **Performance benchmarking**
  ```python
  # File: scripts/benchmark/data_pipeline_benchmark.py
  - Throughput measurement
  - Latency analysis
  - Resource utilization
  ```

### Day 25-28: Demo Preparation
- [ ] **Demo data generation**
  ```bash
  # Generate realistic demo dataset
  python scripts/demo/generate_demo_data.py
  ```

- [ ] **Pipeline documentation**
  ```markdown
  # File: docs/data_pipeline.md
  - Architecture overview
  - Configuration guide
  - Troubleshooting guide
  ```

## 🎯 Deliverables

### Code Repositories
- `data_pipeline/honeypot_stealth/` - Stealth crawling system
- `data_pipeline/spark_etl/` - Big data processing
- `infrastructure/docker/` - Docker configurations

### Documentation
- Data pipeline architecture
- Configuration guides
- Performance benchmarks
- Troubleshooting guides

### Test Coverage
- Unit tests (>80%)
- Integration tests
- Performance tests
- Demo data validation

## 🔧 Technical Requirements

### Dependencies
```python
# requirements.txt
playwright==1.40.0
playwright-stealth==1.0.6
pyspark==3.5.0
pymongo==4.6.0
boto3==1.34.0
redis==5.0.1
```

### Hardware Requirements
- CPU: Intel Core i5+
- RAM: 20GB+
- Storage: SSD 500GB+
- Network: Stable internet for crawling

## 🚨 Critical Path Items

1. **Docker Compose setup** - Day 2
2. **Honeypot crawler implementation** - Day 4
3. **Quarantine filter** - Day 7
4. **PySpark ETL pipeline** - Day 14
5. **Integration testing** - Day 24

## 📞 Support & Collaboration

- **Daily sync:** 9AM with team
- **Code review:** Before merging to main
- **Testing:** Coordinate with Member 2 (AI/ML)
- **Documentation:** Update team wiki

---

**Owner:** Member 1 (Data Engineer)  
**Timeline:** 4 weeks  
**Status:** 🔄 In Progress
