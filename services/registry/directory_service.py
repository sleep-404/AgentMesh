"""
Directory query service.

Handles discovery of registered agents and KBs.
"""
import logging

from adapters.persistence.base import BasePersistenceAdapter
from adapters.persistence.schemas import HealthStatus, RegistryQuery

from .schemas import (
    AgentDetailsResponse,
    AgentListRequest,
    AgentListResponse,
    KBDetailsResponse,
    KBListRequest,
    KBListResponse,
)

logger = logging.getLogger(__name__)


class DirectoryService:
    """Service for querying and discovering agents and KBs"""

    def __init__(self, persistence_adapter: BasePersistenceAdapter):
        """
        Initialize directory service.

        Args:
            persistence_adapter: Persistence adapter for querying records
        """
        self.persistence = persistence_adapter

    async def list_agents(self, request: AgentListRequest) -> AgentListResponse:
        """
        List all registered agents with optional filters.

        Args:
            request: Agent list request with filters

        Returns:
            Agent list response
        """
        logger.info("Listing agents with filters")

        # Build query
        query = RegistryQuery(limit=request.limit)

        # Apply status filter
        if request.status_filter:
            try:
                query.status = HealthStatus(request.status_filter)
            except ValueError:
                logger.warning(f"Invalid status filter: {request.status_filter}")

        # Apply capability filter
        if request.capability_filter:
            query.capabilities = [request.capability_filter]

        # Query persistence layer
        agents = await self.persistence.list_agents(query)

        # Convert to response format
        agent_details = [
            AgentDetailsResponse(
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
            for agent in agents
        ]

        filters_applied = {}
        if request.status_filter:
            filters_applied["status"] = request.status_filter
        if request.capability_filter:
            filters_applied["capability"] = request.capability_filter

        return AgentListResponse(
            agents=agent_details,
            total_count=len(agent_details),
            filters_applied=filters_applied,
        )

    async def list_kbs(self, request: KBListRequest) -> KBListResponse:
        """
        List all registered KBs with optional filters.

        Args:
            request: KB list request with filters

        Returns:
            KB list response
        """
        logger.info("Listing KBs with filters")

        # Build query
        query = RegistryQuery(limit=request.limit)

        # Apply status filter
        if request.status_filter:
            try:
                query.status = HealthStatus(request.status_filter)
            except ValueError:
                logger.warning(f"Invalid status filter: {request.status_filter}")

        # Apply type filter
        if request.type_filter:
            query.kb_type = request.type_filter

        # Query persistence layer
        kbs = await self.persistence.list_kbs(query)

        # Convert to response format
        kb_details = [
            KBDetailsResponse(
                kb_record_id=kb.id,
                kb_id=kb.kb_id,
                kb_type=kb.kb_type,
                endpoint=kb.endpoint,
                operations=kb.operations,
                kb_schema=kb.kb_schema,
                health_endpoint=kb.health_endpoint,
                status=kb.status.value,
                registered_at=kb.registered_at,
                last_health_check=kb.last_health_check,
                metadata=kb.metadata,
            )
            for kb in kbs
        ]

        filters_applied = {}
        if request.status_filter:
            filters_applied["status"] = request.status_filter
        if request.type_filter:
            filters_applied["type"] = request.type_filter

        return KBListResponse(
            kbs=kb_details, total_count=len(kb_details), filters_applied=filters_applied
        )

    async def find_agents_by_capability(
        self, capability: str, limit: int = 100
    ) -> list[AgentDetailsResponse]:
        """
        Find agents with specific capability.

        Args:
            capability: Capability to search for
            limit: Maximum results to return

        Returns:
            List of agents with the capability
        """
        query = RegistryQuery(capabilities=[capability], limit=limit)
        agents = await self.persistence.list_agents(query)

        return [
            AgentDetailsResponse(
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
            for agent in agents
        ]

    async def find_kbs_by_type(
        self, kb_type: str, limit: int = 100
    ) -> list[KBDetailsResponse]:
        """
        Find KBs of specific type.

        Args:
            kb_type: Type of KB to search for
            limit: Maximum results to return

        Returns:
            List of KBs of the specified type
        """
        query = RegistryQuery(kb_type=kb_type, limit=limit)
        kbs = await self.persistence.list_kbs(query)

        return [
            KBDetailsResponse(
                kb_record_id=kb.id,
                kb_id=kb.kb_id,
                kb_type=kb.kb_type,
                endpoint=kb.endpoint,
                operations=kb.operations,
                kb_schema=kb.kb_schema,
                health_endpoint=kb.health_endpoint,
                status=kb.status.value,
                registered_at=kb.registered_at,
                last_health_check=kb.last_health_check,
                metadata=kb.metadata,
            )
            for kb in kbs
        ]

    async def get_directory_summary(self) -> dict:
        """
        Get a summary of the directory.

        Returns:
            Summary with counts and statistics
        """
        # Get all agents
        all_agents_query = RegistryQuery(limit=1000)
        agents = await self.persistence.list_agents(all_agents_query)

        # Get all KBs
        all_kbs_query = RegistryQuery(limit=1000)
        kbs = await self.persistence.list_kbs(all_kbs_query)

        # Count by status
        agent_status_counts: dict[str, int] = {}
        for agent in agents:
            status = agent.status.value
            agent_status_counts[status] = agent_status_counts.get(status, 0) + 1

        kb_status_counts: dict[str, int] = {}
        for kb in kbs:
            status = kb.status.value
            kb_status_counts[status] = kb_status_counts.get(status, 0) + 1

        # Count KBs by type
        kb_type_counts: dict[str, int] = {}
        for kb in kbs:
            kb_type_counts[kb.kb_type] = kb_type_counts.get(kb.kb_type, 0) + 1

        return {
            "total_agents": len(agents),
            "total_kbs": len(kbs),
            "agent_status_counts": agent_status_counts,
            "kb_status_counts": kb_status_counts,
            "kb_type_counts": kb_type_counts,
        }
