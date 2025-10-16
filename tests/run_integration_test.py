"""
Integration test runner for agent mesh connection.

Runs all required services and tests the framework.
"""
import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

project_root = Path(__file__).parent.parent


async def start_rest_api():
    """Start the REST API server"""
    logger.info("Starting REST API server...")

    import uvicorn

    from api.rest_server import app

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
    )
    server = uvicorn.Server(config)

    # Run in background
    asyncio.create_task(server.serve())

    # Wait for server to start
    await asyncio.sleep(2)
    logger.info("REST API server started on port 8080")


async def run_test():
    """Run the actual test"""
    logger.info("Running agent mesh connection test...")

    from dummy_agents.agents.langraph_agent import LangraphAgent

    logger.info("=" * 80)
    logger.info("STARTING LANGRAPH AGENT WITH MESH CONNECTION")
    logger.info("=" * 80)

    # Create agent with mesh connection enabled
    agent = LangraphAgent(
        task="Test mesh connectivity and query KBs", connect_to_mesh=True
    )

    # Execute agent (this will connect to mesh, discover, query, disconnect)
    result = agent.execute()

    logger.info("=" * 80)
    logger.info("AGENT EXECUTION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Result: {result}")
    logger.info("Steps executed:")
    for step in result["steps_executed"]:
        logger.info(f"  - {step}")
    logger.info(f"Mesh Data: {result.get('mesh_data', {})}")

    # Verify results
    assert result["status"] == "completed", "Agent execution failed"
    assert "mesh_data" in result, "No mesh data in result"

    logger.info("=" * 80)
    logger.info("TEST PASSED ✓")
    logger.info("=" * 80)

    return result


async def main():
    """Main test runner"""
    logger.info("=" * 80)
    logger.info("AGENT MESH CONNECTION INTEGRATION TEST")
    logger.info("=" * 80)

    try:
        # Start REST API server
        await start_rest_api()

        # Wait a bit for everything to stabilize
        await asyncio.sleep(1)

        # Run the test
        await run_test()

        logger.info("=" * 80)
        logger.info("ALL TESTS PASSED ✓")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
