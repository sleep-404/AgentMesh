# Policy Persistence Update

## Summary

Enhanced the policy management system to automatically persist policies to disk, making them survive OPA restarts.

## What Changed

### 1. **OPA Client Enhancements** (`adapters/policy/opa_client.py`)

#### New Features:
- **Automatic persistence**: Policies uploaded via API are now saved to disk by default
- **File management**: Policies are saved as `.rego` files in the `policies/` directory
- **Policy content retrieval**: New `get_policy_content()` method for cleaner output

#### Updated Methods:
- `__init__()`: Added `policies_dir` parameter (default: "policies")
- `upload_policy()`: Added `persist` parameter (default: True)
  - Uploads to OPA
  - Saves to `policies/{policy_id}.rego` if `persist=True`
  - Returns file path and persistence status
- `delete_policy()`: Added `delete_file` parameter (default: True)
  - Deletes from OPA
  - Deletes file from disk if `delete_file=True`
  - Returns file deletion status

#### New Methods:
- `get_policy_content(policy_id)`: Returns just the Rego code content
  - Cleaner output than `get_policy()`
  - Returns: `{success, policy_id, content, size}`

### 2. **MCP Server Updates** (`mcp_server/server.py`)

#### New Tool:
- `get_policy_content`: Get just the policy content (raw Rego code)

#### Updated Tools:
- `upload_policy`:
  - Now includes `persist` parameter
  - Description updated to mention automatic persistence
  - Returns `file_path` and `persisted` status

- `delete_policy`:
  - Now includes `delete_file` parameter
  - Returns `file_deleted` status

### 3. **Testing & Examples**

#### New Test Script:
- `examples/test_policy_persistence.py`: Comprehensive test demonstrating:
  - Policy upload with persistence
  - File verification on disk
  - Content comparison (OPA vs disk)
  - Policy deletion (from both OPA and disk)
  - Persistence across OPA restarts

#### Test Results:
```
✅ Policy uploaded to OPA
✅ Policy saved to disk: policies/test_persistence.rego
✅ File content matches OPA content exactly
✅ Policy survives OPA restart
✅ Cleanup successful (file and OPA policy deleted)
```

### 4. **Documentation Updates**

#### Updated Files:
- `POLICY_MANAGEMENT.md`: Complete rewrite with:
  - Persistence details section
  - Updated tool descriptions
  - File management examples
  - Verification instructions
  - Important notes about persistence

## How It Works

```
┌─────────────────┐
│ User via MCP    │
└────────┬────────┘
         │ upload_policy(id, content, persist=True)
         ↓
┌─────────────────┐
│  OPA Client     │
├─────────────────┤
│ 1. Upload to    │─────→  OPA (memory)
│    OPA API      │
│                 │
│ 2. Save to disk │─────→  policies/my_policy.rego
│    (if persist) │
└─────────────────┘
         │
         ↓
  File persists on disk
         │
         ↓
  OPA restart loads from disk
```

## Before & After

### Before:
```python
# Upload policy
result = await opa.upload_policy("test", policy_content)
# ❌ Policy lost on OPA restart
```

### After:
```python
# Upload policy (automatically persisted)
result = await opa.upload_policy("test", policy_content, persist=True)
# ✅ Policy saved to policies/test.rego
# ✅ Policy survives OPA restart

# Response includes file info:
{
  "success": true,
  "message": "Policy 'test' uploaded successfully and saved to policies/test.rego",
  "policy_id": "test",
  "file_path": "policies/test.rego",
  "persisted": true
}
```

## File Structure

```
AgentMesh/
├── policies/
│   ├── agentmesh.rego          # Main policy (pre-existing)
│   ├── my_custom_policy.rego   # Uploaded via MCP (NEW)
│   └── test_policy.rego        # Uploaded via MCP (NEW)
├── adapters/policy/
│   └── opa_client.py           # Enhanced with persistence
├── mcp_server/
│   └── server.py               # Updated MCP tools
└── examples/
    └── test_policy_persistence.py  # New test script
```

## Benefits

1. **✅ Persistence**: Policies survive OPA container restarts
2. **✅ Version Control**: Policy files can be committed to git
3. **✅ Easy Backup**: Simple file-based backup of policies
4. **✅ Transparency**: See exactly what policies are configured
5. **✅ Verification**: Can diff file vs OPA content
6. **✅ Flexibility**: Can disable persistence with `persist=False`

## Backward Compatibility

- ✅ All existing code continues to work
- ✅ Default behavior now includes persistence (opt-out with `persist=False`)
- ✅ Existing policies in `policies/` directory still load on startup
- ✅ No breaking changes to API

## Testing

Run the test to verify persistence:
```bash
source .venv/bin/activate
python examples/test_policy_persistence.py
```

Expected output:
```
✅ Policy uploaded and saved to disk
✅ File exists on disk
✅ Contents match perfectly
✅ Policy survives OPA restart
✅ Cleanup successful
```

## Use Cases

### Production Deployment:
```python
# Upload a production policy (persisted automatically)
await opa.upload_policy("production_rules", policy_content)
# Policy file committed to git
# Deployed across environments
```

### Temporary Testing:
```python
# Test a policy without persistence
await opa.upload_policy("temp_test", policy_content, persist=False)
# Policy only in OPA memory, not saved to disk
```

### Policy Updates:
```python
# Update existing policy (overwrites file)
await opa.upload_policy("my_policy", updated_content)
# File automatically updated
# OPA reloaded with new policy
```

## Impact

This enhancement makes AgentMesh policy management production-ready by ensuring:
- **Durability**: Policies don't disappear on restart
- **Auditability**: Clear file-based record of all policies
- **Simplicity**: Works automatically, no extra steps needed
- **Safety**: Can version control policies like any other code

## Next Steps (Optional)

Future enhancements could include:
- Policy versioning (keep history of changes)
- Policy validation before upload
- Policy diffing tool
- Policy templates
- Bulk policy operations
