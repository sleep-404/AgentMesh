# Design Rationale & Problem-Solving Approach

## The Core Insight: Infrastructure, Not Intelligence

When I first approached the AgentMesh challenge, I recognized a critical distinction: **the mesh shouldn't be a knowledge store—it's an orchestration layer**. Organizations already have knowledge in their databases; duplicating it creates data consistency nightmares and storage overhead.

My approach centered on three core principles:

### 1. Zero-Copy Governance

Rather than storing organizational knowledge, the mesh maintains only metadata (agent/KB registry, audit logs, policies). Knowledge lives in KBs where it belongs. The mesh enforces governance via a two-phase approach: **access control first** (OPA evaluates before query execution), then **response interception** (masking sensitive fields after KBs return data but before delivery to requesters). This ensures no unauthorized queries hit the database, and no data leaks even if a KB misbehaves or returns more data than allowed.

### 2. KB-Agnostic Routing

I rejected query translation (SQL → unified format → Cypher) because it introduces semantic errors and limits KB capabilities. Instead, the mesh **forwards queries unchanged** to KB adapters, which handle native protocols (SQL, Cypher, REST). This enables universal KB support without mesh code changes when adding new KB types. Users write queries in their preferred language, and the mesh routes them directly.

### 3. Bring-Your-Own-Reasoning

Users connect their own LLMs via the Model Context Protocol (MCP). The mesh provides auto-generated tools for querying and invocation, but **contradiction detection and synthesis happen in user reasoning systems**—not the mesh. When a CPO queries both Sales and Engineering KBs about feature timelines, the mesh provides governed access to both. The user's LLM detects the contradiction ("Sales says Q1, Engineering says Q3"). This preserves autonomy and prevents vendor lock-in.

## Key Trade-offs

### Lightweight Now, Extensible Later

I designed extensible metadata schemas (JSONB columns) that start simple (event type, timestamp, outcome) but can grow to heavy audit logs (full request/response in S3) without database migrations. This enables rapid development while preserving future scalability.

**Example extensibility**:
- Current: `{"event_type": "QUERY", "outcome": "SUCCESS", "masked_fields": ["email"]}`
- Future: Add `{"full_request_s3": "s3://audit/req-123.json", "compliance_tags": ["GDPR"]}`

### Out-of-Box Features

Direct database access for metadata queries leverages SQLite/PostgreSQL's native capabilities instead of custom API code. Want to know "which agents queried sales-kb-1 in the last 24 hours?" Just run SQL against the audit_logs table. This reduces development overhead and provides familiar interfaces for users.

### Policy Enforcement Point

Policy evaluation happens BEFORE query execution, while response masking happens AFTER. This two-phase approach (authorize first, mask second) avoids parsing every query language and ensures no data leaks. The mesh doesn't need to understand SQL vs Cypher—it just evaluates access then masks the response according to policy. This makes the system KB-agnostic and secure by default.

**Flow**:
1. Agent sends query → Mesh checks policy (OPA) → Allow/Deny with masking rules
2. If denied: Return error (KB never queried)
3. If allowed: Mesh forwards query to KB (unchanged)
4. KB returns full data (doesn't know about policies)
5. Mesh applies field masks to response
6. Mesh returns masked data to requester

### Message Broker Pattern

Using NATS for KB operations implements the correct mesh architecture: **authorization happens in the mesh layer**, execution happens in adapters. The EnforcementService evaluates policies via OPA, sends authorized requests to KB adapters via NATS, receives raw data, applies masking, and logs the audit event. KB adapters are simple data access components with no governance logic—this centralizes security and makes the system easier to audit.

## What I'd Add With More Time

**Policy Simulation Mode**: Test rules in shadow mode before activation. The mesh would log "would have denied" for testing without impacting users.

**Multi-Region Federation**: Governed cross-boundary analytics with data residency rules. EU agents can query US KBs, but the mesh enforces "EU data stays in EU" via OPA policies.

**Advanced Health Inference**: Use traffic patterns to predict KB degradation. If query latency spikes or error rates increase, proactively mark KB as degraded before it fails.

**Break-Glass Override**: Emergency access with immutable audit trail. When an incident requires bypassing policies, the mesh logs who, when, why, and automatically alerts security teams.

## The Result

The mesh is infrastructure—routing, governing, observing—while intelligence remains in agents, KBs, and user reasoning systems. This separation of concerns enables flexibility, security, and scalability without constraining how users think about their data or build their agents.
