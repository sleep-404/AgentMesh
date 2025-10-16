"""Basic test to verify NATS message broker pattern implementation."""

import asyncio
import logging

from adapters.knowledge_base.postgres.adapter import PostgresAdapter
from adapters.messaging.nats_client import NATSWrapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_nats_pattern():
    """Test the basic NATS pattern without full mesh."""

    logger.info("Testing NATS message broker pattern...")

    # Test 1: Initialize NATS
    logger.info("\n[1] Testing NATS connection...")
    nats = NATSWrapper()
    try:
        await nats.connect()
        logger.info("✓ NATS connected")
    except Exception as e:
        logger.error(f"✗ NATS connection failed: {e}")
        logger.info("Start NATS: docker run -d -p 4222:4222 nats:latest")
        return False

    # Test 2: Create adapter with NATS
    logger.info("\n[2] Testing KB adapter with NATS...")
    try:
        adapter = PostgresAdapter(
            "adapters/knowledge_base/postgres/config.yaml",
            nats_client=nats,
            kb_id="test-kb",
        )
        await adapter.connect()
        logger.info("✓ Adapter initialized with NATS")
    except Exception as e:
        logger.error(f"✗ Adapter initialization failed: {e}")
        await nats.disconnect()
        return False

    # Test 3: Start listening on NATS
    logger.info("\n[3] Testing NATS listening...")
    try:
        await adapter.start_listening()
        logger.info("✓ Adapter listening on test-kb.adapter.query")
    except Exception as e:
        logger.error(f"✗ NATS listening failed: {e}")
        await adapter.disconnect()
        await nats.disconnect()
        return False

    # Test 4: Send request via NATS
    logger.info("\n[4] Testing NATS request-reply...")
    try:
        # Give NATS a moment to set up subscription
        await asyncio.sleep(0.5)

        response = await nats.request(
            "test-kb.adapter.query",
            {"operation": "sql_query", "params": {"query": "SELECT 1 as test"}},
            timeout=3.0,
        )

        if response and response.get("status") == "success":
            logger.info(f"✓ Request-reply successful: {response}")
        else:
            logger.error(f"✗ Unexpected response: {response}")
            await adapter.disconnect()
            await nats.disconnect()
            return False

    except Exception as e:
        logger.error(f"✗ Request-reply failed: {e}")
        await adapter.disconnect()
        await nats.disconnect()
        return False

    # Cleanup
    logger.info("\n[5] Cleaning up...")
    await adapter.disconnect()
    await nats.disconnect()
    logger.info("✓ Cleanup complete")

    logger.info("\n" + "=" * 50)
    logger.info("✓ ALL TESTS PASSED - NATS PATTERN WORKING!")
    logger.info("=" * 50)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_nats_pattern())
    exit(0 if success else 1)
