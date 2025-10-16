# AgentMesh Demo Scenarios

This directory contains runnable Python scripts that demonstrate AgentMesh capabilities.

---

## Prerequisites

Before running these scenarios, make sure:

1. **Docker services are running**:
   ```bash
   cd /path/to/AgentMesh/submission
   docker-compose up -d
   ```

2. **Python environment is activated**:
   ```bash
   cd /path/to/AgentMesh
   source .venv/bin/activate
   ```

3. **Verify services are healthy**:
   ```bash
   docker-compose ps
   # All services should show "Up" status
   ```

---

## Available Scenarios

### Scenario 1: Cross-Team Privacy-Preserving Query

**File**: `scenario1_privacy.py`

**What it demonstrates**:
- Agent registration with validation
- KB registration with connectivity check
- OPA policy upload (field-level masking)
- Governed KB query with automatic masking
- Audit trail viewing

**Run**:
```bash
python scenario1_privacy.py
```

**Expected Output**:
```
=======================================================================
Scenario 1: Cross-Team Privacy-Preserving Query
=======================================================================

📦 Initializing services...
✅ Services initialized

Step 1: Register Marketing Agent
----------------------------------------------------------------------
✅ Agent registered: marketing-agent-2
   Status: active

Step 2: Register Sales Knowledge Base (PostgreSQL)
----------------------------------------------------------------------
✅ KB registered: sales-kb-1
   Status: active

Step 3: Upload Privacy Policy
----------------------------------------------------------------------
✅ Policy uploaded: agentmesh

Step 4: Marketing Queries Sales KB (Governed)
----------------------------------------------------------------------
Query: SELECT customer_name, customer_email, customer_phone, ...

📊 Query Response (Field-Level Masking Applied):
----------------------------------------------------------------------
✅ Query executed successfully
   Rows returned: 5

Sample rows:

   Row 1:
      customer_name: Acme Corp
      customer_email: 🔒 MASKED
      customer_phone: 🔒 MASKED
      objection: Price too high
      region: APAC

🔍 Audit Information:
   Fields Masked: ['customer_email', 'customer_phone']
   Policy Version: agentmesh-v1.0
   Timestamp: 2025-10-16T14:32:15Z

Step 5: View Audit Trail
----------------------------------------------------------------------
📋 Recent audit logs for marketing-agent-2:

   Event ID: 1
   Type: QUERY
   Target: sales-kb-1
   Outcome: SUCCESS
   Masked Fields: ['customer_email', 'customer_phone']
   Timestamp: 2025-10-16T14:32:15Z

=======================================================================
✅ Scenario 1 Complete!
=======================================================================

Key Takeaways:
1. Marketing agent can query Sales KB (policy allows)
2. PII fields (email, phone) are automatically masked
3. All access is logged in audit trail
4. Mesh enforces governance without storing customer data
```

**Key Concepts**:
- **Policy Enforcement**: OPA evaluates access BEFORE query execution in <10ms
- **Response Interception**: KB returns full data (for allowed requests), mesh masks before delivery
- **Audit Trail**: Immutable logs with masked fields recorded
- **Zero-Copy**: Mesh doesn't store customer data

---

### Scenario 3: Real-Time Agent Discovery

**File**: `scenario3_discovery.py`

**What it demonstrates**:
- Connecting to NATS messaging
- Subscribing to directory updates (pub/sub)
- Receiving real-time notifications
- Querying mesh directory
- Dynamic agent discovery

**Run**:
```bash
python scenario3_discovery.py
```

**Expected Output**:
```
=======================================================================
Scenario 3: Real-Time Agent Discovery
=======================================================================

🔌 [discovery-agent-demo] Connecting to NATS...
✅ [discovery-agent-demo] Connected to NATS

📡 [discovery-agent-demo] Subscribing to mesh.directory.updates...
✅ [discovery-agent-demo] Subscribed to directory updates

Step 1: Query Current Directory State
=======================================================================
🔍 [discovery-agent-demo] Querying mesh directory...
✅ Directory query successful
   📊 Found 2 agents
   📊 Found 2 knowledge bases

   🤖 Registered Agents:
      - sales-agent-1
        Capabilities: query_kb, generate_report
        Status: active
      - marketing-agent-2
        Capabilities: query_kb, analyze_data
        Status: active

   💾 Registered Knowledge Bases:
      - sales-kb-1 (postgres)
        Operations: sql_query, insert, update, delete
      - graph-kb-1 (neo4j)
        Operations: cypher_query, create_node, create_relationship

Step 2: Listening for Real-Time Updates
=======================================================================
📡 Waiting for new agents/KBs to register...
💡 Tip: In another terminal, register agents/KBs via MCP tools
   Example: Use Claude Desktop to register a new agent

⏱️  Will listen for 60 seconds...

----------------------------------------------------------------------
📨 [discovery-agent-demo] Received notification: agent_registered
   Timestamp: 2025-10-16T14:45:23Z
   🤖 New agent discovered: analytics-agent-4
   📋 Capabilities: data_analysis, visualization, query_kb
   ✅ Total agents discovered: 1
----------------------------------------------------------------------

=======================================================================
Discovery Summary
=======================================================================
✅ Total agents discovered: 1
✅ Total KBs discovered: 0

🤖 Agents discovered during this session:
   - analytics-agent-4 at 2025-10-16T14:45:23Z

Step 3: Final Directory State
=======================================================================
🔍 [discovery-agent-demo] Querying mesh directory...
✅ Directory query successful
   📊 Found 3 agents
   📊 Found 2 knowledge bases

=======================================================================
✅ Scenario 3 Complete!
=======================================================================

Key Takeaways:
1. Agents can subscribe to real-time mesh updates via NATS
2. New agents/KBs are instantly discoverable (< 100ms)
3. No polling needed - pub/sub provides instant notifications
4. Agents can query directory anytime for current state
```

