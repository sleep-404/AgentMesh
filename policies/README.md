# AgentMesh OPA Policies

This directory contains Open Policy Agent (OPA) policies for AgentMesh governance.

## Policy Structure

### Main Policy: `agentmesh.rego`

The main policy file contains rules for:

1. **KB Access Control**: Determines which agents can access which knowledge bases
2. **Agent Invocation**: Controls agent-to-agent communication
3. **Field-Level Masking**: Specifies which fields should be masked for different requesters

## Simple Policy Rules (Current Implementation)

### KB Access

- **Sales Agents** → Read access to `sales-kb-1` (masks SSN, credit card)
- **Marketing Agents** → Read access to `sales-kb-1` (masks email, phone, SSN, credit card)
- **Engineering Agents** → Read access to `engineering-kb-1`
- **Admin Agents** → Full access to all KBs (no masking)

### Agent Invocation

- **Sales Agents** → Can invoke Engineering Agents
- **Engineering Agents** → Can invoke Marketing Agents
- **Marketing Agents** → Can invoke Sales Agents
- **Admin Agents** → Can invoke any agent

## Testing Policies

You can test policies using OPA's CLI:

```bash
# Test KB access for marketing agent
curl -X POST http://localhost:8181/v1/data/agentmesh/decision \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "principal_type": "agent",
      "principal_id": "marketing-agent-1",
      "resource_type": "kb",
      "resource_id": "sales-kb-1",
      "action": "query"
    }
  }'

# Test agent invocation
curl -X POST http://localhost:8181/v1/data/agentmesh/decision \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "principal_type": "agent",
      "principal_id": "sales-agent-1",
      "resource_type": "agent",
      "resource_id": "engineering-agent-3",
      "action": "invoke"
    }
  }'
```

## Policy Extension

### Option 1: Dynamic Policy Management (Recommended)

AgentMesh now supports dynamic policy management through MCP tools:

```python
# Using the OPA client directly
from adapters.policy.opa_client import OPAClient

opa_client = OPAClient()

# Upload a new policy
policy_content = """
package my_custom_policy

default allow = false

allow {
    input.action == "read"
}
"""

result = await opa_client.upload_policy("my_custom_policy", policy_content)

# List all policies
policies = await opa_client.list_policies()

# Get a specific policy
policy = await opa_client.get_policy("my_custom_policy")

# Delete a policy
result = await opa_client.delete_policy("my_custom_policy")
```

See `POLICY_MANAGEMENT.md` in the root directory for full documentation.

### Option 2: Static Policy Files

To add static policies:

1. Create a new `.rego` file in this directory
2. Use the `package agentmesh` declaration
3. Define your rules following OPA syntax
4. Restart the OPA container to load new policies

## Policy Decision Response

Expected response format:

```json
{
  "result": {
    "allow": true,
    "masking_rules": ["customer_email", "customer_phone"],
    "reason": "Policy allows KB access"
  }
}
```
