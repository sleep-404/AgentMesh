# Scenario 6: Metadata & Audit Queries - Setup Guide

## Overview

Scenario 6 tests demonstrate:
- **Test 6.1**: Querying audit logs via NATS
- **Test 6.2**: Querying agent registry via NATS

Both tests use **zero mesh internals** - all communication happens via NATS.

## What Was Implemented

### 1. Mesh Service Changes (`services/bootstrap/mesh_service.py`)

Added NATS handler for audit log queries:

```python
async def _handle_audit_query(self, msg) -> None:
    """Handle audit log query request from NATS."""
    # Parses query parameters
    # Calls persistence.query_audit_logs()
    # Returns audit records via NATS reply
```

This handler subscribes to: `mesh.audit.query`

### 2. SimpleNATSAgent Extension (`dummy_agents/simple_nats_agent.py`)

Added method for querying audit logs:

```python
async def query_audit_logs(
    self,
    event_type: str | None = None,
    source_id: str | None = None,
    target_id: str | None = None,
    outcome: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Query audit logs from the mesh via NATS."""
```

### 3. Test File (`tests/scenarios_agentic/test_6_metadata_audit_agentic.py`)

Two comprehensive tests:
- `test_6_1_user_queries_audit_logs_agentic`: Tests audit log querying with various filters
- `test_6_2_user_queries_agent_registry_agentic`: Tests registry queries with capability/type filters

## Prerequisites

### Required Services

1. **NATS Server**
   ```bash
   nats-server --port 4222
   ```

2. **OPA Server**
   ```bash
   opa run --server --addr localhost:8181 ./policies/
   ```

3. **AgentMesh Service** (⚠️ IMPORTANT: Must be restarted to pick up new handler)
   ```bash
   # Stop any existing mesh service (Ctrl+C)
   
   # Start fresh with updated code
   python -m services.bootstrap.mesh_service
   ```

   **Why restart?** The `mesh.audit.query` handler was just added, so any mesh service that was running before needs to be restarted to include this handler.

## Running the Tests

### Option 1: Using the provided script

```bash
./tests/scenarios_agentic/run_scenario_6.sh
```

This script will:
- Check all prerequisites
- Run the tests with pytest
- Display results

### Option 2: Direct pytest

```bash
# Activate virtual environment
source .venv/bin/activate

# Run scenario 6 tests
python -m pytest tests/scenarios_agentic/test_6_metadata_audit_agentic.py -v -s
```

## Test Details

### Test 6.1: Query Audit Logs

Demonstrates:
1. Generate audit events by:
   - Registering 2 agents
   - Registering 1 KB
2. Query audit logs with various filters:
   - All logs (no filter)
   - By event type (`register`)
   - By source agent
   - By outcome (`success`)
   - By time range (last 5 minutes)
   - Multiple filters combined
   - By target (KB ID)

Verifications:
- ✅ Audit logs are returned
- ✅ Event type filter works
- ✅ Source filter works
- ✅ Outcome filter works
- ✅ Time range filter works
- ✅ Multiple filters work together
- ✅ All communication via NATS only

### Test 6.2: Query Agent Registry

Demonstrates:
1. Register diverse entities:
   - 3 agents with different capabilities
   - 2 KBs (Postgres and Neo4j)
2. Query registry with filters:
   - All agents
   - Agents by capability (`query_kb`, `write_kb`, `invoke_agent`)
   - All KBs
   - KBs by type (`postgres`, `neo4j`)
3. Verify specific entity details

Verifications:
- ✅ Directory query returns all agents
- ✅ Capability filters work correctly
- ✅ KB type filters work correctly
- ✅ Specific agent details are accurate
- ✅ Specific KB details are accurate
- ✅ All communication via NATS only

## Expected Output

When tests pass, you should see:

```
============================================
TEST 6.1: User Queries Audit Logs (AGENTIC)
============================================
📝 Generating audit events...
✅ Registered audit-test-agent-1-[id]
✅ Registered audit-test-agent-2-[id]
✅ Registered audit-test-kb-[id]

--- Querying Audit Logs via NATS ---
📊 Total audit logs: [N]
✅ Audit log structure verified
✅ Event type filter works correctly
✅ Source filter works correctly
✅ Outcome filter works correctly
✅ Time range filter works correctly
✅ Multiple filters work correctly
✅ Agent can query audit trail without direct persistence access

============================================
TEST 6.1: PASSED ✅
============================================
```

## Troubleshooting

### Error: `nats: no responders available for request`

**Cause**: The `mesh.audit.query` subject has no handler.

**Solution**: Restart the mesh service to pick up the new audit query handler.

```bash
# Stop existing mesh service (Ctrl+C in its terminal)
# Start fresh
python -m services.bootstrap.mesh_service
```

### Error: `KeyError: 'total_count'`

**Cause**: The directory query response structure is unexpected.

**Solution**: Ensure you're running the latest mesh service code. The handler should return `total_count` in the response.

### Error: Test assertions fail (no audit logs found)

**Cause**: Audit logging might not be enabled or working correctly in the mesh.

**Solution**: 
1. Check that audit events are being logged during agent/KB registration
2. Verify the persistence layer is working correctly
3. Check mesh service logs for any errors

## Architecture

```
Test Agent (SimpleNATSAgent)
    |
    | NATS: mesh.audit.query
    | {"event_type": "register", "limit": 100}
    |
    v
Mesh Service (_handle_audit_query)
    |
    | persistence.query_audit_logs(AuditQuery(...))
    |
    v
SQLite Persistence Adapter
    |
    | SQL: SELECT * FROM audit_events WHERE...
    |
    v
Response back via NATS
    |
    | {"audit_logs": [...], "total_count": N}
    |
    v
Test Agent receives results
```

## Key Points

1. ✅ **Zero Mesh Knowledge**: Tests import nothing from `services.*` or `adapters.*`
2. ✅ **NATS Only**: All communication via NATS request-reply
3. ✅ **Language Agnostic**: Could be written in any language (Python, Go, JavaScript, etc.)
4. ✅ **Realistic**: This is exactly how external agents will interact with the mesh
5. ✅ **Complete Coverage**: Tests all audit query filters and registry query options

## Next Steps

After scenario 6 passes:
1. Review test output to understand audit log structure
2. Try querying audit logs for KB queries (event_type="query")
3. Try querying audit logs for agent invocations (event_type="invoke")
4. Explore time-based analysis of mesh activity
5. Build dashboard or monitoring tools using these queries

