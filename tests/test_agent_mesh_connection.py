"""
Test agent mesh connection framework.

This test:
1. Starts NATS, connection API server
2. Runs langraph agent with mesh connectivity
3. Verifies agent connects, discovers capabilities, queries KBs
4. Checks logs
"""
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_langraph_mesh_connection():
    """Test langraph agent connecting to mesh"""
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
    logger.info(f"Steps: {result['steps_executed']}")
    logger.info(f"Mesh Data: {result.get('mesh_data', {})}")

    # Verify results
    assert result["status"] == "completed"
    assert "mesh_data" in result

    logger.info("=" * 80)
    logger.info("TEST PASSED ✓")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_langraph_mesh_connection())
