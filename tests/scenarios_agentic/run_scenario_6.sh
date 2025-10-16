#!/bin/bash
#
# Run AGENTIC Test Scenario 6: Metadata & Audit Queries
#
# This script runs the agentic tests for scenario 6 which demonstrate:
# - Querying audit logs via NATS
# - Querying agent registry via NATS
# - Zero knowledge of mesh internals
#

set -e

echo "=========================================="
echo "AGENTIC TEST SCENARIO 6"
echo "Metadata & Audit Queries"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."
echo ""

check_service() {
    local service_name=$1
    local check_command=$2
    
    if eval $check_command > /dev/null 2>&1; then
        echo -e "${GREEN}✅${NC} $service_name is running"
        return 0
    else
        echo -e "${RED}❌${NC} $service_name is NOT running"
        return 1
    fi
}

all_services_ok=true

# Check NATS
if ! check_service "NATS Server" "nc -zv localhost 4222"; then
    echo -e "${YELLOW}   Start with: nats-server${NC}"
    all_services_ok=false
fi

# Check OPA
if ! check_service "OPA Server" "curl -s http://localhost:8181/health"; then
    echo -e "${YELLOW}   Start with: opa run --server --addr localhost:8181 ./policies/${NC}"
    all_services_ok=false
fi

# Check mesh service (via NATS health check)
if ! python3 -c "
import asyncio
import nats
import json

async def check():
    try:
        nc = await nats.connect('nats://localhost:4222', timeout=2)
        response = await nc.request('mesh.health', b'{}', timeout=2)
        result = json.loads(response.data)
        await nc.close()
        return result.get('status') == 'healthy'
    except:
        return False

result = asyncio.run(check())
exit(0 if result else 1)
" 2>/dev/null; then
    echo -e "${RED}❌${NC} AgentMesh Service is NOT running"
    echo -e "${YELLOW}   Start with: python -m services.bootstrap.mesh_service${NC}"
    all_services_ok=false
else
    echo -e "${GREEN}✅${NC} AgentMesh Service is running"
fi

echo ""

if [ "$all_services_ok" = false ]; then
    echo -e "${RED}❌ Prerequisites not met. Please start required services.${NC}"
    echo ""
    echo "Quick start guide:"
    echo "  Terminal 1: nats-server"
    echo "  Terminal 2: opa run --server --addr localhost:8181 ./policies/"
    echo "  Terminal 3: python -m services.bootstrap.mesh_service"
    echo "  Terminal 4: $0"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites met!${NC}"
echo ""

# Run the tests
echo "🧪 Running Scenario 6 tests..."
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
fi

# Run pytest with verbose output
python -m pytest tests/scenarios_agentic/test_6_metadata_audit_agentic.py -v -s

test_result=$?

echo ""
if [ $test_result -eq 0 ]; then
    echo "=========================================="
    echo -e "${GREEN}✅ SCENARIO 6: ALL TESTS PASSED${NC}"
    echo "=========================================="
else
    echo "=========================================="
    echo -e "${RED}❌ SCENARIO 6: SOME TESTS FAILED${NC}"
    echo "=========================================="
fi

exit $test_result

