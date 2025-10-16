"""
Directory subscriber service.

Maintains an in-memory cache of registered agents and KBs.
Subscribes to directory updates and responds to directory queries.
"""
import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.base import BasePersistenceAdapter

logger = logging.getLogger(__name__)


class DirectorySubscriber:
    """Service that maintains directory cache and responds to queries."""

    def __init__(
        self,
        persistence_adapter: BasePersistenceAdapter,
        nats_url: str = "nats://localhost:4222",
    ):
        """
        Initialize directory subscriber.

        Args:
            persistence_adapter: Persistence adapter for loading directory
            nats_url: NATS server URL
        """
        self.persistence = persistence_adapter
        self.nats_client = NATSWrapper(url=nats_url)
        self.directory_cache: dict[str, list[dict[str, Any]]] = {
            "agents": [],
            "kbs": [],
        }

    async def start(self) -> None:
        """Start the directory subscriber service."""
        logger.info("Starting directory subscriber service...")

        # Connect to NATS
        await self.nats_client.connect()
        logger.info("Connected to NATS")

        # Load initial directory from persistence
        await self._load_directory()

        # Subscribe to directory updates
        await self.nats_client.subscribe("mesh.directory.updates", self._handle_update)
        logger.info("Subscribed to mesh.directory.updates")

        # Subscribe to directory queries with request-response handler
        await self._subscribe_to_queries()
        logger.info("Subscribed to mesh.directory.query")

        logger.info("Directory subscriber service started successfully")

    async def _load_directory(self) -> None:
        """Load full directory from persistence layer into memory."""
        try:
            # Import query schemas
            from adapters.persistence.schemas import RegistryQuery

            # Load agents
            agent_query = RegistryQuery(limit=1000)  # Get all agents
            agents = await self.persistence.list_agents(agent_query)
            self.directory_cache["agents"] = [
                {
                    "identity": agent.identity,
                    "version": agent.version,
                    "capabilities": agent.capabilities,
                    "operations": agent.operations,
                    "status": agent.status.value,
                }
                for agent in agents
            ]
            logger.info(
                f"Loaded {len(self.directory_cache['agents'])} agents into cache"
            )

            # Load KBs (using same RegistryQuery)
            kb_query = RegistryQuery(limit=1000)  # Get all KBs
            kbs = await self.persistence.list_kbs(kb_query)
            self.directory_cache["kbs"] = [
                {
                    "kb_id": kb.kb_id,
                    "kb_type": kb.kb_type,
                    "operations": kb.operations,
                    "status": kb.status.value,
                }
                for kb in kbs
            ]
            logger.info(f"Loaded {len(self.directory_cache['kbs'])} KBs into cache")

        except Exception as e:
            logger.error(f"Failed to load directory from persistence: {e}")
            raise

    async def _handle_update(self, message: dict[str, Any]) -> None:
        """
        Handle directory update notifications.

        Args:
            message: Update notification message
        """
        try:
            msg_type = message.get("type")
            data = message.get("data", {})

            if msg_type == "agent_registered":
                # Add or update agent in cache
                identity = data.get("identity")

                # Remove existing entry if present
                self.directory_cache["agents"] = [
                    a
                    for a in self.directory_cache["agents"]
                    if a.get("identity") != identity
                ]

                # Add new entry
                self.directory_cache["agents"].append(
                    {
                        "identity": data.get("identity"),
                        "version": data.get("version"),
                        "capabilities": data.get("capabilities", []),
                        "operations": data.get("operations", []),
                        "status": data.get("status", "active"),
                    }
                )
                logger.info(f"Updated cache: agent '{identity}' registered")

            elif msg_type == "kb_registered":
                # Add or update KB in cache
                kb_id = data.get("kb_id")

                # Remove existing entry if present
                self.directory_cache["kbs"] = [
                    k for k in self.directory_cache["kbs"] if k.get("kb_id") != kb_id
                ]

                # Add new entry
                self.directory_cache["kbs"].append(
                    {
                        "kb_id": data.get("kb_id"),
                        "kb_type": data.get("kb_type"),
                        "operations": data.get("operations", []),
                        "status": data.get("status", "active"),
                    }
                )
                logger.info(f"Updated cache: KB '{kb_id}' registered")

            else:
                logger.warning(f"Unknown update type: {msg_type}")

        except Exception as e:
            logger.error(f"Error handling directory update: {e}")

    async def _subscribe_to_queries(self) -> None:
        """Subscribe to directory query requests using request-response pattern."""
        if not self.nats_client.nc:
            logger.error("Not connected to NATS")
            return

        async def query_handler(msg) -> None:
            try:
                # Parse request
                request_data = json.loads(msg.data.decode())
                logger.debug(f"Received directory query: {request_data}")

                # Build response
                response = {
                    "request_id": request_data.get("request_id", "unknown"),
                    "agents": self.directory_cache["agents"],
                    "kbs": self.directory_cache["kbs"],
                    "timestamp": datetime.now(UTC).isoformat(),
                }

                # Apply filter if specified
                filter_type = request_data.get("filter")
                if filter_type == "agents":
                    response["kbs"] = []
                elif filter_type == "kbs":
                    response["agents"] = []

                # Send response
                response_payload = json.dumps(response).encode()
                await self.nats_client.nc.publish(msg.reply, response_payload)
                logger.debug(f"Sent directory response to {msg.reply}")

            except Exception as e:
                logger.error(f"Error handling directory query: {e}")
                # Send error response
                error_response = {
                    "error": str(e),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                await self.nats_client.nc.publish(
                    msg.reply, json.dumps(error_response).encode()
                )

        # Subscribe with callback
        await self.nats_client.nc.subscribe("mesh.directory.query", cb=query_handler)

    async def stop(self) -> None:
        """Stop the directory subscriber service."""
        logger.info("Stopping directory subscriber service...")
        await self.nats_client.disconnect()
        logger.info("Directory subscriber service stopped")

    async def run(self) -> None:
        """Run the directory subscriber service (blocking)."""
        await self.start()

        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()


async def main():
    """Main entry point for running the directory subscriber."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize persistence adapter
    from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter

    persistence = SQLitePersistenceAdapter("adapters/persistence/sqlite/config.yaml")
    await persistence.connect()

    # Create and run subscriber
    subscriber = DirectorySubscriber(persistence)
    await subscriber.run()


if __name__ == "__main__":
    asyncio.run(main())
