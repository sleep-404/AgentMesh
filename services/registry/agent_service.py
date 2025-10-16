"""
Agent registration service.

Handles agent registration, validation, and health checks.
"""
import asyncio
import logging
import re
from datetime import UTC, datetime

import aiohttp

from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.base import BasePersistenceAdapter
from adapters.persistence.exceptions import DuplicateRecordError
from adapters.persistence.schemas import AgentRegistration, HealthStatus

from .exceptions import (
    DuplicateIdentityError,
    ValidationError,
)
from .schemas import (
    AgentDetailsResponse,
    AgentRegistrationRequest,
    AgentRegistrationResponse,
)

logger = logging.getLogger(__name__)

# Allowed operations for agents
ALLOWED_OPERATIONS = ["publish", "query", "subscribe", "invoke", "execute"]


class AgentService:
    """Service for managing agent registration and lifecycle"""

    def __init__(
        self,
        persistence_adapter: BasePersistenceAdapter,
        nats_client: NATSWrapper | None = None,
    ):
        """
        Initialize agent service.

        Args:
            persistence_adapter: Persistence adapter for storing agent records
            nats_client: Optional NATS client for publishing notifications
        """
        self.persistence = persistence_adapter
        self.nats_client: NATSWrapper | None = nats_client

    async def register_agent(
        self, request: AgentRegistrationRequest
    ) -> AgentRegistrationResponse:
        """
        Register a new agent with validation and health check.

        Args:
            request: Agent registration request

        Returns:
            Agent registration response

        Raises:
            ValidationError: If validation fails
            DuplicateIdentityError: If agent identity already exists
        """
        logger.info(f"Registering agent: {request.identity}")

        # Validate registration data
        self._validate_registration(request)

        # Check for duplicate identity
        existing_agent = await self.persistence.get_agent(request.identity)
        if existing_agent:
            raise DuplicateIdentityError(request.identity)

        # Perform health check
        initial_status = await self._perform_health_check(request.health_endpoint)

        # Create agent registration
        agent_reg = AgentRegistration(
            identity=request.identity,
            version=request.version,
            capabilities=request.capabilities,
            operations=request.operations,
            schemas=request.schemas,
            health_endpoint=request.health_endpoint,
            metadata=request.metadata,
        )

        # Store in persistence layer
        try:
            agent_id = await self.persistence.register_agent(agent_reg)

            # Update status based on health check
            await self.persistence.update_agent_status(request.identity, initial_status)

            logger.info(
                f"Agent '{request.identity}' registered successfully with ID: {agent_id}"
            )

            # Create audit log for agent registration
            from adapters.persistence.schemas import AuditEvent, AuditEventType, AuditOutcome
            audit_event = AuditEvent(
                event_type=AuditEventType.REGISTER,
                source_id=request.identity,
                target_id=None,
                action="register",
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "agent_id": agent_id,
                    "version": request.version,
                    "capabilities": request.capabilities,
                    "operations": request.operations,
                },
            )
            await self.persistence.log_event(audit_event)

            response = AgentRegistrationResponse(
                agent_id=agent_id,
                identity=request.identity,
                version=request.version,
                status=initial_status,
                registered_at=datetime.now(UTC),
            )

            # Publish notification to NATS if client is available
            if self.nats_client and self.nats_client.is_connected:
                await self._publish_agent_registered(request, initial_status)

            return response
        except DuplicateRecordError as e:
            # This should be caught above, but handle it just in case
            raise DuplicateIdentityError(request.identity) from e

    def _validate_registration(self, request: AgentRegistrationRequest) -> None:
        """
        Validate agent registration request.

        Args:
            request: Agent registration request

        Raises:
            ValidationError: If validation fails
        """
        # Validate identity
        if not request.identity or len(request.identity.strip()) == 0:
            raise ValidationError(
                "identity",
                "Identity cannot be empty",
                "Provide a unique identifier like 'sales-agent-1'",
            )

        # Validate version (semantic versioning)
        if not self._is_valid_semver(request.version):
            raise ValidationError(
                "version",
                f"Invalid semantic version: {request.version}",
                "Use format like '1.0.0', '2.1.3', etc.",
            )

        # Validate capabilities
        if not request.capabilities or len(request.capabilities) == 0:
            raise ValidationError(
                "capabilities",
                "Capabilities list cannot be empty",
                "Provide at least one capability",
            )

        # Validate operations
        if not request.operations or len(request.operations) == 0:
            raise ValidationError(
                "operations",
                "Operations list cannot be empty",
                f"Valid operations: {', '.join(ALLOWED_OPERATIONS)}",
            )

        # Check if operations are valid
        invalid_ops = [op for op in request.operations if op not in ALLOWED_OPERATIONS]
        if invalid_ops:
            raise ValidationError(
                "operations",
                f"Invalid operations: {', '.join(invalid_ops)}",
                f"Allowed operations: {', '.join(ALLOWED_OPERATIONS)}",
            )

        # Validate health endpoint URL format
        if not self._is_valid_url(request.health_endpoint):
            raise ValidationError(
                "health_endpoint",
                f"Invalid URL format: {request.health_endpoint}",
                "Use format like 'http://localhost:8001/health'",
            )

    def _is_valid_semver(self, version: str) -> bool:
        """
        Check if version follows semantic versioning pattern.

        Args:
            version: Version string

        Returns:
            True if valid semver, False otherwise
        """
        semver_pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9\-\.]+)?(\+[a-zA-Z0-9\-\.]+)?$"
        return bool(re.match(semver_pattern, version))

    def _is_valid_url(self, url: str) -> bool:
        """
        Check if URL is valid.

        Args:
            url: URL string

        Returns:
            True if valid URL, False otherwise
        """
        url_pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        return bool(re.match(url_pattern, url, re.IGNORECASE))

    async def _perform_health_check(self, endpoint: str) -> str:
        """
        Perform health check on agent endpoint.

        Args:
            endpoint: Health check endpoint URL

        Returns:
            Health status string ('active' or 'offline')
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    endpoint, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Health check passed for {endpoint}")
                        return HealthStatus.ACTIVE.value
                    else:
                        logger.warning(
                            f"Health check returned status {response.status} for {endpoint}"
                        )
                        return HealthStatus.OFFLINE.value
        except asyncio.TimeoutError:
            logger.warning(f"Health check timeout for {endpoint}")
            return HealthStatus.OFFLINE.value
        except Exception as e:
            logger.warning(f"Health check failed for {endpoint}: {e}")
            return HealthStatus.OFFLINE.value

    async def get_agent_details(self, identity: str) -> AgentDetailsResponse:
        """
        Get detailed information about an agent.

        Args:
            identity: Agent identity

        Returns:
            Agent details response

        Raises:
            EntityNotFoundError: If agent not found
        """
        agent = await self.persistence.get_agent(identity)
        if not agent:
            from .exceptions import EntityNotFoundError

            raise EntityNotFoundError("Agent", identity)

        return AgentDetailsResponse(
            agent_id=agent.id,
            identity=agent.identity,
            version=agent.version,
            capabilities=agent.capabilities,
            operations=agent.operations,
            schemas=agent.schemas,
            health_endpoint=agent.health_endpoint,
            status=agent.status.value,
            registered_at=agent.registered_at,
            last_heartbeat=agent.last_heartbeat,
            metadata=agent.metadata,
        )

    async def update_agent_capabilities(
        self, identity: str, capabilities: list[str]
    ) -> AgentDetailsResponse:
        """
        Update agent capabilities and broadcast notification.

        Args:
            identity: Agent identity
            capabilities: New list of capabilities

        Returns:
            Updated agent details

        Raises:
            EntityNotFoundError: If agent not found
        """
        # Get existing agent
        agent = await self.persistence.get_agent(identity)
        if not agent:
            from .exceptions import EntityNotFoundError

            raise EntityNotFoundError("Agent", identity)

        # Store old capabilities for notification
        old_capabilities = agent.capabilities

        # Update capabilities in persistence
        await self.persistence.update_agent_capabilities(identity, capabilities)
        logger.info(
            f"Agent '{identity}' capabilities updated from {old_capabilities} to {capabilities}"
        )

        # Publish notification if NATS is available
        if self.nats_client and self.nats_client.is_connected:
            await self._publish_agent_capability_updated(
                identity, agent.version, old_capabilities, capabilities
            )

        # Return updated details
        return await self.get_agent_details(identity)

    async def deregister_agent(self, identity: str) -> None:
        """
        Remove an agent from the registry.

        Args:
            identity: Agent identity

        Raises:
            EntityNotFoundError: If agent not found
        """
        agent = await self.persistence.get_agent(identity)
        if not agent:
            from .exceptions import EntityNotFoundError

            raise EntityNotFoundError("Agent", identity)

        await self.persistence.deregister_agent(identity)
        logger.info(f"Agent '{identity}' deregistered successfully")

    async def _publish_agent_registered(
        self, request: AgentRegistrationRequest, status: str
    ) -> None:
        """
        Publish agent registration notification to NATS.

        Args:
            request: Agent registration request
            status: Health status
        """
        if self.nats_client is None:
            return

        try:
            notification = {
                "type": "agent_registered",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {
                    "identity": request.identity,
                    "version": request.version,
                    "capabilities": request.capabilities,
                    "operations": request.operations,
                    "status": status,
                },
            }
            await self.nats_client.publish("mesh.directory.updates", notification)
            logger.debug(
                f"Published agent registration notification for {request.identity}"
            )
        except Exception as e:
            logger.error(f"Failed to publish agent registration notification: {e}")

    async def _publish_agent_capability_updated(
        self,
        identity: str,
        version: str,
        old_capabilities: list[str],
        new_capabilities: list[str],
    ) -> None:
        """
        Publish agent capability update notification to NATS.

        Args:
            identity: Agent identity
            version: Agent version
            old_capabilities: Previous capabilities
            new_capabilities: Updated capabilities
        """
        if self.nats_client is None:
            return

        try:
            notification = {
                "type": "agent_capability_updated",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {
                    "identity": identity,
                    "version": version,
                    "old_capabilities": old_capabilities,
                    "capabilities": new_capabilities,
                },
            }
            await self.nats_client.publish("mesh.directory.updates", notification)
            logger.debug(
                f"Published agent capability update notification for {identity}"
            )
        except Exception as e:
            logger.error(f"Failed to publish agent capability update notification: {e}")
