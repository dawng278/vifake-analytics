#!/usr/bin/env python3
"""
ViFake Analytics - Database Initialization Script
Initialize all databases with required schemas and indexes
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from pymongo import MongoClient
import asyncpg
import redis
from neo4j import GraphDatabase


async def init_mongodb():
    """Initialize MongoDB with collections and indexes"""
    print("🔧 Initializing MongoDB...")
    
    try:
        # Connect to MongoDB
        client = MongoClient("mongodb://admin:vifake_mongo_2024@localhost:27017/")
        db = client["vifake"]
        
        # Create collections
        collections = [
            "posts",
            "users", 
            "review_queue",
            "mlflow_tracking",
            "honeypot_profiles",
            "crawl_logs"
        ]
        
        for collection_name in collections:
            if collection_name not in db.list_collection_names():
                db.create_collection(collection_name)
                print(f"  ✓ Created collection: {collection_name}")
        
        # Create indexes
        posts_collection = db["posts"]
        posts_collection.create_index([("platform", 1), ("collected_at", -1)])
        posts_collection.create_index([("ai_result.label", 1)])
        posts_collection.create_index([("author_id", 1)])
        posts_collection.create_index([("post_id", 1)], unique=True)
        
        review_queue_collection = db["review_queue"]
        review_queue_collection.create_index([("status", 1)])
        review_queue_collection.create_index([("submitted_at", -1)])
        
        users_collection = db["users"]
        users_collection.create_index([("user_id", 1)], unique=True)
        users_collection.create_index([("platform", 1)])
        
        print("  ✓ MongoDB indexes created")
        client.close()
        
    except Exception as e:
        print(f"  ❌ MongoDB initialization failed: {e}")
        return False
    
    return True


async def init_postgres():
    """Initialize PostgreSQL with schemas and tables"""
    print("🔧 Initializing PostgreSQL...")
    
    try:
        # Connect to PostgreSQL
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="vifake_user",
            password="vifake_postgres_2024",
            database="vifake_mart"
        )
        
        # Create tables
        tables_sql = [
            # AI results mart
            """
            CREATE TABLE IF NOT EXISTS ai_results_mart (
                post_id VARCHAR PRIMARY KEY,
                platform VARCHAR,
                url TEXT,
                title TEXT,
                ai_label VARCHAR,
                confidence FLOAT,
                vision_score FLOAT,
                nlp_score FLOAT,
                leetspeak_score FLOAT,
                processed_at TIMESTAMP,
                author_id VARCHAR,
                needs_review BOOLEAN
            )
            """,
            
            # Dashboard summary view
            """
            CREATE OR REPLACE VIEW dashboard_summary AS
            SELECT
                DATE(processed_at) AS date,
                platform,
                ai_label,
                COUNT(*) AS count,
                AVG(confidence) AS avg_confidence
            FROM ai_results_mart
            GROUP BY 1, 2, 3
            ORDER BY 1 DESC, 4 DESC
            """,
            
            # Graph metrics table
            """
            CREATE TABLE IF NOT EXISTS graph_metrics (
                id SERIAL PRIMARY KEY,
                date DATE,
                platform VARCHAR,
                metric_name VARCHAR,
                metric_value FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # MLflow tables (if not exists)
            """
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id SERIAL PRIMARY KEY,
                name VARCHAR UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id SERIAL PRIMARY KEY,
                experiment_id INTEGER REFERENCES experiments(experiment_id),
                status VARCHAR,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                metrics JSONB,
                params JSONB
            )
            """
        ]
        
        for sql in tables_sql:
            await conn.execute(sql)
        
        # Create indexes
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_results_date ON ai_results_mart(processed_at)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_results_platform ON ai_results_mart(platform)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_results_label ON ai_results_mart(ai_label)")
        
        print("  ✓ PostgreSQL tables and indexes created")
        await conn.close()
        
    except Exception as e:
        print(f"  ❌ PostgreSQL initialization failed: {e}")
        return False
    
    return True


