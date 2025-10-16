#!/usr/bin/env python3
"""
Quick verification script for policy management functionality.

This script demonstrates that OPA policy management is working through:
1. Checking OPA availability
2. Uploading a test policy
3. Verifying it was uploaded
4. Cleaning up

Run this script to verify the feature is working correctly.
"""

import asyncio
import sys

from adapters.policy.opa_client import OPAClient


async def main():
    """Verify policy management functionality."""
    print("🔍 AgentMesh Policy Management Verification")
    print("=" * 60)

    # Initialize OPA client
    opa_client = OPAClient(url="http://localhost:8181")
    all_passed = True

    try:
        # Test 1: Health Check
        print("\n✓ Test 1: Checking OPA health...")
        is_healthy = await opa_client.health_check()
        if not is_healthy:
            print("  ❌ OPA is not available at http://localhost:8181")
            print("  Please start OPA: docker-compose up -d opa")
            return False
        print("  ✅ OPA is healthy and responding")

        # Test 2: List Policies
        print("\n✓ Test 2: Listing current policies...")
        policies = await opa_client.list_policies()
        policy_ids = list(policies.get("result", {}).keys())
        print(f"  ✅ Found {len(policy_ids)} policies: {policy_ids}")

        # Test 3: Upload a Test Policy
        print("\n✓ Test 3: Uploading test policy...")
        test_policy = """package test_verification

default allow = false

# Simple rule for verification
allow {
    input.action == "verify"
    input.principal_id == "test-agent"
}

decision = {
    "allow": allow,
    "masking_rules": [],
    "reason": reason
}

reason = r {
    allow
    r := "Verification test passed"
}

reason = r {
    not allow
    r := "Verification test failed"
}
"""
        upload_result = await opa_client.upload_policy("test_verification", test_policy)
        if not upload_result.get("success"):
            print(f"  ❌ Failed to upload policy: {upload_result.get('error')}")
            all_passed = False
        else:
            print("  ✅ Policy uploaded successfully")

            # Test 4: Verify Policy Exists
            print("\n✓ Test 4: Verifying policy was uploaded...")
            get_result = await opa_client.get_policy("test_verification")
            if "error" in get_result:
                print(f"  ❌ Failed to retrieve policy: {get_result['error']}")
                all_passed = False
            else:
                print("  ✅ Policy retrieved successfully")

            # Test 5: List Policies Again
            print("\n✓ Test 5: Confirming policy appears in list...")
            policies = await opa_client.list_policies()
            policy_ids = list(policies.get("result", {}).keys())
            if "test_verification" in policy_ids:
                print(f"  ✅ Policy confirmed in list: {policy_ids}")
            else:
                print(f"  ❌ Policy not found in list: {policy_ids}")
                all_passed = False

            # Test 6: Delete the Test Policy
            print("\n✓ Test 6: Cleaning up test policy...")
            delete_result = await opa_client.delete_policy("test_verification")
            if not delete_result.get("success"):
                print(f"  ⚠️  Failed to delete policy: {delete_result.get('error')}")
                print("  (This is okay - policy can be deleted manually)")
            else:
                print("  ✅ Policy deleted successfully")

        print("\n" + "=" * 60)
        if all_passed:
            print("✅ ALL TESTS PASSED - Policy management is working!")
            print("\nYou can now use the following MCP tools:")
            print("  - list_policies")
            print("  - get_policy")
            print("  - upload_policy")
            print("  - delete_policy")
            print("\nSee POLICY_MANAGEMENT.md for detailed usage.")
            return True
        else:
            print("⚠️  SOME TESTS FAILED - Check the output above")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        await opa_client.close()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
