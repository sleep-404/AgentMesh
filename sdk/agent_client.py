"""
AgentMesh SDK - Client framework for agents to connect to the mesh.

Provides a simple interface for agents to:
- Connect to the mesh with authentication
- Subscribe to global mesh updates
- Listen on their private subject
- Send messages to other agents
- Implement callbacks for various events
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from adapters.messaging.nats_client import NATSWrapper

logger = logging.getLogger(__name__)


class AgentCallbacks(ABC):
    """
    Abstract base class for agent callbacks.

    Agents should extend this class and implement the callback methods
    to handle various mesh events.
    """

    @abstractmethod
    async def on_agent_registered(self, agent_data: dict[str, Any]) -> None:
        """
        Called when a new agent registers with the mesh.

        Args:
            agent_data: Information about the newly registered agent
        """
        pass

    @abstractmethod
    async def on_kb_registered(self, kb_data: dict[str, Any]) -> None:
        """
        Called when a new KB is registered with the mesh.

        Args:
            kb_data: Information about the newly registered KB
        """
        pass

    @abstractmethod
    async def on_agent_disconnected(self, agent_data: dict[str, Any]) -> None:
        """
        Called when an agent disconnects from the mesh.

        Args:
            agent_data: Information about the disconnected agent
        """
        pass

    @abstractmethod
    async def on_direct_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """
        Called when a direct message is received on the agent's private subject.

        Args:
            message: The message payload

        Returns:
            Optional response (for request-reply pattern). Return None for fire-and-forget.
        """
        pass


class AgentClient:
    """
    Client for agents to connect to the AgentMesh.

    This class provides a high-level interface for agents to interact
    with the mesh, including connection, subscriptions, and messaging.
    """

    def __init__(
        self,
        mesh_endpoint: str,
        agent_endpoint: str,
        token: str,
        callbacks: AgentCallbacks,
        nats_url: str = "nats://localhost:4222",
        metadata: dict[str, Any] | None = None,
    ):
        """
        Initialize the agent client.

        Args:
            mesh_endpoint: URL of the mesh connection API (e.g., "http://localhost:8080/connect")
            agent_endpoint: This agent's endpoint URL (gRPC/REST)
            token: Authentication token for mesh connection
            callbacks: Callbacks implementation for handling events
            nats_url: NATS server URL (default: nats://localhost:4222)
            metadata: Optional metadata about this agent
        """
        self.mesh_endpoint = mesh_endpoint
        self.agent_endpoint = agent_endpoint
        self.token = token
        self.callbacks = callbacks
        self.nats_url = nats_url
        self.metadata = metadata or {}

        # Connection state
        self.agent_id: str | None = None
        self.private_subject: str | None = None
        self.global_subjects: list[str] = []
        self.connected = False

        # NATS client
        self.nats = NATSWrapper(url=nats_url)

        # Heartbeat task
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(self) -> dict[str, Any]:
        """
        Connect to the mesh.

        Returns:
            Connection response with agent_id and subjects

        Raises:
            Exception: If connection fails
        """
        logger.info(f"Connecting to mesh at {self.mesh_endpoint}")

        # Connect to NATS first
        await self.nats.connect()
        logger.info(f"Connected to NATS at {self.nats_url}")

        # Connect to mesh via REST API (we'll implement this server next)
        # For now, simulate the connection by directly using the connection service
        # In practice, this would be an HTTP POST to the mesh REST API

        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                request_data = {
                    "endpoint": self.agent_endpoint,
                    "token": self.token,
                    "metadata": self.metadata,
                }

                async with session.post(
                    self.mesh_endpoint,
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Connection failed: {error_text}")

                    result: dict[str, Any] = await response.json()

                    self.agent_id = result["agent_id"]
                    self.private_subject = result["private_subject"]
                    self.global_subjects = result["global_subjects"]
                    self.connected = True

                    logger.info(f"Connected to mesh as agent '{self.agent_id}'")
                    logger.info(f"Private subject: {self.private_subject}")
                    logger.info(f"Global subjects: {self.global_subjects}")

                    # Subscribe to subjects
                    await self._subscribe_to_subjects()

                    # Start heartbeat
                    await self._start_heartbeat()

                    return result

        except Exception as e:
            logger.error(f"Failed to connect to mesh: {e}")
            raise

    async def disconnect(self, reason: str = "Normal disconnect") -> None:
        """
        Disconnect from the mesh.

        Args:
            reason: Reason for disconnection
        """
        if not self.connected:
            logger.warning("Not connected to mesh")
            return

        logger.info(f"Disconnecting from mesh: {reason}")

        # Stop heartbeat
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Notify mesh of disconnection
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                disconnect_url = self.mesh_endpoint.replace("/connect", "/disconnect")
                await session.post(
                    disconnect_url,
                    json={"agent_id": self.agent_id, "reason": reason},
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception as e:
            logger.error(f"Failed to notify mesh of disconnection: {e}")

        # Disconnect from NATS
        await self.nats.disconnect()

        self.connected = False
        logger.info("Disconnected from mesh")

    async def send_message_to_agent(
        self, target_agent_id: str, message: dict[str, Any]
    ) -> None:
        """
        Send a message to another agent (fire-and-forget).

        Args:
            target_agent_id: ID of the target agent
            message: Message payload
        """
        if not self.connected:
            raise Exception("Not connected to mesh")

        target_subject = f"agent.{target_agent_id}"

        message_payload = {
            "from_agent_id": self.agent_id,
            "to_agent_id": target_agent_id,
            "message_type": "direct",
            "payload": message,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self.nats.publish(target_subject, message_payload)
        logger.debug(f"Sent message to agent '{target_agent_id}'")

    async def request_from_agent(
        self, target_agent_id: str, request_data: dict[str, Any], timeout: int = 5
    ) -> dict[str, Any] | None:
        """
        Send a request to another agent and wait for response.

        Args:
            target_agent_id: ID of the target agent
            request_data: Request payload
            timeout: Timeout in seconds

        Returns:
            Response from the agent or None if timeout
        """
        if not self.connected:
            raise Exception("Not connected to mesh")

        target_subject = f"agent.{target_agent_id}"

        message_payload = {
            "from_agent_id": self.agent_id,
            "to_agent_id": target_agent_id,
            "message_type": "request",
            "payload": request_data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        response = await self.nats.request(
            target_subject, message_payload, timeout=timeout
        )
        logger.debug(f"Received response from agent '{target_agent_id}'")
        return response

    async def _subscribe_to_subjects(self) -> None:
        """Subscribe to global subjects and private subject"""
        # Subscribe to global subjects for mesh updates
        for subject in self.global_subjects:
            # Type ignore for the callback type issue - it's correct but mypy can't infer it
            await self.nats.subscribe(subject, self._handle_mesh_update)  # type: ignore[arg-type]
            logger.debug(f"Subscribed to global subject: {subject}")

        # Subscribe to private subject for direct messages
        if self.private_subject:
            await self.nats.subscribe(
                self.private_subject, self._handle_direct_message  # type: ignore[arg-type]
            )
            logger.debug(f"Subscribed to private subject: {self.private_subject}")

    async def _handle_mesh_update(self, message: dict[str, Any]) -> None:
        """Handle mesh update notifications"""
        try:
            update_type = message.get("update_type", message.get("type"))
            data = message.get("data", {})

            if update_type == "agent_registered" or update_type == "agent_connected":
                await self.callbacks.on_agent_registered(data)
            elif update_type == "kb_registered":
                await self.callbacks.on_kb_registered(data)
            elif update_type == "agent_disconnected":
                await self.callbacks.on_agent_disconnected(data)

        except Exception as e:
            logger.error(f"Error handling mesh update: {e}")

    async def _handle_direct_message(
        self, message: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Handle direct messages on private subject"""
        try:
            # Pass to callback
            response = await self.callbacks.on_direct_message(message)

            # If callback returns a response and this is a request, return it
            if response is not None and message.get("message_type") == "request":
                return {
                    "from_agent_id": self.agent_id,
                    "status": "success",
                    "response": response,
                    "timestamp": datetime.now(UTC).isoformat(),
                }

            return None

        except Exception as e:
            logger.error(f"Error handling direct message: {e}")
            # Return error response for requests
            if message.get("message_type") == "request":
                return {
                    "from_agent_id": self.agent_id,
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            return None

    async def _start_heartbeat(self, interval: int = 30) -> None:
        """Start sending heartbeats to the mesh"""

        async def heartbeat_loop():
            while self.connected:
                try:
                    await asyncio.sleep(interval)

                    # Send heartbeat via REST API
                    import aiohttp

                    async with aiohttp.ClientSession() as session:
                        heartbeat_url = self.mesh_endpoint.replace(
                            "/connect", "/heartbeat"
                        )
                        await session.post(
                            heartbeat_url,
                            json={
                                "agent_id": self.agent_id,
                                "timestamp": datetime.now(UTC).isoformat(),
                                "status": "active",
                                "metadata": {},
                            },
                            timeout=aiohttp.ClientTimeout(total=5),
                        )
                    logger.debug("Sent heartbeat")

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error sending heartbeat: {e}")

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())
