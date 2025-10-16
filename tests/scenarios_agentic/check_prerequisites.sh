#!/bin/bash
#
# Pre-flight check for agentic tests
# Verifies all required services are running
#

set -e

echo "🔍 AgentMesh - Prerequisites Check"
echo "==================================="
echo ""

SUCCESS=0
FAILURES=0

check_service() {
    local name=$1
    local check_cmd=$2
    local fix_hint=$3
    
    echo -n "   $name... "
    if eval "$check_cmd" &>/dev/null; then
        echo "✅"
        ((SUCCESS++))
        return 0
    else
        echo "❌"
        echo "      Fix: $fix_hint"
        ((FAILURES++))
        return 1
    fi
}

echo "📋 Checking required services:"
echo ""

# NATS
check_service \
    "NATS Server (localhost:4222)" \
    "nc -z localhost 4222" \
    "nats-server --port 4222"

# OPA
check_service \
    "OPA Server (localhost:8181)" \
    "curl -s http://localhost:8181/health | grep -q ok" \
    "opa run --server --addr localhost:8181 ./policies/"

# PostgreSQL
check_service \
    "PostgreSQL (localhost:5432)" \
    "nc -z localhost 5432" \
    "docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=agentmesh123 postgres:15"

# Mesh Service
if command -v nats &> /dev/null; then
    check_service \
        "Mesh Service (NATS health)" \
        "timeout 2 nats req mesh.health '' --server nats://localhost:4222" \
        "python -m services.bootstrap.mesh_service"
else
    echo "   Mesh Service (NATS health)... ⚠️  (cannot verify - nats CLI not installed)"
    echo "      Hint: brew install nats-io/nats-tools/nats"
fi

# Python venv
echo ""
echo "📋 Checking Python environment:"
echo ""

if [ -d ".venv" ]; then
    echo "   Virtual environment... ✅"
    ((SUCCESS++))
else
    echo "   Virtual environment... ❌"
    echo "      Fix: python -m venv .venv && source .venv/bin/activate && pip install -e ."
    ((FAILURES++))
fi

# Check if nats-py is installed
if python -c "import nats" 2>/dev/null; then
    echo "   nats-py package... ✅"
    ((SUCCESS++))
else
    echo "   nats-py package... ❌"
    echo "      Fix: pip install nats-py"
    ((FAILURES++))
fi

# Check if pytest is installed
if command -v pytest &>/dev/null; then
    echo "   pytest... ✅"
    ((SUCCESS++))
else
    echo "   pytest... ⚠️  (tests can run without it)"
    echo "      Hint: pip install pytest pytest-asyncio"
fi

# Summary
echo ""
echo "==================================="
if [ $FAILURES -eq 0 ]; then
    echo "✅ All prerequisites met! ($SUCCESS checks passed)"
    echo ""
    echo "🚀 You can now run:"
    echo "   ./tests/scenarios_agentic/run_scenario_2.sh"
    echo ""
    echo "Or:"
    echo "   pytest tests/scenarios_agentic/test_2_policy_enforcement_agentic.py -v"
    exit 0
else
    echo "❌ $FAILURES checks failed, $SUCCESS passed"
    echo ""
    echo "📖 See tests/scenarios_agentic/SETUP.md for detailed setup instructions"
    exit 1
fi

