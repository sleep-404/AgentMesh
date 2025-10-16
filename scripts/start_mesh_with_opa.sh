#!/bin/bash

# Start AgentMesh with OPA governance layer

set -e

echo "================================================"
echo "Starting AgentMesh with OPA Governance"
echo "================================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo ""
echo "🚀 Starting infrastructure services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 5

# Check service health
echo ""
echo "🔍 Checking service health..."

check_service() {
    local name=$1
    local port=$2
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -f -s "http://localhost:$port/health" > /dev/null 2>&1 ||
           curl -f -s "http://localhost:$port/healthz" > /dev/null 2>&1 ||
           nc -z localhost $port > /dev/null 2>&1; then
            echo "  ✓ $name is ready"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done

    echo "  ⚠ $name may not be ready (timeout)"
    return 1
}

check_service "PostgreSQL" 5432
check_service "Neo4j" 7474
check_service "NATS" 4222
check_service "OPA" 8181

echo ""
echo "================================================"
echo "✅ Infrastructure Services Ready!"
echo "================================================"
echo ""
echo "Services:"
echo "  - PostgreSQL KB:  http://localhost:5432"
echo "  - Neo4j KB:       http://localhost:7474"
echo "  - NATS:           http://localhost:4222"
echo "  - NATS Monitor:   http://localhost:8222"
echo "  - OPA:            http://localhost:8181"
echo ""
echo "Next steps:"
echo "  1. Install dependencies: pip install -e ."
echo "  2. Setup demo data:     python examples/setup_demo_data.py"
echo "  3. Run demo:            python examples/test_routing_with_opa.py"
echo "  4. Start MCP server:    python -m mcp_server.server"
echo ""
echo "View logs:  docker-compose logs -f"
echo "Stop:       docker-compose down"
echo "================================================"
