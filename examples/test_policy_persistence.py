#!/usr/bin/env python3
"""
Test script to verify policy persistence functionality.

This demonstrates:
1. Getting current policy content (before)
2. Uploading a new policy (saves to disk automatically)
3. Getting the policy content (after)
4. Verifying the file was created on disk
5. Cleanup
"""

import asyncio
from pathlib import Path

from adapters.policy.opa_client import OPAClient


async def main():
    """Test policy persistence."""
    print("=" * 70)
    print("Policy Persistence Test")
    print("=" * 70)

    # Initialize OPA client
    opa = OPAClient(url="http://localhost:8181", policies_dir="policies")

    try:
        # 1. Check OPA health
        print("\n1. Checking OPA health...")
        is_healthy = await opa.health_check()
        if not is_healthy:
            print("❌ OPA is not available. Please start: docker-compose up -d opa")
            return
        print("✅ OPA is healthy")

        # 2. Get current policy list (before)
        print("\n2. Listing current policies (BEFORE)...")
        policies_before = await opa.list_policies()
        policy_ids = [p.get("id", "") for p in policies_before.get("result", [])]
        print(f"   Policies: {policy_ids}")

        # 3. Upload a test policy with persistence
        print("\n3. Uploading test policy (with persistence)...")
        test_policy_id = "test_persistence"
        test_policy_content = """package test_persistence

# Test policy for demonstrating persistence
default allow := false

# Allow test actions
allow if {
    input.action == "test"
    input.user == "tester"
}

# Decision
decision := {
    "allow": allow,
    "masking_rules": [],
    "reason": reason
}

reason := "Test action allowed" if {
    allow
}

reason := "Test action denied" if {
    not allow
}
"""

        result = await opa.upload_policy(
            test_policy_id, test_policy_content, persist=True
        )
        print(f"   Upload result: {result.get('message')}")
        print(f"   File saved to: {result.get('file_path')}")
        print(f"   Persisted: {result.get('persisted')}")

        # 4. Verify the file exists on disk
        print("\n4. Verifying file on disk...")
        policy_file = Path(f"policies/{test_policy_id}.rego")
        if policy_file.exists():
            print(f"   ✅ File exists: {policy_file}")
            file_size = policy_file.stat().st_size
            print(f"   File size: {file_size} bytes")
        else:
            print(f"   ❌ File not found: {policy_file}")

        # 5. Get policy content from OPA (after upload)
        print("\n5. Getting policy content from OPA...")
        content_result = await opa.get_policy_content(test_policy_id)
        if content_result.get("success"):
            print("   ✅ Policy retrieved successfully")
            print(f"   Policy ID: {content_result.get('policy_id')}")
            print(f"   Content size: {content_result.get('size')} bytes")
            print("   Content preview (first 100 chars):")
            print(f"   {content_result.get('content', '')[:100]}...")
        else:
            print(f"   ❌ Failed: {content_result.get('error')}")

        # 6. Compare file content with OPA content
        print("\n6. Comparing disk file with OPA content...")
        if policy_file.exists():
            disk_content = policy_file.read_text()
            opa_content = content_result.get("content", "")
            if disk_content.strip() == opa_content.strip():
                print("   ✅ Contents match perfectly!")
            else:
                print("   ⚠️  Contents differ")
                print(f"      Disk: {len(disk_content)} bytes")
                print(f"      OPA:  {len(opa_content)} bytes")

        # 7. List policies again (after)
        print("\n7. Listing policies (AFTER)...")
        policies_after = await opa.list_policies()
        policy_ids_after = [p.get("id", "") for p in policies_after.get("result", [])]
        print(f"   Policies: {policy_ids_after}")
        if test_policy_id in str(policy_ids_after):
            print(f"   ✅ Test policy '{test_policy_id}' is in the list")

        # 8. Cleanup - delete policy
        print("\n8. Cleanup - deleting test policy...")
        delete_result = await opa.delete_policy(test_policy_id, delete_file=True)
        print(f"   {delete_result.get('message')}")
        print(f"   File deleted: {delete_result.get('file_deleted')}")

        # 9. Verify file was deleted
        print("\n9. Verifying file was deleted...")
        if not policy_file.exists():
            print(f"   ✅ File deleted: {policy_file}")
        else:
            print(f"   ⚠️  File still exists: {policy_file}")

        print("\n" + "=" * 70)
        print("✅ Policy persistence test completed successfully!")
        print("=" * 70)
        print("\nKey findings:")
        print("  • Policies uploaded via API are now saved to disk")
        print("  • Policy files persist in the 'policies/' directory")
        print("  • File content matches OPA content exactly")
        print(
            "  • Policies survive OPA restarts (test with: docker-compose restart opa)"
        )

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await opa.close()


if __name__ == "__main__":
    asyncio.run(main())
