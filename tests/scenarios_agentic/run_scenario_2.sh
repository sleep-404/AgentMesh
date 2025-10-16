#!/bin/bash
#
# Run Scenario 2: Policy Enforcement & Privacy (Agentic)
#
# This script checks prerequisites and runs the agentic tests for scenario 2.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 AgentMesh - Scenario 2: Policy Enforcement (Agentic)"
echo "======================================================"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."
echo ""

# Check NATS
echo -n "   1. NATS Server (localhost:4222)... "
if nc -z localhost 4222 2>/dev/null; then
    echo "✅"
else
    echo "❌"
    echo ""
    echo "⚠️  NATS server not running!"
    echo "   Start it with: nats-server --port 4222"
    exit 1
fi

# Check OPA
echo -n "   2. OPA Server (localhost:8181)... "
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8181/health 2>/dev/null | grep -q "200"; then
    echo "✅"
else
    echo "❌"
    echo ""
    echo "⚠️  OPA server not running!"
    echo "   Start it with: opa run --server --addr localhost:8181 $PROJECT_ROOT/policies/"
    exit 1
fi

# Check PostgreSQL
echo -n "   3. PostgreSQL (localhost:5432)... "
if nc -z localhost 5432 2>/dev/null; then
    echo "✅"
else
    echo "❌"
    echo ""
    echo "⚠️  PostgreSQL not running!"
    echo "   Start it with: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=agentmesh123 postgres:15"
    exit 1
fi

# Check if mesh service is running
echo -n "   4. Mesh Service (NATS subjects)... "
if command -v nats &> /dev/null; then
    if timeout 2 nats req mesh.health "" --server nats://localhost:4222 &>/dev/null; then
        echo "✅"
    else
        echo "❌"
        echo ""
        echo "⚠️  Mesh service not responding on NATS!"
        echo "   Start it with: python -m services.bootstrap.mesh_service"
        exit 1
    fi
else
    echo "⚠️  (cannot verify - nats CLI not installed)"
fi

echo ""
echo "✅ All prerequisites met!"
echo ""

# Run tests
echo "🧪 Running Scenario 2 Tests..."
echo ""

cd "$PROJECT_ROOT"

# Activate venv if it exists
if [ -d ".venv" ]; then
    echo "🐍 Activating virtual environment..."
    source .venv/bin/activate
fi

# Run with pytest if available, otherwise run directly
if command -v pytest &> /dev/null; then
    echo "Running with pytest..."
    pytest tests/scenarios_agentic/test_2_policy_enforcement_agentic.py -v -s
else
    echo "Running directly with Python..."
    python tests/scenarios_agentic/test_2_policy_enforcement_agentic.py
fi

echo ""
echo "✅ Scenario 2 tests completed!"

