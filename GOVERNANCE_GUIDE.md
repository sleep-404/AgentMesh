# AgentMesh Governance Guide

This guide explains how AgentMesh implements governance using OPA (Open Policy Agent) as a sidecar.

## Architecture Overview

AgentMesh provides a governed infrastructure for AI agents with three key layers:

```
┌─────────────────────────────────────────────────┐
│             Agent Applications                   │
│    (Sales Agent, Marketing Agent, etc.)         │
└────────────────┬────────────────────────────────┘
                 │
        ┌────────▼─────────┐
        │  Request Router  │  ◄──── Orchestrates all requests
        │  (Mesh Gateway)  │
        └────────┬─────────┘
                 │
        ┌────────▼──────────┐
        │ Enforcement       │  ◄──── Evaluates policies, masks data
        │ Service           │
        └─┬────────────────┬┘
          │                │
    ┌─────▼─────┐    ┌────▼────┐
    │    OPA    │    │   KBs   │
    │ (Policies)│    │ (Data)  │
    └───────────┘    └─────────┘
```

### Key Components

1. **OPA (Open Policy Agent)**: External policy engine running as a sidecar container
2. **Enforcement Service**: Combines policy evaluation with KB access and data masking
3. **Request Router**: Orchestrates requests through the governance layer
4. **NATS**: Message transport for agent communication

## OPA Integration

### Why OPA as a Sidecar?

- **Separation of Concerns**: Policy logic is decoupled from application code
- **Language Agnostic**: Policies written in Rego, not Python
- **Standard Compliance**: Uses industry-standard policy framework
- **Centralized Management**: Single source of truth for policies
- **Hot Reload**: Policies can be updated without restarting the mesh

### OPA Container Configuration

The OPA container is defined in `docker-compose.yml`:

```yaml
opa:
  image: openpolicyagent/opa:latest
  container_name: agentmesh-opa
  ports:
    - "8181:8181"
  command:
    - "run"
    - "--server"
    - "--log-level=info"
    - "/policies"
  volumes:
    - ./policies:/policies:ro
  healthcheck:
    test: ["CMD", "wget", "--spider", "-q", "http://localhost:8181/health"]
```

### Policy Files

Policies are stored in the `policies/` directory and mounted as read-only:

- `agentmesh.rego`: Main policy file with access control and masking rules

## Policy Structure

### KB Access Policies

Control which agents can access which knowledge bases:

```rego
# Allow sales agents to read from sales KB
allow_kb_access if {
    input.principal_type == "agent"
    startswith(input.principal_id, "sales-agent-")
    input.resource_type == "kb"
    input.resource_id == "sales-kb-1"
    input.action in ["read", "query", "sql_query"]
}
```

### Agent Invocation Policies

Control agent-to-agent communication:

```rego
# Allow sales agents to invoke engineering agents
allow_agent_invoke if {
    input.principal_type == "agent"
    startswith(input.principal_id, "sales-agent-")
    input.resource_type == "agent"
    startswith(input.resource_id, "engineering-agent-")
    input.action == "invoke"
}
```

### Field-Level Masking

Define which fields should be masked based on the requester:

```rego
# Marketing agents see heavily masked data
masking_rules = rules if {
    startswith(input.principal_id, "marketing-agent-")
    input.resource_id == "sales-kb-1"
    rules := ["customer_email", "customer_phone", "ssn", "credit_card"]
}

# Sales agents see less masked data
masking_rules = rules if {
    startswith(input.principal_id, "sales-agent-")
    input.resource_id == "sales-kb-1"
    rules := ["ssn", "credit_card"]
}
```

## Request Flow

### KB Query Flow

1. **Agent Request**: Agent calls `query_kb_governed` with requester_id, kb_id, operation, params
2. **Router**: Request Router receives the request
3. **Policy Evaluation**: Enforcement Service calls OPA to evaluate policy
4. **Access Check**: OPA returns `allow`, `masking_rules`, and `reason`
5. **Execution**: If allowed, Enforcement Service executes query on KB
6. **Masking**: Response is masked according to policy rules
7. **Audit**: Event is logged to audit trail
8. **Response**: Masked response returned to agent

Example:

```python
request = KBQueryRequest(
    requester_id="marketing-agent-2",
    kb_id="sales-kb-1",
    operation="sql_query",
    params={"query": "SELECT * FROM customers LIMIT 1"}
)

response = await router.route_kb_query(request)
# response.status = "success"
# response.masked_fields = ["customer_email", "customer_phone", "ssn", "credit_card"]
# response.data = {"name": "John Doe", "customer_email": "[REDACTED]", ...}
```

### Agent Invocation Flow

