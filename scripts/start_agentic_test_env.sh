#!/bin/bash

# Script to start all services needed for agentic testing
# This script checks for prerequisites and starts the mesh service

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting AgentMesh Agentic Test Environment"
echo "=============================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if NATS server is running
echo "📡 Checking NATS server..."
if ! nc -z localhost 4222 2>/dev/null; then
    echo -e "${RED}❌ NATS server not running on port 4222${NC}"
    echo "   Start it with: nats-server --port 4222"
    echo ""
    exit 1
else
    echo -e "${GREEN}✅ NATS server is running${NC}"
fi

# Check if OPA server is running
echo "🔒 Checking OPA server..."
if ! nc -z localhost 8181 2>/dev/null; then
    echo -e "${RED}❌ OPA server not running on port 8181${NC}"
    echo "   Start it with: opa run --server --addr localhost:8181 ./policies/"
    echo ""
    exit 1
else
    echo -e "${GREEN}✅ OPA server is running${NC}"
fi

# Check if database directory exists
echo "📊 Checking database..."
mkdir -p "$PROJECT_ROOT/data"
if [ -f "$PROJECT_ROOT/data/agentmesh.db" ]; then
    echo -e "${GREEN}✅ Database exists${NC}"
else
    echo -e "${YELLOW}⚠️  Database will be created${NC}"
fi

# Optional: Check PostgreSQL (warn if not running)
echo "🐘 Checking PostgreSQL (optional)..."
if ! nc -z localhost 5432 2>/dev/null; then
    echo -e "${YELLOW}⚠️  PostgreSQL not running (optional for KB tests)${NC}"
    echo "   Start it with: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=agentmesh123 postgres:15"
else
    echo -e "${GREEN}✅ PostgreSQL is running${NC}"
fi

# Optional: Check Neo4j (warn if not running)
echo "🔗 Checking Neo4j (optional)..."
if ! nc -z localhost 7687 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Neo4j not running (optional for KB tests)${NC}"
    echo "   Start it with: docker run -d -p 7687:7687 -e NEO4J_AUTH=neo4j/agentmesh123 neo4j:5"
else
    echo -e "${GREEN}✅ Neo4j is running${NC}"
fi

echo ""
echo "=============================================="
echo "🚀 Starting AgentMesh Service"
echo "=============================================="
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "🐍 Activating virtual environment..."
    source .venv/bin/activate
fi

# Start mesh service
echo "🌐 Starting mesh service..."
echo "   Press Ctrl+C to stop"
echo ""

python -m services.bootstrap.mesh_service

