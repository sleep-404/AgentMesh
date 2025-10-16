# Policy Management Guide

This guide shows how to manage OPA policies through the AgentMesh MCP interface.

## Overview

AgentMesh now supports dynamic policy management through MCP tools with **automatic persistence**. You can:
- List all loaded policies
- Upload new policies or update existing ones (automatically saved to disk)
- Retrieve specific policy content
- Delete policies (from both OPA and disk)

**Key Feature:** All policies uploaded via MCP are automatically saved to the `policies/` directory, ensuring they persist across OPA restarts!

## Available MCP Tools

### 1. `list_policies`
List all policies currently loaded in OPA.

**Parameters:** None

**Example Response:**
```json
{
  "result": [
    {
      "id": "agentmesh",
      "raw": "package agentmesh\n..."
    }
  ]
}
```

### 2. `get_policy`
Retrieve a specific policy by ID (full metadata).

**Parameters:**
- `policy_id` (string, required): Policy identifier

**Example:**
```json
{
  "policy_id": "agentmesh"
}
```

### 3. `get_policy_content`
Get just the policy content (raw Rego code) - cleaner output for reading policies.

**Parameters:**
- `policy_id` (string, required): Policy identifier

**Example Response:**
```json
{
  "success": true,
  "policy_id": "test_policy",
  "content": "package test_policy\n\ndefault allow := false\n...",
  "size": 234
}
```

### 4. `upload_policy`
Upload a new policy or update an existing one. **Automatically saves to disk for persistence!**

**Parameters:**
- `policy_id` (string, required): Unique policy identifier
- `policy_content` (string, required): Rego policy content
- `persist` (boolean, optional): Save to disk (default: true)

**Example:**
```json
{
  "policy_id": "my_custom_policy",
  "policy_content": "package my_custom_policy\n\ndefault allow := false\n\nallow if {\n    input.action == \"read\"\n}",
  "persist": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Policy 'my_custom_policy' uploaded successfully and saved to policies/my_custom_policy.rego",
  "policy_id": "my_custom_policy",
  "file_path": "policies/my_custom_policy.rego",
  "persisted": true
}
```

### 5. `delete_policy`
Delete a policy from OPA and optionally from disk.

**Parameters:**
- `policy_id` (string, required): Policy identifier to delete
- `delete_file` (boolean, optional): Also delete file from disk (default: true)

**Example:**
```json
{
  "policy_id": "my_custom_policy",
  "delete_file": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Policy 'my_custom_policy' deleted successfully (including file)",
  "file_deleted": true
}
```

## Example Policy

Here's a simple example policy you can upload:

```rego
package custom_example

# Default deny
default allow = false

# Allow read operations for all agents
allow {
    input.action == "read"
    input.principal_type == "agent"
}

# Allow write operations only for specific agents
allow {
    input.action == "write"
    input.principal_type == "agent"
    input.principal_id in ["trusted-agent-1", "admin-agent"]
}

# Decision structure
decision = {
    "allow": allow,
    "masking_rules": [],
    "reason": reason
}

reason = r {
    allow
    r := "Access granted"
}

reason = r {
    not allow
    r := "Access denied"
}
```

## Usage via MCP

When using the AgentMesh MCP server in Cursor or other MCP clients, you can:

1. **List policies:**
   ```
   Use the list_policies tool
   ```

2. **Upload a policy:**
   ```
   Use the upload_policy tool with:
   - policy_id: "my_policy"
   - policy_content: "<your rego code here>"
   ```

3. **Get policy details:**
   ```
   Use the get_policy tool with policy_id: "my_policy"
   ```

4. **Delete a policy:**
   ```
   Use the delete_policy tool with policy_id: "my_policy"
   ```

## Testing

### Basic Policy Management
Run the example script to test policy management:

```bash
source .venv/bin/activate
python examples/policy_management_example.py
```

### Policy Persistence
Test that policies are saved to disk and survive restarts:

```bash
source .venv/bin/activate
python examples/test_policy_persistence.py
```

This test will:
1. Upload a policy (automatically saved to `policies/test_persistence.rego`)
2. Verify the file was created on disk
3. Compare file content with OPA content
4. Delete the policy (removes both from OPA and disk)

**Prerequisites:**
- OPA server must be running (default: http://localhost:8181)
- You can start OPA using: `docker-compose up -d opa`

## Policy Structure

AgentMesh policies should follow this structure:

```rego
package <your_package_name>

# Your policy rules here
default allow = false

allow {
    # conditions
}

# Return decision
decision = {
    "allow": allow,
    "masking_rules": masking_rules,
    "reason": reason
}
```

The `agentmesh.decision` endpoint expects policies to return:
- `allow` (boolean): Whether access is granted
- `masking_rules` (array): List of fields to mask in the response
- `reason` (string): Explanation for the decision

## Persistence Details

### How It Works

When you upload a policy via MCP:
1. **Policy is uploaded to OPA** (available immediately)
2. **Policy is saved to `policies/{policy_id}.rego`** (persists across restarts)
3. **File is automatically loaded** when OPA starts via docker-compose volume mount

### File Location

```
/Users/jeevan/AgentMesh/policies/
  ├── agentmesh.rego           # Main policy (pre-existing)
  └── my_custom_policy.rego    # Your uploaded policies
```

### Verification

To verify a policy was saved:
```bash
# Check if file exists
ls -lh policies/my_custom_policy.rego

# View the policy
cat policies/my_custom_policy.rego

# Test persistence by restarting OPA
docker-compose restart opa

# Policy should still be loaded
curl http://localhost:8181/v1/policies/my_custom_policy
```

## Important Notes

- ✅ **Policies are now persistent** - They survive OPA container restarts
- ✅ **Automatic file management** - Upload saves to disk, delete removes from disk
- ⚠️ **Policy IDs should be unique** - Uploading with existing ID will overwrite
- ⚠️ **Be careful with `agentmesh` policy** - It controls all mesh access
- 📁 **Files are in `policies/` directory** - Mounted as read-only volume in OPA container
- 🔄 **Set `persist: false`** if you want temporary policies (memory only)
