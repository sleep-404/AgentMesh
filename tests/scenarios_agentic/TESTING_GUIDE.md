# End-to-End Testing Guide for Agentic Tests

This guide provides step-by-step instructions for running and validating the agentic test implementation.

## Quick Test (5 Minutes)

### Step 1: Start Services

Open 3 terminals:

**Terminal 1 - NATS:**
```bash
nats-server --port 4222
```

**Terminal 2 - OPA:**
```bash
cd /Users/jeevan/AgentMesh
opa run --server --addr localhost:8181 ./policies/
```

**Terminal 3 - Mesh Service:**
```bash
cd /Users/jeevan/AgentMesh
source .venv/bin/activate
python -m services.bootstrap.mesh_service
```

Wait for mesh service to show:
```
✅ AgentMesh Service is ready!
```

### Step 2: Verify Setup

**Terminal 4:**
```bash
cd /Users/jeevan/AgentMesh
source .venv/bin/activate
python tests/scenarios_agentic/verify_setup.py
```

Expected output:
```
✅ All checks passed! Ready to run agentic tests.
```

### Step 3: Run Tests

```bash
pytest tests/scenarios_agentic/test_1_registration_discovery_agentic.py -v -s
```

Expected output:
```
test_1_1_user_registers_agent_agentic PASSED
test_1_2_user_registers_kb_agentic PASSED
test_1_3_agent_discovers_capabilities_agentic PASSED

======================== 3 passed in X.XXs ========================
```

## Detailed Test Validation

### Test 1.1: Agent Registration

**What happens:**
1. SimpleNATSAgent connects to NATS
2. Sends registration to `mesh.registry.agent.register`
3. Mesh service validates and stores agent
4. Agent queries directory to verify registration

**Validation points:**
- ✅ Agent receives `agent_id` and `status`
- ✅ Agent appears in directory query
- ✅ Capabilities are correctly stored
- ✅ No direct service calls (only NATS)

**Expected logs (mesh service):**
```
INFO - 📥 Received agent registration: sales-agent-1
INFO - Agent 'sales-agent-1' registered successfully
INFO - ✅ Agent registered: sales-agent-1 (status: active)
```

### Test 1.2: KB Registration

**What happens:**
1. Agent sends KB registration to `mesh.registry.kb.register`
2. Mesh validates KB type and operations
3. Mesh attempts connectivity check
4. KB is stored and appears in directory

**Validation points:**
- ✅ KB receives confirmation with status
- ✅ KB appears in directory query
- ✅ Operations are validated
- ✅ Status can be "offline" (DB not running - OK)

**Expected logs (mesh service):**
```
INFO - 📥 Received KB registration: sales-kb-test
INFO - KB 'sales-kb-test' registered successfully
INFO - ✅ KB registered: sales-kb-test (status: offline)
```

Note: "offline" status is OK - it means DB isn't running, but registration still works.

### Test 1.3: Discovery

**What happens:**
1. Multiple agents register themselves
2. KB is registered
3. Marketing agent queries directory with filters
4. Agent makes decisions based on discovered capabilities

**Validation points:**
- ✅ All registered agents appear
- ✅ Capability filter works
- ✅ KB type filter works
- ✅ Total counts are accurate

**Expected output:**
```
📊 Discovered 2 total agents
📊 Discovered 2 agents with 'query_kb' capability
📊 Discovered 1 agents with 'write_kb' capability
📊 Discovered 1 total KBs
📊 Discovered 1 Neo4j KBs
```

## Manual Testing

You can test the interface manually:

```python
import asyncio
from dummy_agents.simple_nats_agent import SimpleNATSAgent

async def manual_test():
    # Create and connect
    agent = SimpleNATSAgent("nats://localhost:4222")
    await agent.connect_to_mesh()
    
    # Register
    result = await agent.register_with_mesh(
        identity="manual-test-agent",
        capabilities=["query_kb"],
        operations=["query"],
    )
    print(f"Registered: {result}")
    
    # Discover
    agents = await agent.discover_agents()
    print(f"Found {agents['total_count']} agents")
    for a in agents['agents']:
        print(f"  - {a['identity']}: {a['capabilities']}")
    
    # Cleanup
    await agent.disconnect()

# Run it
asyncio.run(manual_test())
```

## Monitoring NATS Traffic

To see all NATS messages flowing through the mesh:

```bash
# In separate terminal
nats sub "mesh.>"
```

