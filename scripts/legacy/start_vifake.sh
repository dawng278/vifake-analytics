#!/bin/bash
# ViFake Analytics Startup Script
echo "🚀 Starting ViFake Analytics Compliance-First System..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start infrastructure services
echo "📦 Starting infrastructure services..."
if [ -f "infrastructure/docker/docker-compose.yml" ]; then
    docker-compose -f infrastructure/docker/docker-compose.yml up -d
else
    echo "⚠️ Docker compose file not found. Please create infrastructure setup."
fi

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if synthetic data exists
if [ -f "data/synthetic/sample_scams.json" ]; then
    echo "✅ Synthetic data ready"
else
    echo "❌ Synthetic data not found. Please run data initialization first."
fi

# Check environment configuration
if [ -f ".env" ]; then
    echo "✅ Environment configuration ready"
else
    echo "❌ Environment configuration not found."
fi

echo "🎉 ViFake Analytics System startup completed!"
echo "📊 Next steps:"
echo "   1. Ensure MongoDB and Neo4j are running"
echo "   2. Test data processing pipeline"
echo "   3. Start MLflow and API services"
