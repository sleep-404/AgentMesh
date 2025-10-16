"""
Example demonstrating OPA policy management through MCP tools.

This example shows how to:
1. List current policies
2. Upload a new custom policy
3. Retrieve a specific policy
4. Delete a policy

Note: This requires the MCP server to be running with OPA available.
"""

import asyncio

from adapters.policy.opa_client import OPAClient


async def main():
    """Demonstrate policy management operations."""
    # Initialize OPA client
    opa_client = OPAClient(url="http://localhost:8181")

    print("=" * 60)
    print("OPA Policy Management Example")
    print("=" * 60)

    # 1. Check OPA health
    print("\n1. Checking OPA health...")
    is_healthy = await opa_client.health_check()
    if not is_healthy:
        print("❌ OPA is not available. Please start OPA server first.")
        return
    print("✅ OPA is healthy and ready")

    # 2. List current policies
    print("\n2. Listing current policies...")
    policies = await opa_client.list_policies()
    print(f"Current policies: {list(policies.get('result', {}).keys())}")

    # 3. Upload a custom policy
    print("\n3. Uploading custom policy...")
    custom_policy = """
package custom_example

default allow = false

# Allow all read operations
allow {
    input.action == "read"
}

# Deny all write operations
allow {
    input.action == "write"
    input.principal_id == "admin"
}
"""

    result = await opa_client.upload_policy("custom_example", custom_policy)
    if result.get("success"):
        print(f"✅ {result['message']}")
    else:
        print(f"❌ Failed to upload policy: {result.get('error')}")

    # 4. List policies again to confirm
    print("\n4. Listing policies after upload...")
    policies = await opa_client.list_policies()
    print(f"Current policies: {list(policies.get('result', {}).keys())}")

    # 5. Get specific policy
    print("\n5. Retrieving custom policy...")
    policy_detail = await opa_client.get_policy("custom_example")
    if "error" not in policy_detail:
        print("✅ Policy retrieved successfully")
        print(
            f"Policy content preview: {str(policy_detail.get('result', {}).get('raw', ''))[:200]}..."
        )
    else:
        print(f"❌ {policy_detail['error']}")

    # 6. Delete custom policy (cleanup)
    print("\n6. Deleting custom policy (cleanup)...")
    result = await opa_client.delete_policy("custom_example")
    if result.get("success"):
        print(f"✅ {result['message']}")
    else:
        print(f"❌ {result.get('error')}")

    # 7. Verify deletion
    print("\n7. Verifying deletion...")
    policies = await opa_client.list_policies()
    print(f"Current policies: {list(policies.get('result', {}).keys())}")

    print("\n" + "=" * 60)
    print("Policy management example completed!")
    print("=" * 60)

    # Cleanup
    await opa_client.close()


if __name__ == "__main__":
    asyncio.run(main())
