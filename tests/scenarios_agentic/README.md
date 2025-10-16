# Agentic Test Scenarios

This directory contains **truly agentic tests** that demonstrate how external agents interact with AgentMesh.

## Key Principles

### ✅ ALLOWED (External Agent Perspective)
1. Connect to NATS at `nats://localhost:4222`
2. Subscribe/publish to mesh NATS subjects
3. Use agent identity as authentication token
4. Discover capabilities dynamically

### ❌ FORBIDDEN (Internal Mesh Knowledge)
1. `from services.registry import AgentService` ❌
2. `from services.routing import RequestRouter` ❌
3. `from services.enforcement import EnforcementService` ❌
4. Direct Python method calls to mesh components ❌
5. Knowledge of mesh internal APIs ❌

## Test Structure

Each test file follows this pattern:
```python
from dummy_agents.simple_nats_agent import SimpleNATSAgent

# Create agent (knows only NATS URL)
agent = SimpleNATSAgent("nats://localhost:4222")
await agent.connect_to_mesh()

# Register via NATS
await agent.register_with_mesh(
    identity="my-agent-1",
    capabilities=["query_kb"],
    operations=["query"]
)

# Query KB via NATS - mesh handles everything
result = await agent.query_kb(
    kb_id="sales-kb-1",
    operation="sql_query",
    params={"query": "SELECT * FROM customers"}
)
```

## Prerequisites

Before running these tests, ensure all infrastructure is running:

```bash
# 1. NATS Server
nats-server --port 4222

# 2. OPA Server
opa run --server --addr localhost:8181 ./policies/

# 3. PostgreSQL
docker run -d -p 5432:5432 \
  -e POSTGRES_PASSWORD=agentmesh123 \
  -e POSTGRES_DB=agentmesh \
  postgres:15

# 4. Neo4j (optional, for some tests)
docker run -d -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/agentmesh123 \
  neo4j:5

# 5. Mesh Service
python -m services.bootstrap.mesh_service
```

Alternatively, use docker-compose:
```bash
docker-compose up -d
python -m services.bootstrap.mesh_service
```

## Running Tests

### Run all tests with pytest:
```bash
pytest tests/scenarios_agentic/ -v
```

### Run specific test file:
```bash
pytest tests/scenarios_agentic/test_2_policy_enforcement_agentic.py -v
```

### Run specific test:
```bash
pytest tests/scenarios_agentic/test_2_policy_enforcement_agentic.py::TestSection2PolicyEnforcementAgentic::test_2_1_query_with_field_masking -v
```

### Run test file directly (without pytest):
```bash
python tests/scenarios_agentic/test_2_policy_enforcement_agentic.py
```

## Test Scenarios

### ✅ Scenario 2: Policy Enforcement & Privacy
**File:** `test_2_policy_enforcement_agentic.py`

Tests:
1. **Query with Field Masking** - Agent queries KB, mesh applies masking automatically
2. **Unauthorized Write Denied** - Agent attempts write, mesh denies based on policy
3. **Different Agents Different Masking** - Multiple agents get different masking per policy
4. **Agent Discovers Operations** - Agent dynamically discovers what's allowed

**Status:** ✅ Complete

### ⏳ Scenario 1: Registration & Discovery
**File:** `test_1_registration_discovery_agentic.py` (TODO)

### ⏳ Scenario 3: Agent Invocation
**File:** `test_3_agent_invocation_agentic.py` (TODO)

### ⏳ Scenario 4: Real-Time Notifications
**File:** `test_4_realtime_notifications_agentic.py` (TODO)

### ✅ Scenario 5: KB Request-Reply
**File:** `test_5_kb_request_reply_agentic.py`

Tests:
1. **Agent Queries KB Basic** - Agent queries KB via mesh with simple SQL
2. **Multiple Agents Concurrent** - Multiple agents query same KB concurrently
3. **Non-Existent KB Error** - Agent handles error for non-existent KB gracefully

**Status:** ✅ Complete

### ⏳ Scenario 6: Metadata & Audit
**File:** `test_6_metadata_audit_agentic.py` (TODO)

## Benefits of Agentic Testing

1. **True Integration Testing** - Tests the actual external interface
2. **Language Agnostic** - Could implement same tests in Go, JavaScript, etc.
3. **Realistic** - Matches how real agents will use the mesh
4. **Isolation** - Mesh runs as separate service
5. **Debugging** - Can inspect NATS messages with `nats sub "mesh.>"`
6. **Security** - Tests authentication/authorization properly
7. **Performance** - Tests real network latency
8. **Scalability** - Can run mesh and agents on different machines

## Debugging

### Monitor NATS messages:
```bash
nats sub "mesh.>" --server nats://localhost:4222
```

### Monitor specific subject:
```bash
nats sub "mesh.routing.kb_query" --server nats://localhost:4222
```

### Check mesh health:
```bash
nats req mesh.health "" --server nats://localhost:4222
```

### Check OPA policies:
```bash
curl http://localhost:8181/v1/policies
```

## Architecture

```
┌─────────────────┐
│  Test Agent     │  (SimpleNATSAgent - ZERO mesh knowledge)
│  (Python)       │
└────────┬────────┘
         │ NATS only
         ↓
┌─────────────────┐
│  NATS Server    │  (Message broker)
│  localhost:4222 │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Mesh Service   │  (services/bootstrap/mesh_service.py)
│  ├─ Router      │  (Handles all mesh logic)
│  ├─ Enforcement │
│  ├─ OPA Client  │
│  └─ KB Adapters │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  OPA Server     │  (Policy enforcement)
│  localhost:8181 │
└─────────────────┘
         │
         ↓
┌─────────────────┐
│  PostgreSQL/    │  (Knowledge bases)
│  Neo4j          │
└─────────────────┘
```

## Comparison: Old vs Agentic Tests

### Old Test (❌ Not Agentic):
```python
from services.registry import AgentService
from services.routing import RequestRouter

# Direct access to mesh internals
agent_service = AgentService(...)
response = await agent_service.register_agent(...)
```

### Agentic Test (✅ True External Perspective):
```python
from dummy_agents.simple_nats_agent import SimpleNATSAgent

# Agent only knows NATS
agent = SimpleNATSAgent("nats://localhost:4222")
await agent.connect_to_mesh()
response = await agent.register_with_mesh(...)
```

The agentic version is how **real agents in production** will interact with AgentMesh!