You'll see messages like:
```
[mesh.registry.agent.register] {"identity": "sales-agent-1", ...}
[mesh.directory.query] {"type": "agents", ...}
[mesh.directory.updates] {"type": "agent_registered", ...}
```

## Common Issues & Solutions

### Issue: "Connection refused" 
**Cause:** NATS not running  
**Solution:** Start NATS: `nats-server --port 4222`

### Issue: "Registration timeout"
**Cause:** Mesh service not running  
**Solution:** Start mesh: `python -m services.bootstrap.mesh_service`

### Issue: "OPA connection failed" in mesh logs
**Cause:** OPA not running  
**Solution:** Start OPA: `opa run --server --addr localhost:8181 ./policies/`

### Issue: KB status is "offline"
**Cause:** PostgreSQL/Neo4j not running  
**Solution:** This is OK for registration tests. KB will be "offline" but still registered.

### Issue: Test fails with "agent not found"
**Cause:** Directory update hasn't propagated  
**Solution:** Tests include `await asyncio.sleep(0.5)` - if still failing, increase delay.

## Performance Expectations

**Typical timings:**
- Agent registration: 10-50ms
- KB registration: 20-100ms (includes connectivity check)
- Directory query: 5-20ms
- Full test suite: 2-5 seconds

**Slower than expected?**
- Check if OPA server is responding
- Check database connectivity (if testing with real DBs)
- Check NATS server load

## Test Coverage

The tests cover:

**Registration:**
- ✅ Agent registration with validation
- ✅ KB registration with type validation
- ✅ Health/connectivity checks
- ✅ Duplicate detection

**Discovery:**
- ✅ List all agents
- ✅ List all KBs
- ✅ Filter by capability
- ✅ Filter by KB type
- ✅ Filter by status

**Communication:**
- ✅ Request-reply pattern
- ✅ NATS subjects
- ✅ Message serialization
- ✅ Error handling
- ✅ Timeouts

## Integration Points

These tests validate that:

1. **NATS messaging works** - All communication via NATS
2. **Mesh service responds** - All handlers work correctly
3. **Persistence works** - Agents/KBs are stored
4. **Directory service works** - Queries return correct data
5. **Validation works** - Invalid requests are rejected
6. **Health checks work** - Status is updated correctly

## Next Steps After Validation

Once Section 1 tests pass:

1. **Section 2:** Implement policy enforcement tests
2. **Section 3:** Implement agent invocation tests
3. **Section 4:** Implement notification tests
4. **Section 5:** Implement KB query tests with governance
6. **Section 6:** Implement audit query tests

## Continuous Integration

To run in CI/CD:

```yaml
# .github/workflows/agentic-tests.yml
name: Agentic Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      nats:
        image: nats:latest
        ports:
          - 4222:4222
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: agentmesh123
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Start OPA
        run: |
          wget https://openpolicyagent.org/downloads/latest/opa_linux_amd64
          chmod +x opa_linux_amd64
          ./opa_linux_amd64 run --server --addr localhost:8181 ./policies/ &
          sleep 2
      
      - name: Start Mesh Service
        run: |
          python -m services.bootstrap.mesh_service &
          sleep 3
      
      - name: Verify Setup
        run: python tests/scenarios_agentic/verify_setup.py
      
      - name: Run Tests
        run: pytest tests/scenarios_agentic/test_1_registration_discovery_agentic.py -v
```

## Success Criteria Checklist

For each test run, verify:

- [ ] All 3 tests pass
- [ ] No Python exceptions
- [ ] No NATS connection errors
- [ ] Mesh service logs show successful operations
- [ ] Agents are discoverable after registration
- [ ] KBs are discoverable after registration
- [ ] No direct service imports in test code
- [ ] All communication via NATS only

## Reporting Issues

If tests fail:

1. **Capture mesh service logs** (Terminal 3 output)
2. **Capture NATS traffic** (`nats sub "mesh.>"`)
3. **Run verification script** (`verify_setup.py`)
4. **Check service status:**
   - NATS: `nc -zv localhost 4222`
   - OPA: `curl http://localhost:8181/health`
   - Mesh: Check Terminal 3 for errors

5. **Include in issue:**
   - Python version
   - OS version
   - Error messages
   - Service logs
   - Steps to reproduce

---

**Last Updated:** October 16, 2025  
**Status:** Ready for testing  
**Prerequisites:** NATS, OPA, Mesh Service

