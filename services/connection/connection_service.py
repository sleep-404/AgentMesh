"""
Agent Connection Service.

Handles agent connections to the mesh with token authentication,
ID assignment, and NATS subject management.
"""
import asyncio
import logging
import secrets
from datetime import UTC, datetime

from adapters.messaging.nats_client import NATSWrapper

from .schemas import (
    AgentConnectionRequest,
    AgentConnectionResponse,
    AgentHeartbeat,
    MeshUpdate,
)

logger = logging.getLogger(__name__)

# Simple hardcoded tokens for demo (in production, use proper auth)
VALID_TOKENS = {
    "mesh-agent-token-001",
    "mesh-agent-token-002",
    "demo-token",
    "test-token",
}

# Global subjects for mesh-wide notifications
GLOBAL_SUBJECTS = {
    "mesh.updates.agents": "Notifications when agents register/disconnect",
    "mesh.updates.kbs": "Notifications when KBs are registered/removed",
    "mesh.updates.all": "All mesh updates",
}


class AgentConnectionService:
    """Service for managing agent connections to the mesh"""

    def __init__(self, nats_client: NATSWrapper):
        """
        Initialize connection service.

        Args:
            nats_client: NATS client for messaging
        """
        self.nats = nats_client
        self.connected_agents: dict[str, dict] = {}  # agent_id -> connection info
        self._monitoring_task: asyncio.Task | None = None

    async def connect_agent(
        self, request: AgentConnectionRequest
    ) -> AgentConnectionResponse:
        """
        Connect an agent to the mesh.

        Args:
            request: Connection request with endpoint and token

        Returns:
            Connection response with assigned ID and subjects

        Raises:
            ValueError: If token is invalid
        """
        # Validate token
        if request.token not in VALID_TOKENS:
            raise ValueError("Invalid authentication token")

        # Generate unique agent ID
        agent_id = self._generate_agent_id()

        # Define private subject for this agent
        private_subject = f"agent.{agent_id}"

        # Store connection info
        self.connected_agents[agent_id] = {
            "endpoint": request.endpoint,
            "private_subject": private_subject,
            "connected_at": datetime.now(UTC),
            "last_heartbeat": datetime.now(UTC),
            "metadata": request.metadata,
        }

        # Subscribe agent to global subjects (mesh will publish, agent will receive)
        global_subjects = list(GLOBAL_SUBJECTS.keys())

        logger.info(
            f"Agent '{agent_id}' connected from {request.endpoint}, private subject: {private_subject}"
        )

        # Publish notification about new agent connection
        if self.nats and self.nats.is_connected:
            await self._publish_agent_connected(agent_id, request)

        return AgentConnectionResponse(
            agent_id=agent_id,
            private_subject=private_subject,
            global_subjects=global_subjects,
            connection_status="connected",
            connected_at=self.connected_agents[agent_id]["connected_at"],
        )

    async def disconnect_agent(
        self, agent_id: str, reason: str = "Normal disconnect"
    ) -> None:
        """
        Disconnect an agent from the mesh.

        Args:
            agent_id: ID of agent to disconnect
            reason: Reason for disconnection
        """
        if agent_id not in self.connected_agents:
            logger.warning(f"Agent '{agent_id}' not found in connected agents")
            return

        # Remove from connected agents
        self.connected_agents.pop(agent_id)

        logger.info(f"Agent '{agent_id}' disconnected: {reason}")

        # Publish notification about agent disconnection
        if self.nats and self.nats.is_connected:
            await self._publish_agent_disconnected(agent_id, reason)

    async def handle_heartbeat(self, heartbeat: AgentHeartbeat) -> dict[str, str]:
        """
        Handle heartbeat from connected agent.

        Args:
            heartbeat: Heartbeat message

        Returns:
            Acknowledgment
        """
        if heartbeat.agent_id in self.connected_agents:
            self.connected_agents[heartbeat.agent_id][
                "last_heartbeat"
            ] = heartbeat.timestamp
            self.connected_agents[heartbeat.agent_id]["status"] = heartbeat.status
            logger.debug(f"Heartbeat received from agent '{heartbeat.agent_id}'")
            return {"status": "ok", "message": "Heartbeat acknowledged"}
        else:
            logger.warning(f"Heartbeat from unknown agent '{heartbeat.agent_id}'")
            return {"status": "error", "message": "Agent not connected"}

    async def get_connected_agents(self) -> list[dict]:
        """
        Get list of all connected agents.

        Returns:
            List of connected agent info
        """
        return [
            {
                "agent_id": agent_id,
                "endpoint": info["endpoint"],
                "private_subject": info["private_subject"],
                "connected_at": info["connected_at"].isoformat(),
                "last_heartbeat": info["last_heartbeat"].isoformat(),
                "metadata": info["metadata"],
            }
            for agent_id, info in self.connected_agents.items()
        ]

    async def send_direct_message(
        self, to_agent_id: str, message: dict, from_agent_id: str = "mesh"
    ) -> bool:
        """
        Send a direct message to a specific agent.

        Args:
            to_agent_id: Target agent ID
            message: Message payload
            from_agent_id: Sender agent ID (default: "mesh")

        Returns:
            True if message sent successfully
        """
        if to_agent_id not in self.connected_agents:
            logger.error(f"Agent '{to_agent_id}' not connected")
            return False

        private_subject = self.connected_agents[to_agent_id]["private_subject"]

        if not self.nats or not self.nats.is_connected:
            logger.error("NATS client not connected")
            return False

        try:
            message_payload = {
                "from_agent_id": from_agent_id,
                "to_agent_id": to_agent_id,
                "message_type": "direct",
                "payload": message,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            await self.nats.publish(private_subject, message_payload)
            logger.debug(f"Sent direct message to agent '{to_agent_id}'")
            return True
        except Exception as e:
            logger.error(f"Failed to send direct message: {e}")
            return False

    async def request_from_agent(
        self, agent_id: str, request_data: dict, timeout: int = 5
    ) -> dict | None:
        """
        Send a request to an agent and wait for response (request-reply pattern).

        Args:
            agent_id: Target agent ID
            request_data: Request payload
            timeout: Timeout in seconds

        Returns:
            Response from agent or None if timeout/error
        """
        if agent_id not in self.connected_agents:
            logger.error(f"Agent '{agent_id}' not connected")
            return None

        private_subject = self.connected_agents[agent_id]["private_subject"]

        if not self.nats or not self.nats.is_connected:
            logger.error("NATS client not connected")
            return None

        try:
            message_payload = {
                "from_agent_id": "mesh",
                "to_agent_id": agent_id,
                "message_type": "request",
                "payload": request_data,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            response = await self.nats.request(
                private_subject, message_payload, timeout=timeout
            )
            logger.debug(f"Received response from agent '{agent_id}'")
            return response
        except Exception as e:
            logger.error(f"Failed to request from agent: {e}")
            return None

    async def broadcast_mesh_update(self, update: MeshUpdate) -> None:
        """
        Broadcast an update to all connected agents.

        Args:
            update: Mesh update to broadcast
        """
        if not self.nats or not self.nats.is_connected:
            logger.error("NATS client not connected")
            return

        try:
            # Determine which subject to publish to
            if update.update_type in ["agent_registered", "agent_disconnected"]:
                subject = "mesh.updates.agents"
            elif update.update_type in ["kb_registered", "kb_removed"]:
                subject = "mesh.updates.kbs"
            else:
                subject = "mesh.updates.all"

            # Also publish to "all" subject
            await self.nats.publish(subject, update.model_dump(mode="json"))
            await self.nats.publish("mesh.updates.all", update.model_dump(mode="json"))

            logger.debug(f"Broadcasted mesh update: {update.update_type}")
        except Exception as e:
            logger.error(f"Failed to broadcast mesh update: {e}")

    async def start_monitoring(self, check_interval: int = 30) -> None:
        """
        Start monitoring connected agents for stale connections.

        Args:
            check_interval: Interval in seconds between checks
        """
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Monitoring already running")
            return

        async def monitor():
            while True:
                try:
                    await asyncio.sleep(check_interval)
                    now = datetime.now(UTC)

                    # Check for stale connections (no heartbeat in 2x check_interval)
                    stale_threshold = check_interval * 2
                    stale_agents = []

                    for agent_id, info in self.connected_agents.items():
                        last_hb = info["last_heartbeat"]
                        if (now - last_hb).total_seconds() > stale_threshold:
                            stale_agents.append(agent_id)

                    # Disconnect stale agents
                    for agent_id in stale_agents:
                        logger.warning(
                            f"Agent '{agent_id}' connection stale, disconnecting"
                        )
                        await self.disconnect_agent(
                            agent_id, "Stale connection (no heartbeat)"
                        )

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in connection monitoring: {e}")

        self._monitoring_task = asyncio.create_task(monitor())
        logger.info(f"Started connection monitoring (interval: {check_interval}s)")

    async def stop_monitoring(self) -> None:
        """Stop monitoring task"""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped connection monitoring")

    def _generate_agent_id(self) -> str:
        """Generate a unique agent ID"""
        # Use timestamp + random hex for uniqueness
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        random_hex = secrets.token_hex(4)
        return f"agent-{timestamp}-{random_hex}"

    async def _publish_agent_connected(
        self, agent_id: str, request: AgentConnectionRequest
    ) -> None:
        """Publish notification when agent connects"""
        update = MeshUpdate(
            update_type="agent_connected",
            timestamp=datetime.now(UTC),
            data={
                "agent_id": agent_id,
                "endpoint": request.endpoint,
                "metadata": request.metadata,
            },
        )
        await self.broadcast_mesh_update(update)

    async def _publish_agent_disconnected(self, agent_id: str, reason: str) -> None:
        """Publish notification when agent disconnects"""
        update = MeshUpdate(
            update_type="agent_disconnected",
            timestamp=datetime.now(UTC),
            data={
                "agent_id": agent_id,
                "reason": reason,
            },
        )
        await self.broadcast_mesh_update(update)
