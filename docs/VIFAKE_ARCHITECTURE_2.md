# 🏗️ VIFAKE ARCHITECTURE 2.0 - MongoDB Metadata Structure

## 📋 Overview

Định nghĩa cấu trúc metadata tuân thủ Privacy-by-Design cho hệ thống ViFake Analytics, tập trung vào xử lý dữ liệu tổng hợp và tracking quyền riêng tư.

---

## 🗄️ MongoDB Collections Schema

### 1. posts_collection
```javascript
{
  _id: ObjectId,
  post_id: String,           // Unique identifier from platform
  platform: String,          // "youtube", "facebook", "tiktok"
  content_type: String,      // "video", "image", "text", "comment"
  
  // Zero-Trust Content Storage
  content_hash: String,      // SHA-256 hash (không lưu content)
  content_url: String,       // MinIO path (nếu an toàn)
  is_quarantined: Boolean,   // True nếu bị filter
  
  // Metadata Analysis
  analysis_timestamp: Date,
  scam_probability: Number,   // 0.0 - 1.0
  scam_type: String,         // "phishing", "gift_card", "account_theft"
  confidence_score: Number,  // AI model confidence
  
  // Vietnamese Language Features
  contains_teencode: Boolean,
  leetspeak_score: Number,
  detected_keywords: [String], // ["robux", "skibidi", "free"]
  
  // Graph Analytics
  interaction_count: Number,
  propagation_depth: Number,
  network_cluster: String,
  
  // Compliance Tracking
  processing_tier: String,   // "synthetic", "research", "test"
  data_source: String,       // "facebook/natural_reasoning", "synthetic"
  retention_expires: Date,    // Tự động xóa sau 30 ngày
  
  created_at: Date,
  updated_at: Date
}
```

### 2. user_interactions_collection
```javascript
{
  _id: ObjectId,
  interaction_id: String,
  post_id: String,           // Reference to posts_collection
  
  // User Privacy (Zero-Trust)
  user_hash: String,         // SHA-256 của user ID (không lưu ID gốc)
  user_age_group: String,    // "child_8-12", "teen_13-17", "adult_18+"
  user_platform: String,    // Platform detected from user agent
  
  // Interaction Metadata
  interaction_type: String,  // "like", "share", "comment", "click"
  interaction_timestamp: Date,
  sentiment_score: Number,   // -1.0 to 1.0
  
  // Scam Detection Features
  is_suspicious: Boolean,
  risk_factors: [String],   // ["new_account", "high_activity", "unusual_timing"]
  
  // Graph Properties
  source_user_hash: String, // Who shared this
  target_user_hash: String, // Who received this
  relationship_type: String, // "friend", "follower", "stranger"
  
  // Compliance
  consent_level: String,     // "implicit", "explicit", "synthetic"
  data_classification: String, // "public", "semi_private", "private"
  
  created_at: Date
}
```

### 3. synthetic_data_collection
```javascript
{
  _id: ObjectId,
  synthetic_id: String,
  
  // Generation Metadata
  generation_prompt: String,  // Prompt used to generate
  generation_model: String,   // "gpt-4", "local_llm", "template"
  generation_timestamp: Date,
  
  // Scenario Classification
  scam_scenario: String,      // "robux_phishing", "gift_card_scam", "account_theft"
  target_age_group: String,   // "8-10", "11-13", "14-17"
  language_variant: String,   // "teencode_heavy", "mixed", "formal"
  
  // Content Structure
  conversation_turns: Number,
  participant_roles: [String], // ["scammer", "victim_child"]
  
  // Quality Metrics
  realism_score: Number,      // 0.0 - 1.0
  diversity_score: Number,   // So với các mẫu khác
  safety_score: Number,      // Không chứa nội dung độc hại thực
  
  // Usage Tracking
  used_in_training: Boolean,
  training_performance: Number, // Model accuracy với mẫu này
  human_reviewed: Boolean,
  reviewer_notes: String,
  
  // Version Control
  version: String,           // "v1.0", "v1.1", ...
  parent_synthetic_id: String, // Nếu được augment từ mẫu khác
  
  created_at: Date,
  updated_at: Date
}
```

### 4. model_training_collection
```javascript
{
  _id: ObjectId,
  training_run_id: String,
  
  // Training Configuration
  model_name: String,        // "phobert_scam_detector", "clip_vision"
  model_version: String,     // "v2.1.0"
  training_timestamp: Date,
  
  // Dataset Composition
  synthetic_data_ratio: Number, // % dữ liệu tổng hợp (target: 90%)
  research_data_ratio: Number,  // % dữ liệu nghiên cứu (Meta datasets)
  test_data_ratio: Number,      // % dữ liệu test
  
  // Training Metrics
  accuracy: Number,
  precision: Number,
  recall: Number,
  f1_score: Number,
  auc_roc: Number,
  
  // Vietnamese Language Performance
  teencode_accuracy: Number,
  leetspeak_detection_rate: Number,
  dialect_coverage: [String], // ["north", "central", "south"]
  
  // Compliance Metrics
  privacy_preservation_score: Number, // 0.0 - 1.0
  data_minimization_score: Number,    // 0.0 - 1.0
  ethical_compliance_score: Number,   // 0.0 - 1.0
  
  // Model Registry
  model_path: String,         // MinIO path to model artifacts
  is_deployed: Boolean,
  deployment_timestamp: Date,
  
  created_at: Date
}
```