**Key Concepts**:
- **NATS Pub/Sub**: Real-time notifications to all subscribers
- **Dynamic Discovery**: No manual configuration needed
- **Instant Updates**: <100ms from registration to notification
- **Zero Downtime**: Mesh updates without restart

**Interactive Usage**:

While `scenario3_discovery.py` is running (listening for 60 seconds):

1. **Open Claude Desktop** in another window
2. **Register a new agent**:
   ```
   User: "Register an analytics agent with data visualization capabilities"
   ```
3. **Watch the terminal** - you'll see the notification appear instantly!

---

## Running All Scenarios

```bash
cd submission/examples

# Scenario 1 (Privacy-Preserving Query)
python scenario1_privacy.py

# Scenario 3 (Real-Time Discovery)
python scenario3_discovery.py
```

---

## Troubleshooting

### Error: "Connection refused" (NATS)

**Problem**: NATS server not running

**Solution**:
```bash
# Check NATS status
docker-compose ps nats

# If not running, start it
docker-compose up -d nats

# Verify NATS is healthy
curl http://localhost:8222/healthz
```

### Error: "Connection refused" (PostgreSQL)

**Problem**: PostgreSQL server not running

**Solution**:
```bash
# Check PostgreSQL status
docker-compose ps postgres

# If not running, start it
docker-compose up -d postgres

# Verify PostgreSQL is healthy
docker exec -it agentmesh-postgres-kb pg_isready -U admin
```

### Error: "OPA server not responding"

**Problem**: OPA server not running

**Solution**:
```bash
# Check OPA status
docker-compose ps opa

# If not running, start it
docker-compose up -d opa

# Verify OPA is healthy
curl http://localhost:8181/health
```

### Error: "ModuleNotFoundError"

**Problem**: Python environment not activated or PYTHONPATH not set

**Solution**:
```bash
# Navigate to project root
cd /path/to/AgentMesh

# Activate virtual environment
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=/path/to/AgentMesh:$PYTHONPATH

# Verify imports work
python -c "from adapters.messaging.nats_client import NATSWrapper; print('OK')"
```

---

## Creating Custom Scenarios

### Template

```python
#!/usr/bin/env python3
"""
My Custom Scenario

Demonstrates: [what this scenario shows]
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.registry.agent_service import AgentService
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter


async def main():
    print("=" * 70)
    print("My Custom Scenario")
    print("=" * 70)
    print()

    # Initialize services
    persistence = SQLitePersistenceAdapter(
        str(PROJECT_ROOT / "adapters/persistence/sqlite/config.yaml")
    )
    await persistence.connect()

    agent_service = AgentService(persistence)

    # Your scenario logic here
    # ...

    # Cleanup
    await persistence.disconnect()

    print("✅ Scenario Complete!")


if __name__ == "__main__":
    asyncio.run(main())
```

### Example: Query Multiple KBs

```python
# Query both PostgreSQL and Neo4j
postgres_result = await enforcement_service.query_kb_governed(
    requester_id="cpo-user-1",
    kb_id="sales-kb-1",
    operation="sql_query",
    params={"query": "SELECT * FROM commitments WHERE feature='Y'"}
)

neo4j_result = await enforcement_service.query_kb_governed(
    requester_id="cpo-user-1",
    kb_id="engineering-kb-3",
    operation="cypher_query",
    params={"query": "MATCH (f:Feature {name: 'Y'}) RETURN f"}
)

# Compare results (contradiction detection)
if postgres_result["timeline"] != neo4j_result["timeline"]:
    print("⚠️ Timeline contradiction detected!")
```

---

## Next Steps

1. **Run the scenarios** to see AgentMesh in action
2. **Modify scenarios** to test different policies or queries
3. **Create custom scenarios** for your use cases
4. **Integrate with Claude Desktop** for interactive demos

---

## Additional Resources

- **Main README**: `../README.md` - Project overview
- **Setup Guide**: `../SETUP.md` - Detailed installation
- **Architecture**: `../ARCHITECTURE.md` - Technical deep dive
- **Demo Walkthrough**: `../DEMO.md` - Visual scenarios
- **Evaluation Mapping**: `../EVALUATION_MAPPING.md` - Evidence for each criterion

---

**Happy experimenting with AgentMesh! 🎉**
