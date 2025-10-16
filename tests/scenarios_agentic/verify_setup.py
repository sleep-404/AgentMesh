#!/usr/bin/env python3
"""
Verification script for agentic test setup.

This script checks if all prerequisites are running and the mesh is accessible.
Run this before running the actual tests to ensure everything is configured correctly.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dummy_agents.simple_nats_agent import SimpleNATSAgent

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(text: str):
    """Print a colored header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print("=" * len(text))


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


async def check_nats_connection() -> bool:
    """Check if NATS server is accessible."""
    print_header("Checking NATS Server")
    try:
        import nats

        nc = await nats.connect("nats://localhost:4222", connect_timeout=2)
        await nc.close()
        print_success("NATS server is running on port 4222")
        return True
    except Exception as e:
        print_error(f"NATS server not accessible: {e}")
        print("   Start it with: nats-server --port 4222")
        return False


async def check_mesh_service() -> bool:
    """Check if AgentMesh service is running."""
    print_header("Checking AgentMesh Service")
    try:
        agent = SimpleNATSAgent("nats://localhost:4222")
        await agent.connect_to_mesh()

        # Try to query health
        try:
            response = await agent.nc.request("mesh.health", b"{}", timeout=3.0)
            health = json.loads(response.data.decode())
            print_success("AgentMesh service is running")
            print(f"   Services status: {health.get('services', {})}")
            await agent.disconnect()
            return True
        except asyncio.TimeoutError:
            print_error("AgentMesh service not responding to health checks")
            print("   Start it with: python -m services.bootstrap.mesh_service")
            await agent.disconnect()
            return False

    except Exception as e:
        print_error(f"Failed to check mesh service: {e}")
        return False


async def check_agent_registration() -> bool:
    """Check if agent registration works."""
    print_header("Testing Agent Registration")
    try:
        agent = SimpleNATSAgent("nats://localhost:4222")
        await agent.connect_to_mesh()

        # Try to register a test agent
        result = await agent.register_with_mesh(
            identity="verify-test-agent",
            version="1.0.0",
            capabilities=["test"],
            operations=["query"],
        )

        if "error" in result:
            print_error(f"Agent registration failed: {result['error']}")
            await agent.disconnect()
            return False

        print_success(f"Agent registration works (status: {result.get('status')})")
        await agent.disconnect()
        return True

    except Exception as e:
        print_error(f"Agent registration test failed: {e}")
        return False


async def check_directory_query() -> bool:
    """Check if directory queries work."""
    print_header("Testing Directory Query")
    try:
        agent = SimpleNATSAgent("nats://localhost:4222")
        await agent.connect_to_mesh()

        # Try to query directory
        agents = await agent.discover_agents()

        if "error" in agents:
            print_error(f"Directory query failed: {agents['error']}")
            await agent.disconnect()
            return False

        print_success(
            f"Directory query works (found {agents.get('total_count', 0)} agents)"
        )

        # List discovered agents
        for agent_info in agents.get("agents", [])[:3]:  # Show first 3
            print(f"   - {agent_info['identity']} (capabilities: {agent_info['capabilities']})")

        await agent.disconnect()
        return True

    except Exception as e:
        print_error(f"Directory query test failed: {e}")
        return False


async def check_kb_registration() -> bool:
    """Check if KB registration works."""
    print_header("Testing KB Registration")
    try:
        agent = SimpleNATSAgent("nats://localhost:4222")
        await agent.connect_to_mesh()

        # Try to register a test KB
        result = await agent.register_kb(
            kb_id="verify-test-kb",
            kb_type="postgres",
            endpoint="postgresql://localhost:5432/test",
            operations=["sql_query"],
        )

        if "error" in result:
            print_error(f"KB registration failed: {result['error']}")
            await agent.disconnect()
            return False

        print_success(f"KB registration works (status: {result.get('status')})")
        if result.get("status") == "offline":
            print_warning("KB status is 'offline' (database not accessible - this is OK)")

        await agent.disconnect()
        return True

    except Exception as e:
        print_error(f"KB registration test failed: {e}")
        return False


async def check_kb_discovery() -> bool:
    """Check if KB discovery works."""
    print_header("Testing KB Discovery")
    try:
        agent = SimpleNATSAgent("nats://localhost:4222")
        await agent.connect_to_mesh()

        # Try to query KB directory
        kbs = await agent.discover_kbs()

        if "error" in kbs:
            print_error(f"KB discovery failed: {kbs['error']}")
            await agent.disconnect()
            return False

        print_success(f"KB discovery works (found {kbs.get('total_count', 0)} KBs)")

        # List discovered KBs
        for kb_info in kbs.get("kbs", [])[:3]:  # Show first 3
            print(
                f"   - {kb_info['kb_id']} (type: {kb_info['kb_type']}, status: {kb_info['status']})"
            )

        await agent.disconnect()
        return True

    except Exception as e:
        print_error(f"KB discovery test failed: {e}")
        return False


async def run_all_checks():
    """Run all verification checks."""
    print(f"\n{Colors.BOLD}🔍 AgentMesh Agentic Test Setup Verification{Colors.END}")
    print("=" * 50)

    results = {}

    # Check NATS
    results["nats"] = await check_nats_connection()
    if not results["nats"]:
        print("\n⛔ Cannot proceed without NATS. Please start NATS server first.")
        return False

    # Check mesh service
    results["mesh"] = await check_mesh_service()
    if not results["mesh"]:
        print("\n⛔ Cannot proceed without mesh service. Please start it first.")
        return False

    # Check agent registration
    results["agent_reg"] = await check_agent_registration()

    # Check directory query
    results["directory"] = await check_directory_query()

    # Check KB registration
    results["kb_reg"] = await check_kb_registration()

    # Check KB discovery
    results["kb_discovery"] = await check_kb_discovery()

    # Summary
    print_header("Verification Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\nPassed: {passed}/{total} checks")
    print("\nDetailed Results:")
    print(f"  NATS Connection:     {'✅' if results.get('nats') else '❌'}")
    print(f"  Mesh Service:        {'✅' if results.get('mesh') else '❌'}")
    print(f"  Agent Registration:  {'✅' if results.get('agent_reg') else '❌'}")
    print(f"  Directory Query:     {'✅' if results.get('directory') else '❌'}")
    print(f"  KB Registration:     {'✅' if results.get('kb_reg') else '❌'}")
    print(f"  KB Discovery:        {'✅' if results.get('kb_discovery') else '❌'}")

    if all(results.values()):
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All checks passed! Ready to run agentic tests.{Colors.END}")
        print(f"\n{Colors.BLUE}Run tests with:{Colors.END}")
        print("  pytest tests/scenarios_agentic/test_1_registration_discovery_agentic.py -v -s")
        return True
    else:
        print(
            f"\n{Colors.YELLOW}⚠️  Some checks failed. Fix the issues above before running tests.{Colors.END}"
        )
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_checks())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⛔ Verification cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