async def init_neo4j():
    """Initialize Neo4j with constraints and indexes"""
    print("🔧 Initializing Neo4j...")
    
    try:
        # Connect to Neo4j
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "vifake_neo4j_2024")
        )
        
        with driver.session() as session:
            # Create constraints
            constraints = [
                "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
                "CREATE CONSTRAINT post_id_unique IF NOT EXISTS FOR (p:Post) REQUIRE p.post_id IS UNIQUE",
                "CREATE CONSTRAINT honeypot_id_unique IF NOT EXISTS FOR (h:HoneypotProfile) REQUIRE h.profile_id IS UNIQUE"
            ]
            
            for constraint in constraints:
                session.run(constraint)
            
            # Create indexes
            indexes = [
                "CREATE INDEX post_label_idx IF NOT EXISTS FOR (p:Post) ON (p.ai_label)",
                "CREATE INDEX post_collected_idx IF NOT EXISTS FOR (p:Post) ON (p.collected_at)",
                "CREATE INDEX user_platform_idx IF NOT EXISTS FOR (u:User) ON (u.platform)",
                "CREATE INDEX post_confidence_idx IF NOT EXISTS FOR (p:Post) ON (p.confidence)"
            ]
            
            for index in indexes:
                session.run(index)
            
            print("  ✓ Neo4j constraints and indexes created")
        
        driver.close()
        
    except Exception as e:
        print(f"  ❌ Neo4j initialization failed: {e}")
        return False
    
    return True


async def init_redis():
    """Initialize Redis connection and test"""
    print("🔧 Initializing Redis...")
    
    try:
        # Connect to Redis
        r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        
        # Test connection
        r.ping()
        
        # Set some initial keys for testing
        r.set("vifake:status", "initialized")
        r.set("vifake:version", "1.0.0")
        
        print("  ✓ Redis connection established")
        return True
        
    except Exception as e:
        print(f"  ❌ Redis initialization failed: {e}")
        return False


async def init_minio():
    """Initialize MinIO with buckets"""
    print("🔧 Initializing MinIO...")
    
    try:
        import boto3
        from botocore.client import Config
        
        # Connect to MinIO
        minio = boto3.client(
            "s3",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="vifake_admin",
            aws_secret_access_key="vifake_secret_2024",
            config=Config(signature_version="s3v4"),
        )
        
        # Create buckets
        buckets = [
            "raw-media",
            "processed",
            "models",
            "exports",
            "backups"
        ]
        
        for bucket in buckets:
            try:
                minio.head_bucket(Bucket=bucket)
                print(f"  ✓ Bucket {bucket} already exists")
            except:
                minio.create_bucket(Bucket=bucket)
                print(f"  ✓ Created bucket: {bucket}")
        
        print("  ✓ MinIO buckets initialized")
        return True
        
    except Exception as e:
        print(f"  ❌ MinIO initialization failed: {e}")
        return False


async def main():
    """Main initialization function"""
    print("🚀 Initializing ViFake Analytics Databases")
    print("=" * 50)
    
    # Check if Docker services are running
    print("📋 Checking service availability...")
    
    services = {
        "MongoDB": 27017,
        "PostgreSQL": 5432,
        "Redis": 6379,
        "Neo4j": 7687,
        "MinIO": 9000
    }
    
    for service, port in services.items():
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            
            if result == 0:
                print(f"  ✓ {service} is running on port {port}")
            else:
                print(f"  ❌ {service} is not running on port {port}")
        except:
            print(f"  ❌ {service} connection failed")
    
    print()
    
    # Initialize databases
    results = []
    
    results.append(await init_mongodb())
    results.append(await init_postgres())
    results.append(await init_neo4j())
    results.append(await init_redis())
    results.append(await init_minio())
    
    print()
    print("=" * 50)
    
    # Summary
    success_count = sum(results)
    total_count = len(results)
    
    if success_count == total_count:
        print(f"🎉 All {total_count} databases initialized successfully!")
        print("✅ ViFake Analytics is ready to use!")
    else:
        print(f"⚠️  {success_count}/{total_count} databases initialized successfully")
        print("❌ Please check the failed services and try again")
    
    print()
    print("📋 Next steps:")
    print("1. Start the application services:")
    print("   docker-compose up -d api-gateway review-ui")
    print("2. Run the setup script:")
    print("   python scripts/setup/setup_services.py")
    print("3. Access the applications:")
    print("   - API Gateway: http://localhost:8000")
    print("   - Review UI: http://localhost:3000")
    print("   - Metabase: http://localhost:3001")
    print("   - Neo4j Bloom: http://localhost:7474")


if __name__ == "__main__":
    asyncio.run(main())
