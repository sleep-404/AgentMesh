# AgentMesh: Technical Architecture

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Core Components](#2-core-components)
3. [Request Flow](#3-request-flow)
4. [Policy Enforcement](#4-policy-enforcement)
5. [Scalability Design](#5-scalability-design)
6. [Security Model](#6-security-model)
7. [Data Schemas](#7-data-schemas)
8. [Extensibility Hooks](#8-extensibility-hooks)
9. [Deployment Architecture](#9-deployment-architecture)
10. [Trade-offs & Decisions](#10-trade-offs--decisions)

---

## 1. System Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Users' LLMs/Reasoning Systems            │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP Protocol (JSON-RPC over stdio)
┌────────────────────────▼────────────────────────────────────┐
│                      MCP Server                              │
│  • Tool Generation from KB Adapters                          │
│  • Registry Management Tools (9 tools)                       │
│  • Knowledge Base Tools (8 tools: 4 Postgres + 4 Neo4j)     │
└────────────────────────┬────────────────────────────────────┘
                         │ Python Function Calls
┌────────────────────────▼────────────────────────────────────┐
│                 AgentMesh Service Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Registry     │  │ Enforcement  │  │  Directory   │      │
│  │ Service      │  │ Service      │  │  Service     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│  ┌──────▼──────────────────▼──────────────────▼───────┐    │
│  │           NATS Messaging Layer                      │    │
│  │  • mesh.directory.updates (pub/sub)                 │    │
│  │  • mesh.directory.query (request-reply)             │    │
│  │  • {kb_id}.adapter.query (request-reply)            │    │
│  │  • agent.{agent_id} (private subjects)              │    │
│  └─────────────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    Persistence Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Agent        │  │ KB           │  │ Policy       │      │
│  │ Registry     │  │ Registry     │  │ Store        │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ Audit        │  │ OPA Client   │                        │
│  │ Logs         │  │ (External)   │                        │
│  └──────────────┘  └──────────────┘                        │
│                                                              │
│  Storage: SQLite (dev) / PostgreSQL (prod)                  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    KB Adapter Layer                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  PostgreSQL Adapter                                   │  │
│  │  • Operations: sql_query, insert, update, delete     │  │
│  │  • NATS Subject: postgres-kb-1.adapter.query         │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Neo4j Adapter                                        │  │
│  │  • Operations: cypher_query, create_node, etc.       │  │
│  │  • NATS Subject: neo4j-kb-1.adapter.query            │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ Native Protocols
┌────────────────────────▼────────────────────────────────────┐
│              External Knowledge Bases                        │
│  • PostgreSQL (port 5432)                                    │
│  • Neo4j (ports 7474, 7687)                                  │
│  • Future: Vector DBs, REST APIs, etc.                      │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 Design Principles

1. **Infrastructure Boundaries**: Mesh = Route + Govern + Observe (NO intelligence)
2. **Zero-Copy**: Mesh stores only metadata, never duplicates KB data
3. **KB-Agnostic**: Pass queries unchanged; support any query language
4. **Policy-First**: OPA evaluates access BEFORE query execution; field masking AFTER data retrieval
5. **Message Broker Pattern**: Authorization in mesh, execution in adapters

---

## 2. Core Components

### 2.1 Registry/Directory Service

**Purpose**: Maintain catalog of agents/KBs with capabilities

**Implementation**: `services/registry/`

**Agent Schema**:
```python
{
  "identity": "sales-agent-1",
  "version": "1.0.0",
  "capabilities": ["query_kb", "analyze_data"],
  "operations": ["query", "invoke", "subscribe"],
  "schemas": {
    "input": {"type": "object", "properties": {...}},
    "output": {"type": "object", "properties": {...}}
  },
  "health_endpoint": "http://localhost:8001/health",
  "status": "active",  # active | degraded | offline
  "metadata": {
    "team": "sales",
    "region": "us-west"
  }
}
```

**KB Schema**:
```python
{
  "kb_id": "sales-kb-1",
  "kb_type": "postgres",
  "endpoint": "postgresql://localhost:5432/agentmesh",
  "operations": ["sql_query", "insert", "update", "delete"],
  "kb_schema": {
    "tables": ["customers", "deals", "activities"],
    "sensitive_fields": ["email", "phone", "ssn"]
  },
  "credentials": {
    "username": "admin",  # Encrypted in persistence
    "password": "***"     # Never logged
  },
  "health_status": "active",
  "metadata": {
    "owner": "sales-team",
    "description": "Sales CRM database"
  }
}
```

**Operations**:
- `register_agent(config)` - Add new agent with validation
- `register_kb(config)` - Add new KB with connectivity check
- `list_agents(filter)` - Query agent directory
- `list_kbs(filter)` - Query KB directory
- `get_health_status(entity_id)` - Check health
- `update_agent_capabilities(identity, capabilities)` - Update agent

**Key Features**:
- **Validation**: Health endpoint checks during registration
- **Connectivity**: KB connection tests before acceptance
- **Background Monitoring**: Automatic health checks every 30s
- **Status Tracking**: Active → Degraded → Offline transitions

---

### 2.2 Policy Engine (OPA Integration)

**Purpose**: Store and evaluate access policies

**Implementation**: `adapters/policy/opa_client.py`, `services/enforcement/enforcement_service.py`

**Policy Structure** (Rego):
```rego
package agentmesh

# Allow marketing to query sales KB with masking
allow {
    input.principal == "marketing-agent-1"
    input.resource == "sales-kb-1"
    input.action == "query"
}

# Define field masks for marketing
field_masks[field] {
    input.principal == "marketing-agent-1"
    input.resource == "sales-kb-1"
    field := ["customer_email", "customer_phone", "ssn"]
}

# Deny marketing from writing
deny {
    input.principal == "marketing-agent-1"
    input.resource == "sales-kb-1"
    input.action == "write"
}
```

**Enforcement Flow**:
1. Request arrives: `(principal=marketing-agent-1, resource=sales-kb-1, action=query)`
2. Policy engine evaluates: `POST /v1/data/agentmesh/allow` to OPA
3. OPA returns: `{"result": {"allow": true, "field_masks": ["email", "phone"]}}`
4. If deny: Return error with reason
5. If allow: Extract masking rules and obligations
6. Execute KB query via NATS request-reply
7. Apply field masks to response
8. Log decision immutably

**Policy Management**:
- `upload_policy(policy_id, rego_content)` - Add/update policy
- `get_policy(policy_id)` - Retrieve policy
- `list_policies()` - List all policies
- `delete_policy(policy_id)` - Remove policy
- Policies auto-saved to disk for persistence

**Key Features**:
- **Deny-Overrides**: Deny rules take precedence over allow
- **Field-Level Masking**: Granular control over response fields
- **Policy Versioning**: Track which policy version was applied
- **Audit Integration**: Every decision logged

---

### 2.3 Response Interception & Masking

**Purpose**: Apply field-level masking BEFORE forwarding to requesters

**Implementation**: `services/enforcement/enforcement_service.py::apply_masking()`

**Algorithm**:
```python
def apply_masking(kb_response: dict, field_masks: list[str]) -> dict:
    """
    Recursively mask sensitive fields in KB response.

    Args:
        kb_response: Raw response from KB (unmasked)
        field_masks: List of field paths to mask (e.g., ["email", "phone"])

    Returns:
        Masked response with sensitive fields replaced by "***"
    """
    if isinstance(kb_response, dict):
        for key in kb_response:
            if key in field_masks:
                kb_response[key] = "***"  # Mask field
            else:
                kb_response[key] = apply_masking(kb_response[key], field_masks)

    elif isinstance(kb_response, list):
        return [apply_masking(item, field_masks) for item in kb_response]

    return kb_response
```

**Key Insight**:
- KBs return full data (they don't know about policies)
- Mesh masks sensitive fields based on requester's permissions
- No data leaks even if KB misbehaves

**Example**:
```python
# Raw KB Response
{
  "rows": [
    {"name": "Acme Corp", "email": "ceo@acme.com", "revenue": 5000000},
    {"name": "Beta Inc", "email": "cfo@beta.com", "revenue": 3000000}
  ]
}

# After Masking (field_masks=["email"])
{
  "rows": [
    {"name": "Acme Corp", "email": "***", "revenue": 5000000},
    {"name": "Beta Inc", "email": "***", "revenue": 3000000}
  ]
}
```

---

### 2.4 MCP Server & Auto-Tool Generation

**Purpose**: Expose KB operations as MCP tools automatically

**Implementation**: `mcp_server/server.py`

**Tool Generation Logic**:
```python
def generate_kb_tools(kb_config: dict) -> list[Tool]:
    """Generate MCP tools from KB adapter operations."""
    tools = []

    for operation in kb_config["operations"]:
        tool = Tool(
            name=f"{kb_config['kb_id']}_{operation}",
            description=f"Execute {operation} on {kb_config['kb_id']}",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "params": {"type": "object"}
                }
            }
        )
        tools.append(tool)

    return tools
```

**Generated Tools**:

**Registry Management (9 tools)**:
- `register_agent` - Register new agent
- `register_kb` - Register new knowledge base
- `list_agents` - List all registered agents
- `list_kbs` - List all registered KBs
- `get_agent_details` - Get agent information
- `get_kb_details` - Get KB information
- `check_health` - Check entity health
- `upload_policy` - Upload OPA policy
- `query_kb_governed` - Query KB with governance

**PostgreSQL Tools (4 tools)**:
- `postgres_sql_query` - Execute SQL query
- `postgres_insert` - Insert data
- `postgres_update` - Update data
- `postgres_delete` - Delete data

**Neo4j Tools (4 tools)**:
- `neo4j_cypher_query` - Execute Cypher query
- `neo4j_create_node` - Create node
- `neo4j_create_relationship` - Create relationship
- `neo4j_find_node` - Find nodes by properties

**Key Features**:
- **Dynamic Discovery**: Tools auto-generated from registered KBs
- **Schema Validation**: Input validation using JSON Schema
- **Datetime Serialization**: Proper handling of datetime fields
- **Error Handling**: Structured error responses

---

### 2.5 NATS Messaging Layer

**Purpose**: Enable real-time pub/sub and request-reply patterns

**Implementation**: `adapters/messaging/nats_client.py`

**NATS Subjects**:

| Subject | Pattern | Purpose |
|---------|---------|---------|
| `mesh.directory.updates` | Pub/Sub | Broadcast agent/KB registration events |
| `mesh.directory.query` | Request-Reply | Directory listing queries |
| `{kb_id}.adapter.query` | Request-Reply | KB query execution (message broker) |
| `agent.{agent_id}` | Request-Reply | Direct agent-to-agent messaging |

**Message Broker Pattern for KB Operations**:

```
User/Agent Query Request
    ↓
EnforcementService
    ↓ (1) Evaluate policy via OPA
    ↓ (2) Check access + get field masks
    ↓
NATS Request: {kb_id}.adapter.query
    ↓
KB Adapter (listens on subject)
    ↓ (3) Execute query against database
    ↓ (4) Return raw, unmasked data
    ↓
EnforcementService
    ↓ (5) Apply field masking
    ↓ (6) Log audit event
    ↓ (7) Return masked response
    ↓
User/Agent
```

**Key Architectural Principle**:
- **Authorization happens in mesh layer** (EnforcementService)
- **Masking happens in mesh layer** (EnforcementService)
- **KB Adapters only execute queries** (no governance logic)
- **All governance centralized** in mesh layer

**Message Formats**:

**Directory Update (Pub/Sub)**:
```json
{
  "type": "agent_registered",
  "timestamp": "2025-10-16T12:00:00Z",
  "data": {
    "identity": "analytics-agent-1",
    "version": "1.0.0",
    "capabilities": ["data_analysis", "query_kb"],
    "status": "active"
  }
}
```

**KB Query Request (Request-Reply)**:
```json
{
  "operation": "sql_query",
  "params": {
    "query": "SELECT * FROM customers WHERE region = $1",
    "params": {"region": "APAC"}
  }
}
```

**KB Query Response**:
```json
{
  "status": "success",
  "data": {
    "rows": [...],
    "row_count": 150
  }
}
```

---

## 3. Request Flow

### 3.1 Query Execution Flow (Governed KB Access)

```
1. User's LLM → MCP Tool: query_kb_governed({
     "requester_id": "marketing-agent-1",
     "kb_id": "sales-kb-1",
     "operation": "sql_query",
     "params": {"query": "SELECT * FROM customers"}
   })

2. MCP Server → EnforcementService: Forward request

3. EnforcementService → OPA: Evaluate policy
   Request: POST /v1/data/agentmesh/allow
   Body: {
     "input": {
       "principal": "marketing-agent-1",
       "resource": "sales-kb-1",
       "action": "query"
     }
   }

4. OPA → EnforcementService: Policy decision
   Response: {
     "result": {
       "allow": true,
       "field_masks": ["customer_email", "customer_phone"]
     }
   }

5. EnforcementService → NATS: Send KB query request
   Subject: sales-kb-1.adapter.query
   Message: {
     "operation": "sql_query",
     "params": {"query": "SELECT * FROM customers"}
   }

6. KB Adapter → PostgreSQL: Execute query
   SELECT * FROM customers

7. PostgreSQL → KB Adapter: Return full result set (unmasked)
   {
     "rows": [
       {"name": "Acme", "email": "ceo@acme.com", "phone": "+1234567890"}
     ]
   }

8. KB Adapter → NATS: Return response
   Subject: (reply subject)
   Message: {
     "status": "success",
     "data": {"rows": [...]}
   }

9. EnforcementService: Apply field masking
   mask_fields(response, ["customer_email", "customer_phone"])
   Result: {
     "rows": [
       {"name": "Acme", "email": "***", "phone": "***"}
     ]
   }

10. EnforcementService → Persistence: Log audit event
    AuditEvent(
      event_type="QUERY",
      source_id="marketing-agent-1",
      target_id="sales-kb-1",
      outcome="SUCCESS",
      masked_fields=["customer_email", "customer_phone"]
    )

11. EnforcementService → MCP Server: Return masked response

12. MCP Server → User's LLM: Deliver masked data
```

**Latency Breakdown** (Target):
- Policy lookup (OPA): <10ms (in-memory evaluation)
- NATS roundtrip: <5ms (local network)
- KB query execution: Variable (depends on KB and query complexity)
- Field masking: <5ms (recursive traversal)
- Audit logging: <10ms (async write to SQLite)
- **Total mesh overhead**: <30ms

---

### 3.2 Agent Registration Flow

```
1. User → Claude Desktop: "Register sales agent"

2. Claude → MCP Server: Use register_agent tool
   {
     "identity": "sales-agent-1",
     "version": "1.0.0",
     "capabilities": ["query_kb", "analyze_data"],
     "operations": ["query", "subscribe"],
     "health_endpoint": "http://localhost:8001/health"
   }

3. MCP Server → AgentService: register_agent(request)

4. AgentService → Validation:
   - Check identity uniqueness
   - Validate health endpoint (HTTP GET)
   - Validate capabilities format

5. AgentService → Persistence: Save agent registration
   INSERT INTO agents (identity, version, capabilities, ...)

6. AgentService → NATS: Publish registration event
   Subject: mesh.directory.updates
   Message: {
     "type": "agent_registered",
     "data": {"identity": "sales-agent-1", ...}
   }

7. NATS → All Subscribers: Broadcast notification
   (Connected agents receive update)

8. AgentService → HealthService: Start monitoring
   (Background health checks every 30s)

9. AgentService → MCP Server: Return response
   {
     "agent_id": "sales-agent-1",
     "status": "active",
     "message": "Agent registered successfully"
   }

10. MCP Server → Claude: Show success message
```

---

## 4. Policy Enforcement

### 4.1 Policy Evaluation Logic

**Implementation**: `services/enforcement/enforcement_service.py`

```python
async def evaluate_policy(
    self,
    principal: str,
    resource: str,
    action: str
) -> PolicyDecision:
    """
    Evaluate OPA policy for access decision.

    Args:
        principal: Requester identity (agent or user)
        resource: Target resource (kb_id or agent_id)
        action: Operation (query, write, invoke)

    Returns:
        PolicyDecision with allow/deny and masking rules
    """
    # 1. Build OPA input
    policy_input = {
        "input": {
            "principal": principal,
            "resource": resource,
            "action": action
        }
    }

    # 2. Evaluate allow rule
    allow_result = await opa_client.evaluate_policy(
        policy="agentmesh",
        rule="allow",
        input_data=policy_input
    )

    # 3. Check deny rule (deny overrides allow)
    deny_result = await opa_client.evaluate_policy(
        policy="agentmesh",
        rule="deny",
        input_data=policy_input
    )

    if deny_result.get("result", False):
        return PolicyDecision(
            allow=False,
            reason="Denied by policy",
            policy_version="v1.0"
        )

    if allow_result.get("result", False):
        # 4. Get field masks
        masks_result = await opa_client.evaluate_policy(
            policy="agentmesh",
            rule="field_masks",
            input_data=policy_input
        )

        return PolicyDecision(
            allow=True,
            field_masks=masks_result.get("result", []),
            policy_version="v1.0"
        )

    # 5. Default deny (no matching policy)
    return PolicyDecision(
        allow=False,
        reason="No matching policy found",
        policy_version="v1.0"
    )
```

### 4.2 OPA Policy Structure

**File**: `policies/agentmesh.rego`

```rego
package agentmesh

# Default deny
default allow = false
default deny = false

# Allow sales team to query their own KB
allow {
    input.principal == "sales-agent-1"
    input.resource == "sales-kb-1"
    input.action == "query"
}

# Allow marketing to query sales KB (with masking)
allow {
    input.principal == "marketing-agent-1"
    input.resource == "sales-kb-1"
    input.action == "query"
}

# Deny marketing from writing
deny {
    input.principal == "marketing-agent-1"
    input.resource == "sales-kb-1"
    input.action == "write"
}

# Field masking rules for marketing
field_masks[mask] {
    input.principal == "marketing-agent-1"
    input.resource == "sales-kb-1"
    mask := "customer_email"
}

field_masks[mask] {
    input.principal == "marketing-agent-1"
    input.resource == "sales-kb-1"
    mask := "customer_phone"
}

field_masks[mask] {
    input.principal == "marketing-agent-1"
    input.resource == "sales-kb-1"
    mask := "ssn"
}

# Admin has full access (no masking)
allow {
    input.principal == "admin"
}

field_masks[mask] {
    input.principal == "admin"
    # No masks for admin (empty set)
    false
}
```

---

## 5. Scalability Design

### 5.1 Horizontal Scaling

**Current Architecture** (Single Instance):
- SQLite persistence (file-based)
- Single MCP server instance
- Local NATS server

**Future Architecture** (Multi-Instance):
```
┌────────────────────────────────────────┐
│     Load Balancer / API Gateway        │
└───────────┬────────────────────────────┘
            │
    ┌───────┴───────┐
    │               │
┌───▼───┐       ┌───▼───┐
│ Mesh  │       │ Mesh  │  (Stateless instances)
│ Inst-1│       │ Inst-2│
└───┬───┘       └───┬───┘
    │               │
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │ NATS Cluster  │  (Distributed messaging)
    │ (3+ nodes)    │
    └───────┬───────┘
            │
    ┌───────▼───────┐
    │  PostgreSQL   │  (Shared persistence)
    │  + TimescaleDB│  (Time-series audit logs)
    └───────────────┘
```

**Key Scaling Strategies**:
1. **Stateless Router**: All context in requests, no session state
2. **Distributed Registry**: Redis cache for KB/agent registry (100ms TTL)
3. **Policy Cache**: In-memory OPA cache with invalidation events
4. **NATS Clustering**: Multi-node NATS for high availability
5. **Connection Pooling**: Shared connection pools to KBs

### 5.2 Performance Targets

| Metric | Target | Current | Measurement Method |
|--------|--------|---------|-------------------|
| Routing Overhead | P95 <100ms | ~30ms | Policy + masking + audit |
| Registry Lookup | P95 <10ms | ~5ms | In-memory cache |
| Concurrent Requests | 1000+ req/s | TBD | Load testing |
| KB Adapter Fanout | 5-10 KBs | Unlimited | Multi-source queries |
| Policy Evaluation | P95 <10ms | ~8ms | OPA benchmarks |
| NATS Latency | P95 <5ms | ~2ms | Request-reply roundtrip |

### 5.3 Optimization Strategies

**Current Optimizations**:
- Async/await throughout (Python asyncio)
- Connection pooling in adapters (asyncpg, Neo4j driver)
- In-memory policy evaluation (OPA)
- JSONB for extensible metadata (PostgreSQL-ready)

**Future Optimizations**:
- Redis cache for registry (warm cache on startup)
- Policy decision cache (TTL 60s, invalidate on policy update)
- Batch audit logging (write in chunks of 100 events)
- Response streaming for large result sets
- TimescaleDB for time-series audit queries

---

## 6. Security Model

### 6.1 Trust Boundaries

```
┌─────────────────────────────────────────────┐
│  Trusted Zone: Mesh Components              │
│  - Router (EnforcementService)              │
│  - Policy Engine (OPA)                      │
│  - Persistence Layer                        │
│  - Audit Store                              │
└────────────────┬────────────────────────────┘
                 │ Trust boundary
┌────────────────▼────────────────────────────┐
│  Semi-Trusted: KB Adapters                  │
│  - Apply optional pre-filtering             │
│  - Must return structured data              │
│  - Credentials managed by mesh              │
└────────────────┬────────────────────────────┘
                 │ Trust boundary
┌────────────────▼────────────────────────────┐
│  Untrusted: External KBs                    │
│  - May return sensitive data                │
│  - Mesh applies masking regardless          │
│  - No direct access to policies             │
└─────────────────────────────────────────────┘
```

### 6.2 Authentication & Authorization

**User Authentication** (via MCP):
- Claude Desktop handles user auth (OAuth2/OIDC)
- MCP server trusts Claude Desktop process
- Future: Token-based auth for external MCP clients

**Agent Authentication**:
- Token-based auth for agent connections
- Unique agent IDs assigned by mesh
- Private NATS subjects per agent

**KB Credentials**:
- Stored encrypted in persistence layer
- Never exposed in logs or audit trails
- Adapter-managed (not visible to mesh core)

### 6.3 Data Protection

**In Transit**:
- NATS TLS (future: enable TLS for production)
- MCP over secure stdio (process isolation)
- KB connections via native protocols (PostgreSQL SSL, Neo4j TLS)

**At Rest**:
- KB credentials encrypted (fernet)
- Audit logs contain metadata only (no PII)
- SQLite file permissions (0600)

**In Memory**:
- Response masking before forwarding
- No caching of sensitive data
- Policy cache contains rules only (no data)

---

## 7. Data Schemas

### 7.1 Metadata Store Schema (SQLite/PostgreSQL)

**Agents Table**:
```sql
CREATE TABLE agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity TEXT UNIQUE NOT NULL,
    version TEXT NOT NULL,
    capabilities TEXT NOT NULL,  -- JSON array
    operations TEXT NOT NULL,    -- JSON array
    schemas TEXT,                -- JSON object (nullable)
    health_endpoint TEXT NOT NULL,
    status TEXT DEFAULT 'active',  -- active | degraded | offline
    metadata TEXT,               -- JSON object (extensible)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_agents_identity ON agents(identity);
CREATE INDEX idx_agents_status ON agents(status);
```

**KBs Table**:
```sql
CREATE TABLE knowledge_bases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id TEXT UNIQUE NOT NULL,
    kb_type TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    operations TEXT NOT NULL,     -- JSON array
    kb_schema TEXT,               -- JSON object (nullable)
    credentials TEXT,             -- Encrypted JSON (nullable)
    health_status TEXT DEFAULT 'active',
    metadata TEXT,                -- JSON object (extensible)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_kbs_kb_id ON knowledge_bases(kb_id);
CREATE INDEX idx_kbs_type ON knowledge_bases(kb_type);
CREATE INDEX idx_kbs_status ON knowledge_bases(health_status);
```

**Policies Table**:
```sql
CREATE TABLE policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_name TEXT UNIQUE NOT NULL,
    rules TEXT NOT NULL,          -- JSON array of PolicyRule
    precedence INTEGER DEFAULT 100,
    active INTEGER DEFAULT 1,     -- Boolean (0 or 1)
    metadata TEXT,                -- JSON object (extensible)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_policies_name ON policies(policy_name);
CREATE INDEX idx_policies_active ON policies(active);
```

**Audit Logs Table**:
```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,     -- QUERY | INVOKE | REGISTER | POLICY_DECISION
    timestamp TEXT NOT NULL,
    source_id TEXT NOT NULL,      -- Agent or user ID
    target_id TEXT NOT NULL,      -- KB or agent ID
    outcome TEXT NOT NULL,        -- SUCCESS | DENIED | ERROR
    request_metadata TEXT,        -- JSON object (query params, etc.)
    response_metadata TEXT,       -- JSON object (row_count, etc.)
    masked_fields TEXT,           -- JSON array of field names
    policy_version TEXT,          -- Policy version applied
    latency_ms INTEGER,           -- Total latency
    error_message TEXT,           -- Error details (if failed)
    metadata TEXT                 -- JSON object (extensible)
);

CREATE INDEX idx_audit_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_source ON audit_logs(source_id);
CREATE INDEX idx_audit_target ON audit_logs(target_id);
CREATE INDEX idx_audit_outcome ON audit_logs(outcome);
```

**Schema Version** (Migrations):
```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);

INSERT INTO schema_version (version, applied_at, description)
VALUES (1, datetime('now'), 'Initial schema');
```

### 7.2 Extensibility via JSONB

**Metadata Column Design**:
- Lightweight by default (only essential fields)
- Extensible via `metadata` JSON column
- Future: Migrate to PostgreSQL JSONB for indexing

**Example Extensibility Paths**:

1. **Heavy Audit Logs** (store full request/response):
```json
{
  "metadata": {
    "full_request": "SELECT * FROM customers WHERE ...",
    "full_response_hash": "sha256:abc123...",
    "response_size_bytes": 15240,
    "s3_location": "s3://audit-logs/2025/10/16/req-123.json"
  }
}
```

2. **Advanced ABAC** (jurisdiction, purpose):
```json
{
  "metadata": {
    "jurisdiction": "EU",
    "purpose_of_use": "campaign_analysis",
    "data_classification": "PII-RESTRICTED",
    "compliance_tags": ["GDPR", "CCPA"]
  }
}
```

3. **Provenance Tracking**:
```json
{
  "metadata": {
    "provenance_chain": [
      {"agent": "sales-agent-1", "timestamp": "2025-10-16T10:00:00Z"},
      {"agent": "analytics-agent-2", "timestamp": "2025-10-16T10:05:00Z"}
    ]
  }
}
```

---

## 8. Extensibility Hooks

### 8.1 Planned Extensions (Not Implemented)

**1. Medium/Heavy Audit Logs**

*Current*: Lightweight logs (metadata only)

*Future*:
- Hook: `audit_logs.metadata` JSON column
- Implementation: Store full request/response in S3/MinIO
- Reference object storage location in metadata
- Enable compliance audits and replay

**2. Advanced ABAC Policies**

*Current*: RBAC with field-level masking

*Future*:
- Hook: Extend OPA policy conditions
- Add jurisdiction checks (EU data stays in EU)
- Add purpose-of-use enforcement (analytics vs operations)
- Time-based access (business hours only)

**3. Multi-KB Query Orchestration**

*Current*: Single KB per query

*Future*:
- Hook: `EnforcementService` fanout logic
- Query multiple KBs in parallel
- Merge/aggregate responses
- Apply per-KB policies independently

**4. Policy Simulation Mode**

*Current*: Policies active immediately

*Future*:
- Hook: Add `simulation_mode` flag to policy
- Shadow mode: evaluate but don't enforce
- Log "would have denied" for testing
- Activate after confidence threshold

**5. Break-Glass Override**

*Current*: Strict policy enforcement

*Future*:
- Hook: Add `override` permission with audit
- Emergency access with reason + approval
- Immutable break-glass audit log
- Automatic alert to security team

### 8.2 Custom Adapter Development

**Adapter Interface**:
```python
from adapters.knowledge_base.base import KBAdapter

class MyCustomAdapter(KBAdapter):
    async def connect(self) -> None:
        """Establish connection to KB."""
        pass

    async def disconnect(self) -> None:
        """Close connection."""
        pass

    async def health(self) -> dict:
        """Check KB health."""
        return {"status": "healthy"}

    async def execute(self, operation: str, **kwargs) -> dict:
        """Execute operation on KB."""
        if operation == "custom_query":
            return await self._custom_query(**kwargs)
        raise ValueError(f"Unsupported operation: {operation}")

    async def _custom_query(self, query: str) -> dict:
        """Custom query implementation."""
        # Your KB-specific logic here
        return {"data": [...]}
```

**Registration**:
```python
# Register in adapters/knowledge_base/registry.py
from adapters.knowledge_base.registry import OperationRegistry

registry = OperationRegistry()

@registry.register("custom_query")
async def custom_query_operation(adapter, query: str, **kwargs):
    return await adapter._custom_query(query)
```

---

## 9. Deployment Architecture

### 9.1 Development Deployment

```
Docker Compose Services:
- postgres (port 5432)
- neo4j (ports 7474, 7687)
- nats (ports 4222, 8222)
- opa (port 8181)

Local Processes:
- agentmesh-mcp (stdio, spawned by Claude)
- SQLite persistence (data/agentmesh.db)
```

### 9.2 Production Deployment (Future)

```
┌──────────────────────────────────────────┐
│  Kubernetes Cluster                       │
│                                           │
│  ┌────────────────────────────────────┐  │
│  │  MCP Server (Deployment)           │  │
│  │  - Replicas: 3                     │  │
│  │  - Service: LoadBalancer           │  │
│  └────────────────────────────────────┘  │
│                                           │
│  ┌────────────────────────────────────┐  │
│  │  NATS Cluster (StatefulSet)        │  │
│  │  - Replicas: 3                     │  │
│  │  - Persistent Volumes              │  │
│  └────────────────────────────────────┘  │
│                                           │
│  ┌────────────────────────────────────┐  │
│  │  OPA (Deployment)                  │  │
│  │  - Replicas: 2                     │  │
│  │  - ConfigMap for policies          │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘

External Services:
- PostgreSQL (RDS/Cloud SQL)
- Redis (ElastiCache/Memorystore)
- S3/MinIO (Audit log storage)
```

---

## 10. Trade-offs & Decisions

### 10.1 Query Translation vs Pass-Through

**Decision**: Pass-through (queries unchanged)

**Why**:
- Avoids semantic errors from translation
- Supports any query language (SQL, Cypher, custom)
- No mesh code changes for new KB types
- Users write queries in native KB language

**Trade-off**:
- Users must know target KB query language
- Can't optimize queries across KBs

### 10.2 Response Interception vs Query Rewriting

**Decision**: Response interception (mask after KB execution, but access control BEFORE)

**Why**:
- Access control happens BEFORE query (prevents unauthorized DB hits)
- Field masking happens AFTER KB returns data (for allowed requests)
- Ensures no data leaks (even if KB misbehaves)
- Avoids parsing every query language
- Simpler policy rules (field masks vs query rewriting)
- KB-agnostic enforcement

**Trade-off**:
- KB returns full data (network overhead for masked fields)
- Can't push-down filtering to KB

### 10.3 SQLite vs PostgreSQL for Persistence

**Decision**: SQLite (dev), PostgreSQL (prod)

**Why**:
- SQLite: Zero setup, file-based, perfect for dev
- PostgreSQL: JSONB indexing, TimescaleDB for time-series
- Easy migration path (same schema)

**Trade-off**:
- SQLite: Single-writer limit (not for high concurrency)
- PostgreSQL: Requires external deployment

### 10.4 Lightweight vs Heavy Audit Logs

**Decision**: Lightweight (metadata only) with extensibility

**Why**:
- Lightweight by default (fast writes, small storage)
- Extensible via JSON metadata column
- Can add heavy logging without schema migration

**Trade-off**:
- Compliance audits may need full request/response
- Future: Store full data in object storage

---

## Conclusion

AgentMesh's architecture prioritizes:
1. **Separation of concerns**: Intelligence in KBs/agents, governance in mesh
2. **Extensibility**: Lightweight now, scalable later
3. **Zero-copy**: No data duplication, only metadata
4. **Message broker pattern**: Authorization centralized, execution distributed
5. **Developer experience**: MCP protocol, auto-generated tools, real-time updates

This design enables secure, policy-driven access to distributed knowledge bases while maintaining flexibility for future enhancements.
