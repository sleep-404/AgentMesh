"""
Sample Agent - Demonstrates how to connect to AgentMesh.

This example shows how an agent can:
1. Connect to the mesh via NATS
2. Subscribe to directory updates
3. Query the directory to discover agents and KBs
4. Receive real-time notifications when new entities register
"""
import asyncio
import logging
import uuid

from adapters.messaging.nats_client import NATSWrapper

logger = logging.getLogger(__name__)


class SampleAgent:
    """Sample agent that demonstrates mesh connectivity."""

    def __init__(
        self,
        agent_name: str = "sample-agent-1",
        nats_url: str = "nats://localhost:4222",
    ):
        """
        Initialize sample agent.

        Args:
            agent_name: Name of this agent
            nats_url: NATS server URL
        """
        self.agent_name = agent_name
        self.nats_client = NATSWrapper(url=nats_url)
        self.local_cache: dict[str, list] = {"agents": [], "kbs": []}

    async def start(self) -> None:
        """Start the agent and connect to mesh."""
        logger.info(f"[{self.agent_name}] Starting agent...")

        # Connect to NATS
        try:
            await self.nats_client.connect()
            logger.info(f"[{self.agent_name}] Connected to mesh via NATS")
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to connect to NATS: {e}")
            logger.error(
                f"[{self.agent_name}] Make sure NATS is running (docker-compose up -d)"
            )
            return

        # Subscribe to directory updates
        await self.nats_client.subscribe(
            "mesh.directory.updates", self._handle_directory_update
        )
        logger.info(f"[{self.agent_name}] Subscribed to directory updates")

        # Query directory on startup
        await self._query_directory()

        logger.info(f"[{self.agent_name}] Agent started successfully")

    async def _handle_directory_update(self, message: dict) -> None:
        """
        Handle directory update notifications.

        Args:
            message: Update notification message
        """
        msg_type = message.get("type")
        data = message.get("data", {})

        if msg_type == "agent_registered":
            identity = data.get("identity")
            capabilities = data.get("capabilities", [])
            logger.info(f"[{self.agent_name}] 🎉 New agent registered: {identity}")
            logger.info(
                f"[{self.agent_name}]    Capabilities: {', '.join(capabilities)}"
            )

            # Update local cache
            self.local_cache["agents"].append(
                {
                    "identity": identity,
                    "capabilities": capabilities,
                    "operations": data.get("operations", []),
                }
            )

        elif msg_type == "kb_registered":
            kb_id = data.get("kb_id")
            kb_type = data.get("kb_type")
            operations = data.get("operations", [])
            logger.info(f"[{self.agent_name}] 🎉 New KB registered: {kb_id} ({kb_type})")
            logger.info(f"[{self.agent_name}]    Operations: {', '.join(operations)}")

            # Update local cache
            self.local_cache["kbs"].append(
                {
                    "kb_id": kb_id,
                    "kb_type": kb_type,
                    "operations": operations,
                }
            )

    async def _query_directory(self) -> None:
        """Query the directory to get all available agents and KBs."""
        logger.info(f"[{self.agent_name}] Querying directory...")

        request = {
            "request_id": str(uuid.uuid4()),
            "filter": None,  # Get both agents and KBs
        }

        try:
            response = await self.nats_client.request(
                "mesh.directory.query", request, timeout=5
            )

            if response and "error" not in response:
                agents = response.get("agents", [])
                kbs = response.get("kbs", [])

                logger.info(f"[{self.agent_name}] Directory query response:")
                logger.info(f"[{self.agent_name}]   Found {len(agents)} agent(s)")

                for agent in agents:
                    identity = agent.get("identity", "unknown")
                    capabilities = agent.get("capabilities", [])
                    status = agent.get("status", "unknown")
                    logger.info(f"[{self.agent_name}]     - {identity} [{status}]")
                    logger.info(
                        f"[{self.agent_name}]       Capabilities: {', '.join(capabilities)}"
                    )

                logger.info(f"[{self.agent_name}]   Found {len(kbs)} KB(s)")

                for kb in kbs:
                    kb_id = kb.get("kb_id", "unknown")
                    kb_type = kb.get("kb_type", "unknown")
                    operations = kb.get("operations", [])
                    status = kb.get("status", "unknown")
                    logger.info(
                        f"[{self.agent_name}]     - {kb_id} ({kb_type}) [{status}]"
                    )
                    logger.info(
                        f"[{self.agent_name}]       Operations: {', '.join(operations)}"
                    )

                # Update local cache
                self.local_cache["agents"] = agents
                self.local_cache["kbs"] = kbs

            else:
                error = (
                    response.get("error", "Unknown error")
                    if response
                    else "No response"
                )
                logger.error(f"[{self.agent_name}] Directory query failed: {error}")

        except Exception as e:
            logger.error(f"[{self.agent_name}] Directory query error: {e}")
            logger.error(
                f"[{self.agent_name}] Make sure directory subscriber is running"
            )

    async def discover_agents_by_capability(self, capability: str) -> list:
        """
        Discover agents that have a specific capability.

        Args:
            capability: Capability to search for

        Returns:
            List of agents with the specified capability
        """
        matching_agents = [
            agent
            for agent in self.local_cache["agents"]
            if capability in agent.get("capabilities", [])
        ]

        logger.info(
            f"[{self.agent_name}] Agents with capability '{capability}': {len(matching_agents)}"
        )
        for agent in matching_agents:
            logger.info(f"[{self.agent_name}]   - {agent.get('identity')}")

        return matching_agents

    async def discover_kbs_by_type(self, kb_type: str) -> list:
        """
        Discover KBs of a specific type.

        Args:
            kb_type: KB type to search for (e.g., 'postgres', 'neo4j')

        Returns:
            List of KBs with the specified type
        """
        matching_kbs = [
            kb for kb in self.local_cache["kbs"] if kb.get("kb_type") == kb_type
        ]

        logger.info(f"[{self.agent_name}] KBs of type '{kb_type}': {len(matching_kbs)}")
        for kb in matching_kbs:
            logger.info(f"[{self.agent_name}]   - {kb.get('kb_id')}")

        return matching_kbs

    async def stop(self) -> None:
        """Stop the agent and disconnect from mesh."""
        logger.info(f"[{self.agent_name}] Stopping agent...")
        await self.nats_client.disconnect()
        logger.info(f"[{self.agent_name}] Agent stopped")

    async def run(self) -> None:
        """Run the agent (blocking until interrupted)."""
        await self.start()

        try:
            logger.info(f"[{self.agent_name}] Agent running... (Press Ctrl+C to stop)")
            logger.info(f"[{self.agent_name}] Waiting for directory updates...")

            # Demonstrate capability search after a delay
            await asyncio.sleep(3)
            logger.info(
                f"[{self.agent_name}] --- Demonstration: Searching for capabilities ---"
            )
            await self.discover_agents_by_capability("query_kb")
            await self.discover_kbs_by_type("postgres")

            # Keep running to receive updates
            while True:
                await asyncio.sleep(10)
                # Periodically refresh directory
                await self._query_directory()

        except KeyboardInterrupt:
            logger.info(f"[{self.agent_name}] Received interrupt signal")
        finally:
            await self.stop()


async def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    agent = SampleAgent(agent_name="sample-agent-demo")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
