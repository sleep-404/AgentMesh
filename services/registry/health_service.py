"""
Health monitoring service.

Handles health checks for agents and KBs.
"""
import asyncio
import logging
from datetime import UTC, datetime, timedelta

import aiohttp

from adapters.persistence.base import BasePersistenceAdapter
from adapters.persistence.schemas import HealthStatus, RegistryQuery

from .exceptions import EntityNotFoundError
from .schemas import HealthCheckRequest, HealthCheckResponse

logger = logging.getLogger(__name__)


class HealthService:
    """Service for monitoring health of agents and KBs"""

    def __init__(self, persistence_adapter: BasePersistenceAdapter):
        """
        Initialize health service.

        Args:
            persistence_adapter: Persistence adapter for updating health status
        """
        self.persistence = persistence_adapter
        self._monitoring_task: asyncio.Task | None = None

    async def check_health(self, request: HealthCheckRequest) -> HealthCheckResponse:
        """
        Manually trigger health check for an entity.

        Args:
            request: Health check request

        Returns:
            Health check response

        Raises:
            EntityNotFoundError: If entity not found
        """
        logger.info(f"Checking health for {request.entity_type}: {request.entity_id}")

        if request.entity_type.lower() == "agent":
            return await self._check_agent_health(request.entity_id)
        elif request.entity_type.lower() == "kb":
            return await self._check_kb_health(request.entity_id)
        else:
            raise ValueError(
                f"Invalid entity type: {request.entity_type}. Must be 'agent' or 'kb'"
            )

    async def _check_agent_health(self, identity: str) -> HealthCheckResponse:
        """
        Check health of a specific agent.

        Args:
            identity: Agent identity

        Returns:
            Health check response

        Raises:
            EntityNotFoundError: If agent not found
        """
        agent = await self.persistence.get_agent(identity)
        if not agent:
            raise EntityNotFoundError("Agent", identity)

        start_time = datetime.now(UTC)
        status = HealthStatus.OFFLINE
        error = None
        latency_ms = None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    agent.health_endpoint, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    end_time = datetime.now(UTC)
                    latency_ms = (end_time - start_time).total_seconds() * 1000

                    if response.status == 200:
                        status = HealthStatus.ACTIVE
                    else:
                        status = HealthStatus.DEGRADED
                        error = f"HTTP {response.status}"
        except asyncio.TimeoutError:
            error = "Timeout after 5 seconds"
            status = HealthStatus.OFFLINE
        except Exception as e:
            error = str(e)
            status = HealthStatus.OFFLINE

        # Update status in persistence layer
        await self.persistence.update_agent_status(identity, status.value)

        message = f"Agent is {status.value}"
        if error:
            message += f": {error}"

        return HealthCheckResponse(
            entity_id=identity,
            entity_type="agent",
            status=status.value,
            last_check=datetime.now(UTC),
            latency_ms=latency_ms,
            error=error,
            message=message,
        )

    async def _check_kb_health(self, kb_id: str) -> HealthCheckResponse:
        """
        Check health of a specific KB.

        Args:
            kb_id: KB identifier

        Returns:
            Health check response

        Raises:
            EntityNotFoundError: If KB not found
        """
        kb = await self.persistence.get_kb(kb_id)
        if not kb:
            raise EntityNotFoundError("KB", kb_id)

        start_time = datetime.now(UTC)
        status = HealthStatus.OFFLINE
        error = None
        latency_ms = None

        try:
            # Check connectivity based on KB type
            if kb.kb_type == "postgres":
                status, error = await self._check_postgres_health(kb.endpoint)
            elif kb.kb_type == "neo4j":
                status, error = await self._check_neo4j_health(kb.endpoint, kb.metadata)
            else:
                error = f"Unsupported KB type: {kb.kb_type}"
                status = HealthStatus.OFFLINE

            end_time = datetime.now(UTC)
            latency_ms = (end_time - start_time).total_seconds() * 1000
        except Exception as e:
            error = str(e)
            status = HealthStatus.OFFLINE

        # Update status in persistence layer
        await self.persistence.update_kb_status(kb_id, status.value)

        message = f"KB is {status.value}"
        if error:
            message += f": {error}"

        return HealthCheckResponse(
            entity_id=kb_id,
            entity_type="kb",
            status=status.value,
            last_check=datetime.now(UTC),
            latency_ms=latency_ms,
            error=error,
            message=message,
        )

    async def _check_postgres_health(
        self, endpoint: str
    ) -> tuple[HealthStatus, str | None]:
        """Check PostgreSQL health"""
        try:
            import asyncpg

            conn = await asyncpg.connect(endpoint, timeout=5)
            try:
                await conn.fetchval("SELECT 1")
                return (HealthStatus.ACTIVE, None)
            finally:
                await conn.close()
        except Exception as e:
            return (HealthStatus.OFFLINE, str(e))

    async def _check_neo4j_health(
        self, endpoint: str, credentials: dict[str, str] | None = None
    ) -> tuple[HealthStatus, str | None]:
        """Check Neo4j health"""
        try:
            from neo4j import AsyncGraphDatabase, basic_auth

            # Create auth using basic_auth if credentials provided
            auth = None
            if credentials and "username" in credentials and "password" in credentials:
                auth = basic_auth(credentials["username"], credentials["password"])

            driver = AsyncGraphDatabase.driver(endpoint, auth=auth)
            try:
                async with driver.session() as session:
                    result = await session.run("RETURN 1 as num")
                    await result.single()
                    return (HealthStatus.ACTIVE, None)
            finally:
                await driver.close()
        except Exception as e:
            return (HealthStatus.OFFLINE, str(e))

    async def start_monitoring(self, interval_seconds: int = 30) -> None:
        """
        Start background health monitoring.

        Args:
            interval_seconds: How often to check health (default: 30 seconds)
        """
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Health monitoring is already running")
            return

        logger.info(f"Starting health monitoring (interval: {interval_seconds}s)")
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )

    async def stop_monitoring(self) -> None:
        """Stop background health monitoring"""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.info("Stopping health monitoring")
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

    async def _monitoring_loop(self, interval_seconds: int) -> None:
        """
        Background monitoring loop.

        Args:
            interval_seconds: Check interval
        """
        while True:
            try:
                await self._check_all_entities()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                logger.info("Health monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(interval_seconds)

    async def _check_all_entities(self) -> None:
        """Check health of all registered entities"""
        logger.debug("Running periodic health checks")

        # Check all agents
        agents_query = RegistryQuery(limit=1000)
        agents = await self.persistence.list_agents(agents_query)

        for agent in agents:
            try:
                await self._check_agent_health(agent.identity)
            except Exception as e:
                logger.error(
                    f"Error checking agent {agent.identity}: {e}", exc_info=True
                )

        # Check all KBs
        kbs_query = RegistryQuery(limit=1000)
        kbs = await self.persistence.list_kbs(kbs_query)

        for kb in kbs:
            try:
                await self._check_kb_health(kb.kb_id)
            except Exception as e:
                logger.error(f"Error checking KB {kb.kb_id}: {e}", exc_info=True)

        logger.debug(
            f"Completed health checks for {len(agents)} agents and {len(kbs)} KBs"
        )

    async def get_health_summary(self) -> dict:
        """
        Get health summary for all entities.

        Returns:
            Summary with health statistics
        """
        # Get all agents
        agents_query = RegistryQuery(limit=1000)
        agents = await self.persistence.list_agents(agents_query)

        # Get all KBs
        kbs_query = RegistryQuery(limit=1000)
        kbs = await self.persistence.list_kbs(kbs_query)

        # Classify agents by health status
        now = datetime.now(UTC)
        agent_active = 0
        agent_degraded = 0
        agent_offline = 0

        for agent in agents:
            if agent.status == HealthStatus.ACTIVE:
                # Check if heartbeat is recent
                if agent.last_heartbeat and (now - agent.last_heartbeat) < timedelta(
                    minutes=1
                ):
                    agent_active += 1
                elif agent.last_heartbeat and (now - agent.last_heartbeat) < timedelta(
                    minutes=5
                ):
                    agent_degraded += 1
                else:
                    agent_offline += 1
            elif agent.status == HealthStatus.DEGRADED:
                agent_degraded += 1
            else:
                agent_offline += 1

        # Classify KBs by health status
        kb_active = 0
        kb_degraded = 0
        kb_offline = 0

        for kb in kbs:
            if kb.status == HealthStatus.ACTIVE:
                # Check if last health check is recent
                if kb.last_health_check and (now - kb.last_health_check) < timedelta(
                    minutes=1
                ):
                    kb_active += 1
                elif kb.last_health_check and (now - kb.last_health_check) < timedelta(
                    minutes=5
                ):
                    kb_degraded += 1
                else:
                    kb_offline += 1
            elif kb.status == HealthStatus.DEGRADED:
                kb_degraded += 1
            else:
                kb_offline += 1

        return {
            "agents": {
                "total": len(agents),
                "active": agent_active,
                "degraded": agent_degraded,
                "offline": agent_offline,
            },
            "kbs": {
                "total": len(kbs),
                "active": kb_active,
                "degraded": kb_degraded,
                "offline": kb_offline,
            },
            "timestamp": now.isoformat(),
        }
