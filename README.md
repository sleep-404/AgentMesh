# AgentMesh: Governed Orchestration Infrastructure

> A routing and governance layer that enables secure, policy-driven access
> to distributed knowledge bases without storing organizational knowledge itself.

## 🎯 Quick Links
- [Architecture Overview](#-architecture-overview)
- [Core Design Decisions](#-design-philosophy)
- [Setup & Installation](#-setup--installation)
- [Demo Scenarios](#-demo-scenarios)
- [Evaluation Criteria Mapping](#-evaluation-criteria-mapping)

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Users/LLMs (via MCP)                      │
└────────────────────────┬────────────────────────────────────┘
                         │ Model Context Protocol
┌────────────────────────▼────────────────────────────────────┐
│                      MCP Server                              │
│  (Auto-generates tools from KB adapter interfaces)          │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                 AgentMesh Routing Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Registry   │  │ Policy Engine│  │  Audit Store │      │
│  │  (Agents/KBs)│  │  (OPA-RBAC)  │  │  (SQLite)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           NATS Messaging Layer                        │  │
│  │   • Directory Updates (Pub/Sub)                       │  │
│  │   • Agent-Agent Messaging (Private Subjects)          │  │
│  │   • KB Request-Reply (Message Broker)                 │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ Forward query unchanged
┌────────────────────────▼────────────────────────────────────┐
│                    KB Adapters                               │
│  (PostgreSQL | Neo4j | Vector DBs | REST APIs)              │
└────────────────────────┬────────────────────────────────────┘
                         │ Native query execution
┌────────────────────────▼────────────────────────────────────┐
│              Knowledge Bases (User-Owned)                    │
│  (PostgreSQL | Neo4j | Pinecone | REST APIs)                │
└──────────────────────────────────────────────────────────────┘
```

### What the Mesh Does (Infrastructure):
- ✅ Routes requests to appropriate KBs/agents based on registry
- ✅ Enforces field-level masking via response interception
- ✅ Maintains metadata (registry, audit logs) - NOT organizational knowledge
- ✅ Exposes MCP tools auto-generated from KB adapters
- ✅ Real-time pub/sub for agent discovery and notifications
- ✅ Message broker pattern for governed KB access

### What the Mesh Does NOT Do (Intelligence):
- ❌ Store organizational insights (lives in KBs)
- ❌ Detect contradictions (user reasoning systems do this)
- ❌ Translate queries (forwards unchanged to KBs)

---

## 🎨 Design Philosophy

### Key Principle: Infrastructure, Not Intelligence
The mesh is a **routing + governance + observability** layer. Think of it as:
- **NOT** a knowledge store (no duplication of KB data)
- **NOT** a semantic engine (no query interpretation)
- **YES** a policy enforcer (intercepts responses, masks fields)
- **YES** an orchestrator (routes, tracks, logs)

### Critical Decisions:
1. **Pass-Through Queries**: Mesh forwards queries unchanged (SQL/Cypher/REST) to KB adapters
2. **Pre-Query Policy Enforcement**: OPA evaluates access policies BEFORE DB queries execute
3. **Response Interception**: Field-level masking applied AFTER KBs return data (for allowed requests)
4. **Lightweight Metadata**: Extensible schema starts simple (event type, timestamp, outcome)
5. **Auto-Generated Tools**: MCP tools created automatically from KB adapter interfaces
6. **NATS Messaging**: Real-time notifications and message broker for all communications

---

## 🚀 Setup & Installation

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- Claude Desktop (for MCP integration)

### Quick Start

```bash
# 1. Clone and setup
git clone <your-repo>
cd AgentMesh

# 2. Start all infrastructure services
docker-compose up -d

# This starts:
# - PostgreSQL (KB) on port 5432
# - Neo4j (KB) on ports 7474, 7687
# - NATS (messaging) on ports 4222, 8222
# - OPA (policy engine) on port 8181
# - SQLite persistence (file-based, no container needed)

# 3. Verify services are healthy
docker-compose ps

# 4. Configure Claude Desktop
# Edit: ~/Library/Application Support/Claude/claude_desktop_config.json
# Add MCP server configuration (see MCP_SETUP.md)

# 5. Restart Claude Desktop and start using!
```

### Service Endpoints

| Service | Endpoint | Purpose |
|---------|----------|---------|
| PostgreSQL | `localhost:5432` | Knowledge Base (relational) |
| Neo4j | `localhost:7474` (HTTP), `localhost:7687` (Bolt) | Knowledge Base (graph) |
| NATS | `localhost:4222` (client), `localhost:8222` (monitoring) | Messaging layer |
| OPA | `localhost:8181` | Policy engine |
| SQLite | `data/agentmesh.db` | Mesh persistence |

---

## 🎬 Demo Scenarios

### Scenario 1: Cross-Team Privacy-Preserving Query

**Setup**: Marketing agent queries Sales KB for customer objections

```bash
# Via Claude Desktop (using MCP tools)
User: "Register marketing agent with query capabilities"
Claude: [Uses register_agent tool]
  → Agent ID: marketing-agent-1
  → Status: active

User: "Query the sales KB: SELECT * FROM customers WHERE region='APAC'"
Claude: [Uses query_kb_governed tool]
  → Policy Check: Allow with masking
  → Fields Masked: customer_email, customer_phone
  → Result: 150 rows with masked PII
```

**What it shows**:
- Field-level masking via response interception
- OPA policy enforcement
- Audit logging with masked fields

### Scenario 2: Agent-to-Agent Coordination

**Setup**: Sales agent invokes Engineering agent to prioritize feature

```bash
# Via MCP tools
User: "Sales agent invokes engineering agent to prioritize feature Y"
Claude: [Uses invoke_agent_governed tool]
  → Source: sales-agent-1
  → Target: engineering-agent-1
  → Operation: prioritize_feature
  → Tracking ID: inv-123
  → Status: queued → processing → completed
```

**What it shows**:
- Governed agent invocation
- Lifecycle tracking
- Audit trail across agent boundaries

### Scenario 3: Real-Time Agent Discovery

**Setup**: New KB registered, all connected agents notified

```bash
# Terminal 1: Start agent
python examples/sample_agent.py

# Terminal 2: Via Claude Desktop
User: "Register engineering KB"
Claude: [Uses register_kb tool]
  → KB ID: engineering-kb-1
  → Status: active

# Terminal 1 output:
INFO: [AGENT] Received notification: New KB registered
  KB ID: engineering-kb-1
  Type: neo4j
  Operations: cypher_query, create_node
```

**What it shows**:
- NATS pub/sub for real-time notifications
- Automatic capability discovery
- Zero-downtime mesh updates

### Scenario 4: Multi-Source Synthesis (User LLM)

**Setup**: CPO's LLM queries both Sales and Engineering KBs

```bash
# Via Claude Desktop
User: "What's the timeline for feature Y?"
Claude:
  [Queries sales-kb-1] → "Q1 2025"
  [Queries engineering-kb-1] → "Q3 2025"

  "I found a contradiction:
   - Sales committed to Q1 2025
   - Engineering estimates Q3 2025
   Recommendation: Align teams or adjust customer expectations"
```

**What it shows**:
- Mesh provides governed access to multiple KBs
- Contradiction detection happens in user's LLM (NOT the mesh)
- Mesh is infrastructure, intelligence lives in agents/LLMs

---

## 📚 Further Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Deep dive into design decisions and components
- [THINKING.md](THINKING.md) - Problem-solving approach & trade-offs
- [DEMO.md](DEMO.md) - Screenshots and detailed walkthrough
- [docker-compose.yml](docker-compose.yml) - Complete infrastructure setup

---

## 🔮 Future Extensions (Designed, Not Implemented)

### Extensibility Hooks
1. **Medium/Heavy Audit Logs**: Store full request/response in object store
2. **Advanced ABAC Policies**: Jurisdiction, purpose-of-use, time-based rules
3. **Multi-Region Federation**: Cross-region governance with data residency
4. **Policy Simulation**: Test policies in shadow mode before activation
5. **Health Inference**: Predict KB health using traffic patterns

*See ARCHITECTURE.md Section 8 for implementation paths*

---

## 🧪 Testing

### Run All Tests

```bash
# Prerequisites: Docker running
docker-compose up -d

# Run all integration tests
pytest tests/scenarios/ -v

# Expected: 16/20 scenarios passing (80% coverage)
# - ✅ Registration & Discovery (3/3)
# - ✅ Policy Enforcement (3/3)
# - ✅ Agent Invocation (2/2)
# - ✅ Real-Time Notifications (3/3)
# - ✅ KB Request-Reply (3/3)
# - ✅ Metadata & Audit (2/2)
```

### Performance Benchmarks

```bash
# Routing overhead test
pytest tests/scenarios/test_5_kb_request_reply.py -v

# Typical results:
# - Policy lookup: <10ms
# - Field masking: <5ms
# - Total mesh overhead: <20ms
# - KB query time: Variable (depends on KB)
```

---

## 🧠 Core Insight

> "The mesh is infrastructure, not intelligence. Knowledge lives in KBs.
> Intelligence lives in agents and user reasoning systems. The mesh routes,
> governs, and observes."

This design enables:
- **Bring-Your-Own-Reasoning**: Connect any LLM via MCP
- **Zero-Copy Governance**: No data duplication, only metadata
- **Universal Integration**: One adapter interface, any KB type
- **Real-Time Discovery**: Agents discover capabilities via NATS pub/sub

---

## 📦 Project Structure

```
submission/
├── README.md              # This file - main documentation
├── ARCHITECTURE.md        # Technical deep dive
├── THINKING.md           # Design rationale & trade-offs
├── DEMO.md               # Visual walkthrough with screenshots
├── docker-compose.yml    # Complete infrastructure setup
└── examples/             # Demo scripts and scenarios
    ├── scenario1_privacy.py
    ├── scenario2_coordination.py
    └── scenario3_discovery.py
```

---

## 🚢 Deployment

### Development
```bash
docker-compose up -d
# Uses SQLite persistence, single instance
```

### Production (Future)
```bash
# Uncomment PostgreSQL persistence in docker-compose.yml
# Enable TimescaleDB for time-series audit logs
# Deploy multiple mesh instances with NATS clustering
# Add Redis for distributed policy cache
```

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

- **Anthropic**: For the MCP protocol and Claude Desktop integration
- **OPA**: For the powerful policy engine
- **NATS**: For the lightweight messaging infrastructure
- **PostgreSQL/Neo4j**: For excellent database support