1. **Source Agent**: Calls `invoke_agent_governed`
2. **Router**: Request Router receives invocation request
3. **Policy Evaluation**: Enforcement Service checks with OPA
4. **Authorization**: If allowed, tracking ID is assigned
5. **Forwarding**: Request forwarded to target agent via NATS
6. **Tracking**: Invocation tracked with status updates
7. **Completion**: Target agent notifies mesh on completion
8. **Notification**: Source agent notified of result

## Testing the Governance Layer

### 1. Start Infrastructure

```bash
# Start all services including OPA
bash scripts/start_mesh_with_opa.sh
```

### 2. Setup Demo Data

```bash
python examples/setup_demo_data.py
```

### 3. Run Governance Demo

```bash
python examples/test_routing_with_opa.py
```

This will demonstrate:
- ✅ Sales agent accessing sales KB (allowed, minimal masking)
- ✅ Marketing agent accessing sales KB (allowed, heavy masking)
- ❌ Engineering agent accessing sales KB (denied)
- ✅ Engineering agent accessing engineering KB (allowed)

### 4. Test OPA Directly

```bash
# Test policy evaluation
curl -X POST http://localhost:8181/v1/data/agentmesh/decision \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "principal_type": "agent",
      "principal_id": "sales-agent-1",
      "resource_type": "kb",
      "resource_id": "sales-kb-1",
      "action": "query"
    }
  }'
```

## Policy Management

### Updating Policies

1. Edit `policies/agentmesh.rego`
2. OPA automatically reloads policies (hot reload)
3. Test new policies with curl or demo script

### Adding New Policies

Create new `.rego` files in the `policies/` directory:

```rego
package agentmesh

# New policy rules here
```

### Policy Testing

Use OPA's test framework:

```bash
# Run in OPA container
docker exec -it agentmesh-opa opa test /policies
```

## Audit Trail

All governed operations are logged:

```python
from adapters.persistence.schemas import AuditQuery

logs = await persistence.query_audit_logs(
    AuditQuery(limit=10, source_id="sales-agent-1")
)

for log in logs:
    print(f"{log.timestamp}: {log.event_type} → {log.target_id}: {log.outcome}")
    if log.masked_fields:
        print(f"  Masked: {log.masked_fields}")
```

## MCP Tools for Governance

The MCP server exposes governance tools:

### `query_kb_governed`

Query a KB through the governance layer:

```json
{
  "name": "query_kb_governed",
  "arguments": {
    "requester_id": "sales-agent-1",
    "kb_id": "sales-kb-1",
    "operation": "sql_query",
    "params": {"query": "SELECT * FROM customers"}
  }
}
```

### `invoke_agent_governed`

Invoke an agent through the governance layer:

```json
{
  "name": "invoke_agent_governed",
  "arguments": {
    "source_agent_id": "sales-agent-1",
    "target_agent_id": "engineering-agent-3",
    "operation": "prioritize_feature",
    "payload": {"feature": "Feature X"}
  }
}
```

### `get_invocation_status`

Check status of an invocation:

```json
{
  "name": "get_invocation_status",
  "arguments": {
    "tracking_id": "123e4567-e89b-12d3-a456-426614174000"
  }
}
```

## Security Considerations

1. **Default Deny**: All requests are denied unless explicitly allowed by policy
2. **Field Masking**: Sensitive fields are redacted before returning to agents
3. **Audit Logging**: All operations logged with full context
4. **Policy Isolation**: Policies run in separate OPA container
5. **Read-Only Policies**: Policy files mounted read-only in container

## Troubleshooting

### OPA Not Responding

```bash
# Check OPA health
curl http://localhost:8181/health

# View OPA logs
docker logs agentmesh-opa

# Restart OPA
docker-compose restart opa
```

### Policy Evaluation Fails

```bash
# Check policy syntax
docker exec -it agentmesh-opa opa check /policies

# View loaded policies
curl http://localhost:8181/v1/policies
```

### Requests Denied

1. Check OPA decision directly (curl command above)
2. Review policy rules in `policies/agentmesh.rego`
3. Check audit logs for deny reason
4. Verify agent/KB IDs match policy patterns

## Advanced Usage

### Custom Policy Conditions

Add time-based or context-based policies:

```rego
# Only allow queries during business hours
allow_kb_access if {
    # ... other conditions ...
    is_business_hours(input.context.timestamp)
}

is_business_hours(ts) {
    hour := time.clock([ts])[0]
    hour >= 9
    hour < 17
}
```

### Dynamic Masking

Adjust masking based on data sensitivity:

```rego
# Mask more fields for PII data
masking_rules = rules if {
    input.params.query contains "customers"
    rules := ["email", "phone", "ssn", "credit_card", "address"]
}
```

## Summary

The OPA integration provides:

- ✅ **Centralized policy management**
- ✅ **Fine-grained access control**
- ✅ **Field-level data masking**
- ✅ **Complete audit trail**
- ✅ **Hot-reloadable policies**
- ✅ **Standard-based governance**

All without modifying agent code or KB adapters!
