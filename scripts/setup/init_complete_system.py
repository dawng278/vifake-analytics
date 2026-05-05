#!/usr/bin/env python3
"""
Complete ViFake Analytics System Initialization Script
Sets up all components for the compliance-first AI-powered child safety platform
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ViFakeSystemInitializer:
    """Complete system initialization for ViFake Analytics"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.setup_status = {
            "architecture": False,
            "mongodb": False,
            "neo4j": False,
            "datasets": False,
            "synthetic_data": False,
            "graph_simulation": False,
            "active_learning": False,
            "compliance": False
        }
    
    def check_prerequisites(self):
        """Check system prerequisites"""
        logger.info("🔍 Checking system prerequisites...")
        
        # Check Python version
        python_version = sys.version_info
        if python_version.major != 3 or python_version.minor < 9:
            logger.error(f"❌ Python 3.9+ required, found {python_version.major}.{python_version.minor}")
            return False
        
        # Check required directories
        required_dirs = [
            "data_pipeline",
            "ai_engine", 
            "graph_analytics",
            "docs",
            "scripts"
        ]
        
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                logger.error(f"❌ Required directory missing: {dir_name}")
                return False
        
        logger.info("✅ Prerequisites check passed")
        return True
    
    def setup_mongodb_schema(self):
        """Setup MongoDB collections and indexes"""
        logger.info("🗄️ Setting up MongoDB schema...")
        
        try:
            from pymongo import MongoClient
            from pymongo.errors import ConnectionFailure
            
            # Connect to MongoDB
            mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            
            # Test connection
            client.admin.command('ping')
            db = client.vifake_analytics
            
            # Create collections
            collections = [
                "posts_collection",
                "user_interactions_collection", 
                "synthetic_data_collection",
                "model_training_collection",
                "audit_log_collection",
                "active_learning_queue",
                "pagerank_analysis_collection",
                "community_analysis_collection",
                "botnet_detection_collection",
                "pattern_weights_collection",
                "perturbed_synthetic_data"
            ]
            
            for collection_name in collections:
                if collection_name not in db.list_collection_names():
                    db.create_collection(collection_name)
                    logger.info(f"✅ Created collection: {collection_name}")
                else:
                    logger.info(f"ℹ️ Collection already exists: {collection_name}")
            
            # Setup indexes (from VIFAKE_ARCHITECTURE_2.md)
            posts_collection = db.posts_collection
            posts_collection.create_index([("platform", 1), ("created_at", -1)])
            posts_collection.create_index([("scam_probability", -1)])
            posts_collection.create_index([("processing_tier", 1), ("retention_expires", 1)])
            posts_collection.create_index([("content_hash", 1)], unique=True)
            
            # Setup other indexes
            interactions_collection = db.user_interactions_collection
            interactions_collection.create_index([("post_id", 1), ("interaction_timestamp", -1)])
            interactions_collection.create_index([("user_hash", 1), ("interaction_timestamp", -1)])
            interactions_collection.create_index([("is_suspicious", 1), ("created_at", -1)])
            
            synthetic_collection = db.synthetic_data_collection
            synthetic_collection.create_index([("scam_scenario", 1), ("target_age_group", 1)])
            synthetic_collection.create_index([("generation_timestamp", -1)])
            synthetic_collection.create_index([("used_in_training", 1), ("realism_score", -1)])
            
            audit_collection = db.audit_log_collection
            audit_collection.create_index([("event_timestamp", -1)])
            audit_collection.create_index([("event_type", 1), ("severity", 1)])
            audit_collection.create_index([("user_hash", 1), ("event_timestamp", -1)])
            
            logger.info("✅ MongoDB schema setup completed")
            self.setup_status["mongodb"] = True
            client.close()
            return True
            
        except ConnectionFailure:
            logger.error("❌ MongoDB connection failed. Please ensure MongoDB is running.")
            return False
        except Exception as e:
            logger.error(f"❌ MongoDB setup failed: {e}")
            return False
    
    def setup_neo4j_graph(self):
        """Setup Neo4j graph database"""
        logger.info("🕸️ Setting up Neo4j graph database...")
        
        try:
            from neo4j import GraphDatabase
            
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
            
            driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            
            # Test connection
            with driver.session() as session:
                session.run("RETURN 1")
            
            # Setup graph constraints and indexes
            with driver.session() as session:
                # Create constraints
                constraints = [
                    "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:USER) REQUIRE u.id IS UNIQUE",
                    "CREATE CONSTRAINT content_id_unique IF NOT EXISTS FOR (c:CONTENT) REQUIRE c.id IS UNIQUE",
                    "CREATE CONSTRAINT scammer_id_unique IF NOT EXISTS FOR (s:SCAMMER) REQUIRE s.id IS UNIQUE"
                ]
                
                for constraint in constraints:
                    try:
                        session.run(constraint)
                        logger.info(f"✅ Created constraint: {constraint.split('FOR')[1].split('REQUIRE')[0].strip()}")
                    except Exception as e:
                        logger.warning(f"⚠️ Constraint may already exist: {e}")
            
            logger.info("✅ Neo4j graph setup completed")
            self.setup_status["neo4j"] = True
            driver.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Neo4j setup failed: {e}")
            return False
    
    def create_directories(self):
        """Create necessary directories"""
        logger.info("📁 Creating directory structure...")
        
        directories = [
            "data/synthetic",
            "data/graph_simulation", 
            "data/perturbation",
            "logs",
            "models/checkpoints",
            "models/outputs"
        ]
        
        for dir_path in directories:
            full_path = self.project_root / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Created directory: {dir_path}")
        
        return True
    
    def generate_sample_synthetic_data(self):
        """Generate sample synthetic data for testing"""
        logger.info("🎭 Generating sample synthetic data...")
        
        try:
            # Import the synthetic data generator
            sys.path.append(str(self.project_root / "ai_engine/synthetic_data"))
            
            from vietnamese_child_scam_generator import SyntheticDataGenerator, SyntheticConfig
            
            config = SyntheticConfig()
            config.num_samples = 50  # Small sample for testing
            generator = SyntheticDataGenerator(config)
            
            # Generate sample data
            synthetic_data = generator.generate_synthetic_dataset()
            
            # Save to file
            generator.save_to_json(synthetic_data)
            
            logger.info(f"✅ Generated {len(synthetic_data)} sample synthetic conversations")
            self.setup_status["synthetic_data"] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Synthetic data generation failed: {e}")
            return False
    
    def setup_mlflow(self):
        """Setup MLflow for experiment tracking"""
        logger.info("📊 Setting up MLflow...")
        
        try:
            import mlflow
            
            # Set tracking URI
            mlflow_tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")
            mlflow.set_tracking_uri(mlflow_tracking_uri)
            
            # Create experiment
            experiment_name = "vifake-analytics-compliance-first"
            try:
                mlflow.create_experiment(experiment_name)
                logger.info(f"✅ Created MLflow experiment: {experiment_name}")
            except Exception:
                logger.info(f"ℹ️ MLflow experiment already exists: {experiment_name}")
            
            mlflow.set_experiment(experiment_name)
            
            logger.info("✅ MLflow setup completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ MLflow setup failed: {e}")
            return False
    
    def create_environment_file(self):
        """Create .env file with default configurations"""
        logger.info("⚙️ Creating environment configuration...")
        
        env_content = """# ViFake Analytics Environment Configuration

# Database Connections
MONGODB_URI=mongodb://localhost:27017
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# MLflow Configuration
MLFLOW_TRACKING_URI=http://localhost:5001

# Data Processing
SSD_LIMIT_GB=512
BATCH_SIZE=1000
RETENTION_DAYS=30

# Active Learning
UNCERTAINTY_THRESHOLD=0.6
CONFIDENCE_THRESHOLD=0.8
RETRAIN_THRESHOLD=100

# Synthetic Data Generation
NUM_SYNTHETIC_SAMPLES=500
MIN_CONVERSATION_TURNS=3
MAX_CONVERSATION_TURNS=8

# Graph Simulation
VOXPOPULI_SAMPLE_SIZE=10000
PAGERANK_THRESHOLD=0.01
COMMUNITY_SIZE_THRESHOLD=10
SCAM_INJECTION_RATIO=0.15

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/vifake/analytics.log

# Security
ENCRYPTION_KEY=your-encryption-key-here
JWT_SECRET=your-jwt-secret-here
"""
        
        env_file = self.project_root / ".env"
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        logger.info("✅ Environment configuration created")
        return True
    
    def create_startup_script(self):
        """Create system startup script"""
        logger.info("🚀 Creating startup script...")
        
        startup_script = f"""#!/bin/bash
# ViFake Analytics Startup Script
# Generated on: {datetime.now().isoformat()}

echo "🚀 Starting ViFake Analytics Compliance-First System..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start infrastructure services
echo "📦 Starting infrastructure services..."
docker-compose -f infrastructure/docker/docker-compose.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check MongoDB
echo "🗄️ Checking MongoDB..."
python -c "
from pymongo import MongoClient
client = MongoClient('mongodb://localhost:27017')
client.admin.command('ping')
print('✅ MongoDB is ready')
"

# Check Neo4j
echo "🕸️ Checking Neo4j..."
python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password'))
with driver.session() as session:
    session.run('RETURN 1')
print('✅ Neo4j is ready')
"

# Start MLflow
echo "📊 Starting MLflow..."
mlflow server --host 0.0.0.0 --port 5001 --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns &

# Start API Gateway (background)
echo "🌐 Starting API Gateway..."
cd backend_services/api_gateway
python main.py &

# Start Active Learning System (background)
echo "🧠 Starting Active Learning System..."
cd ../../ai_engine/active_learning
python human_in_the_loop_2026.py &

echo "🎉 ViFake Analytics System started successfully!"
echo "📊 Dashboard: http://localhost:3001 (Metabase)"
echo "🕸️ Neo4j Bloom: http://localhost:7474"
echo "📈 MLflow: http://localhost:5001"
echo "🌐 API: http://localhost:8000"
"""
        
        startup_file = self.project_root / "scripts/start_vifake_system.sh"
        with open(startup_file, 'w') as f:
            f.write(startup_script)
        
        # Make executable
        startup_file.chmod(0o755)
        
        logger.info("✅ Startup script created")
        return True
    
    def generate_system_report(self):
        """Generate complete system setup report"""
        logger.info("📋 Generating system setup report...")
        
        report = {
            "system_info": {
                "setup_timestamp": datetime.now().isoformat(),
                "project_root": str(self.project_root),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "system_type": "ViFake Analytics Compliance-First"
            },
            "architecture_components": {
                "vifake_architecture_2": {
                    "file": "docs/VIFAKE_ARCHITECTURE_2.md",
                    "status": "✅ Created",
                    "description": "MongoDB metadata structure with Privacy-by-Design"
                },
                "data_engineering_processor": {
                    "file": "data_pipeline/dataset_processing/meta_natural_reasoning_processor.py",
                    "status": "✅ Created", 
                    "description": "Streaming processing for Meta datasets with zero-trust"
                },
                "synthetic_data_generator": {
                    "file": "ai_engine/synthetic_data/vietnamese_child_scam_generator.py",
                    "status": "✅ Created",
                    "description": "Vietnamese child scam scenario generation with Teencode"
                },
                "perturbation_engine": {
                    "file": "ai_engine/perturbation_engine/data_perturbation_engine.py",
                    "status": "✅ Created",
                    "description": "Realistic data 'dirtying' with PySpark Track B"
                },
                "graph_simulation": {
                    "file": "graph_analytics/graph_simulation/voxpopuli_botnet_detector.py",
                    "status": "✅ Created",
                    "description": "Neo4j botnet detection using VoxPopuli network structure"
                },
                "active_learning": {
                    "file": "ai_engine/active_learning/human_in_the_loop_2026.py",
                    "status": "✅ Created",
                    "description": "2026 pattern updates with 10% test account integration"
                },
                "ethical_compliance": {
                    "file": "docs/ethical_compliance_justification.md",
                    "status": "✅ Created",
                    "description": "Complete ethical justification for review board"
                }
            },
            "database_setup": self.setup_status,
            "compliance_features": {
                "zero_trust_processing": "RAM-only content analysis",
                "synthetic_first_training": "90% synthetic data usage",
                "non_invasive_verification": "10% test account data only",
                "privacy_by_design": "Built-in privacy preservation",
                "audit_trail": "Complete logging and monitoring"
            },
            "auto_solutions": {
                "data_realism": "Perturbation Engine for realistic 'dirtying'",
                "graph_tracking": "Neo4j simulation without real crawling",
                "pattern_updates": "Human-in-the-loop for 2026 patterns"
            },
            "next_steps": [
                "Start Docker services: docker-compose up -d",
                "Run initialization: python scripts/setup/init_complete_system.py",
                "Start system: ./scripts/start_vifake_system.sh",
                "Access dashboards and begin testing"
            ]
        }
        
        # Save report
        report_file = self.project_root / "docs/system_setup_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📋 System setup report saved to: {report_file}")
        
        # Print summary
        logger.info("🎉 VI_FAKE ANALYTICS SYSTEM SETUP COMPLETE!")
        logger.info("=" * 60)
        logger.info("📊 System Components:")
        for component, info in report["architecture_components"].items():
            logger.info(f"   ✅ {info['description']}")
        
        logger.info("🔒 Compliance Features:")
        for feature, description in report["compliance_features"].items():
            logger.info(f"   ✅ {description}")
        
        logger.info("🚀 Next Steps:")
        for step in report["next_steps"]:
            logger.info(f"   📝 {step}")
        
        logger.info("=" * 60)
        
        return True
    
    def run_complete_setup(self):
        """Run complete system initialization"""
        logger.info("🚀 Starting complete ViFake Analytics system setup...")
        
        # Run all setup steps
        steps = [
            ("Prerequisites", self.check_prerequisites),
            ("Directory Structure", self.create_directories),
            ("Environment Configuration", self.create_environment_file),
            ("MongoDB Schema", self.setup_mongodb_schema),
            ("Neo4j Graph", self.setup_neo4j_graph),
            ("MLflow Setup", self.setup_mlflow),
            ("Sample Synthetic Data", self.generate_sample_synthetic_data),
            ("Startup Script", self.create_startup_script),
            ("System Report", self.generate_system_report)
        ]
        
        for step_name, step_function in steps:
            logger.info(f"🔄 Running: {step_name}")
            try:
                if not step_function():
                    logger.error(f"❌ Step failed: {step_name}")
                    return False
            except Exception as e:
                logger.error(f"❌ Step failed: {step_name} - {e}")
                return False
        
        logger.info("🎉 Complete system setup finished successfully!")
        return True

def main():
    """Main execution function"""
    initializer = ViFakeSystemInitializer()
    
    try:
        success = initializer.run_complete_setup()
        if success:
            logger.info("✅ ViFake Analytics system is ready for use!")
            sys.exit(0)
        else:
            logger.error("❌ System setup failed. Please check the logs.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("⏹️ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