### 5. audit_log_collection
```javascript
{
  _id: ObjectId,
  log_id: String,
  
  // Event Metadata
  event_type: String,        // "data_access", "model_training", "violation_detected"
  event_timestamp: Date,
  severity: String,          // "low", "medium", "high", "critical"
  
  // User/Session Context
  session_id: String,
  user_role: String,         // "data_engineer", "ml_engineer", "reviewer"
  user_hash: String,         // Privacy-preserving identifier
  
  // Data Access Tracking
  data_accessed: [String],   // Collections accessed
  records_count: Number,     // Số records được truy cập
  access_purpose: String,    // "training", "analysis", "debugging"
  
  // Privacy Compliance
  consent_verified: Boolean,
  data_minimization_applied: Boolean,
  anonymization_method: String, // "hashing", "aggregation", "synthetic"
  
  // Security Events
  ip_address: String,
  user_agent: String,
  authentication_method: String,
  
  // Event Details
  event_details: {
    description: String,
    affected_records: Number,
    action_taken: String,
    resolution_status: String
  },
  
  created_at: Date
}
```

### 6. active_learning_queue
```javascript
{
  _id: ObjectId,
  queue_item_id: String,
  
  // Item Identification
  item_type: String,         // "post", "conversation", "user_interaction"
  item_id: String,           // Reference to source collection
  item_hash: String,         // For deduplication
  
  // ML Model Uncertainty
  model_confidence: Number,  // 0.0 - 1.0
  uncertainty_type: String,  // "low_confidence", "high_entropy", "disagreement"
  
  // Human Review Priority
  priority_score: Number,    // 0.0 - 1.0
  review_reason: String,     // "new_pattern", "edge_case", "model_drift"
  
  // Review Assignment
  assigned_reviewer: String,
  review_deadline: Date,
  review_status: String,      // "pending", "in_review", "completed", "skipped"
  
  // Review Outcome
  human_label: String,       // "scam", "legitimate", "uncertain"
  human_confidence: Number,  // 0.0 - 1.0
  reviewer_notes: String,
  
  // Model Update Impact
  used_in_retraining: Boolean,
  performance_impact: Number, // Độ cải thiện sau khi thêm label
  
  // 2026 Pattern Detection
  is_2026_pattern: Boolean,
  new_keywords_detected: [String],
  new_scam_variant: String,
  
  created_at: Date,
  reviewed_at: Date
}
```

---

## 🔄 Index Strategy

### Performance Indexes
```javascript
// posts_collection
db.posts.createIndex({"platform": 1, "created_at": -1})
db.posts.createIndex({"scam_probability": -1})
db.posts.createIndex({"processing_tier": 1, "retention_expires": 1})
db.posts.createIndex({"content_hash": 1}, {unique: true})

// user_interactions_collection  
db.interactions.createIndex({"post_id": 1, "interaction_timestamp": -1})
db.interactions.createIndex({"user_hash": 1, "interaction_timestamp": -1})
db.interactions.createIndex({"is_suspicious": 1, "created_at": -1})

// synthetic_data_collection
db.synthetic.createIndex({"scam_scenario": 1, "target_age_group": 1})
db.synthetic.createIndex({"generation_timestamp": -1})
db.synthetic.createIndex({"used_in_training": 1, "realism_score": -1})

// audit_log_collection
db.audit.createIndex({"event_timestamp": -1})
db.audit.createIndex({"event_type": 1, "severity": 1})
db.audit.createIndex({"user_hash": 1, "event_timestamp": -1})
```

---

## 🔒 Privacy by Design Rules

### Data Minimization
1. **Zero Content Storage**: Không lưu nội dung gốc, chỉ hash
2. **User Anonymization**: User ID luôn được hash với salt
3. **Temporal Limits**: Data tự động xóa sau 30 ngày
4. **Synthetic First**: 90% data từ nguồn tổng hợp

### Access Control
1. **Role-Based Access**: Engineer, ML, Reviewer roles
2. **Need-to-Know**: Chỉ truy cập data cần thiết cho task
3. **Audit Trail**: Mọi action được logged
4. **Consent Tracking**: Level consent cho mỗi data source

### Compliance Monitoring
1. **Real-time Alerts**: Vi phạm privacy rules
2. **Periodic Audits**: Monthly compliance reports  
3. **Data Classification**: Public, semi-private, private
4. **Retention Policies**: Automatic cleanup schedules

---

## 📊 Usage Examples

### Streaming Data Processing
```python
# Insert new post with zero-trust processing
post_metadata = {
    "post_id": "yt_123456789",
    "platform": "youtube",
    "content_hash": hashlib.sha256(content_bytes).hexdigest(),
    "is_quarantined": False,
    "scam_probability": 0.85,
    "processing_tier": "research",
    "data_source": "facebook/natural_reasoning",
    "retention_expires": datetime.now() + timedelta(days=30)
}
```

### Synthetic Data Tracking
```python
# Track generated synthetic conversation
synthetic_metadata = {
    "synthetic_id": f"synth_{uuid4().hex[:8]}",
    "generation_prompt": "Vietnamese child scam scenario",
    "scam_scenario": "robux_phishing",
    "target_age_group": "8-10",
    "realism_score": 0.92,
    "safety_score": 1.0
}
```

---

## 🚀 Next Steps

1. **Initialize Collections**: Run setup script to create collections & indexes
2. **Configure TTL**: Setup automatic expiration for retention policies  
3. **Test Privacy**: Validate zero-trust processing pipeline
4. **Monitor Performance**: Benchmark query performance with indexes
5. **Audit Setup**: Configure logging and compliance monitoring

---

**Version:** 2.0  
**Last Updated:** 2026-05-04  
**Compliance:** GDPR + Vietnamese Child Protection Law  
**Architecture:** Privacy-by-Design + Zero-Trust
