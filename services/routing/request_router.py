"""Request routing service for orchestrating mesh operations."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.base import BasePersistenceAdapter
from adapters.persistence.schemas import AuditEvent, AuditEventType, AuditOutcome
from services.enforcement.enforcement_service import EnforcementService
from services.enforcement.exceptions import AccessDeniedError
from services.routing.schemas import (
    AgentInvokeRequest,
    AgentInvokeResponse,
    InvocationRecord,
    InvocationStatus,
    KBQueryRequest,
    KBQueryResponse,
)

logger = logging.getLogger(__name__)


class RequestRouter:
    """
    Request routing service that orchestrates policy-enforced routing.

    This service is the central orchestration layer that:
    1. Receives routing requests via NATS or direct calls
    2. Delegates to EnforcementService for policy evaluation
    3. Routes approved requests to appropriate targets
    4. Tracks request lifecycle
    5. Handles completions and notifications

    Architecture:
    - Uses NATS for transport
    - Uses EnforcementService for governance
    - Uses registry for discovery
    - Uses persistence for audit logging
    """

    def __init__(
        self,
        enforcement: EnforcementService,
        persistence: BasePersistenceAdapter,
        nats_client: NATSWrapper,
    ):
        """Initialize request router.

        Args:
            enforcement: Enforcement service for policy evaluation
            persistence: Persistence adapter for registry and audit
            nats_client: NATS client for messaging
        """
        self.enforcement = enforcement
        self.persistence = persistence
        self.nats = nats_client
        self.invocations: dict[str, InvocationRecord] = {}

    async def start(self) -> None:
        """Start the request router and subscribe to routing subjects."""
        logger.info("Starting request router...")

        # Subscribe to routing subjects
        await self.nats.subscribe("mesh.routing.kb_query", self._handle_kb_query_msg)
        await self.nats.subscribe(
            "mesh.routing.agent_invoke", self._handle_agent_invoke_msg
        )
        await self.nats.subscribe(
            "mesh.routing.completion", self._handle_completion_msg
        )

        logger.info("Request router started and listening for requests")

    async def stop(self) -> None:
        """Stop the request router."""
        logger.info("Stopping request router...")
        await self.nats.disconnect()
        logger.info("Request router stopped")

    # ============================================
    # KB QUERY ROUTING (Direct API)
    # ============================================

    async def route_kb_query(self, request: KBQueryRequest) -> KBQueryResponse:
        """
        Route KB query request through enforcement layer.

        This is the main entry point for KB queries, providing full governance:
        1. Policy evaluation via OPA
        2. KB operation execution
        3. Response masking
        4. Audit logging

        Args:
            request: KB query request

        Returns:
            Masked response from KB
        """
        try:
            # Delegate to enforcement service (does policy + execution + masking + audit)
            result = await self.enforcement.enforce_kb_access(
                requester_id=request.requester_id,
                kb_id=request.kb_id,
                operation=request.operation,
                params=request.params,
            )

            return KBQueryResponse(
                status=result["status"],
                data=result["data"],
                masked_fields=result.get("masked_fields", []),
                policy=result.get("policy", ""),
            )

        except AccessDeniedError as e:
            logger.warning(f"KB query denied: {e}")
            return KBQueryResponse(
                status="denied",
                error=str(e),
                policy="Access denied by policy",
            )
        except Exception as e:
            logger.error(f"KB query failed: {e}")
            return KBQueryResponse(
                status="error",
                error=str(e),
            )

    # ============================================
    # AGENT INVOCATION ROUTING (Direct API)
    # ============================================

    async def route_agent_invoke(
        self, request: AgentInvokeRequest
    ) -> AgentInvokeResponse:
        """
        Route agent invocation request through enforcement layer.

        This handles agent-to-agent invocations with:
        1. Policy evaluation via OPA
        2. Tracking ID assignment
        3. Lifecycle tracking
        4. Target agent notification via NATS
        5. Audit logging

        Args:
            request: Agent invocation request

        Returns:
            Invocation response with tracking ID
        """
        try:
            # Step 1: Evaluate policy via enforcement service
            authorization = await self.enforcement.enforce_agent_invoke(
                source_agent_id=request.source_agent_id,
                target_agent_id=request.target_agent_id,
                operation=request.operation,
                payload=request.payload,
            )

            # Step 2: Look up target agent
            target_agent = await self.persistence.get_agent(request.target_agent_id)
            if not target_agent:
                raise Exception(
                    f"Target agent {request.target_agent_id} not found in registry"
                )

            # Step 3: Assign tracking ID
            tracking_id = str(uuid.uuid4())
            started_at = datetime.now(UTC)

            # Step 4: Create invocation record
            invocation = InvocationRecord(
                tracking_id=tracking_id,
                source_agent_id=request.source_agent_id,
                target_agent_id=request.target_agent_id,
                operation=request.operation,
                payload=request.payload,
                status=InvocationStatus.PROCESSING,
                started_at=started_at,
            )
            self.invocations[tracking_id] = invocation

            # Step 5: Forward to target agent via NATS
            await self.nats.publish(
                f"mesh.agent.{target_agent.identity}.invoke",
                {
                    "tracking_id": tracking_id,
                    "source": request.source_agent_id,
                    "operation": request.operation,
                    "payload": request.payload,
                },
            )

            logger.info(
                f"Invocation routed: {request.source_agent_id} -> {request.target_agent_id} "
                f"(tracking_id={tracking_id})"
            )

            # Step 6: Return tracking response
            return AgentInvokeResponse(
                tracking_id=tracking_id,
                status=InvocationStatus.PROCESSING,
                source=request.source_agent_id,
                target=request.target_agent_id,
                operation=request.operation,
                policy=authorization.get("policy", ""),
                started_at=started_at,
            )

        except AccessDeniedError as e:
            logger.warning(f"Agent invocation denied: {e}")
            return AgentInvokeResponse(
                tracking_id="",
                status=InvocationStatus.DENIED,
                source=request.source_agent_id,
                target=request.target_agent_id,
                operation=request.operation,
                error=str(e),
                policy="Access denied by policy",
            )
        except Exception as e:
            logger.error(f"Agent invocation failed: {e}")
            return AgentInvokeResponse(
                tracking_id="",
                status=InvocationStatus.FAILED,
                source=request.source_agent_id,
                target=request.target_agent_id,
                operation=request.operation,
                error=str(e),
            )

    async def get_invocation_status(
        self, tracking_id: str
    ) -> AgentInvokeResponse | None:
        """
        Get status of an invocation by tracking ID.

        Args:
            tracking_id: Tracking ID of the invocation

        Returns:
            Invocation response or None if not found
        """
        invocation = self.invocations.get(tracking_id)
        if not invocation:
            return None

        return AgentInvokeResponse(
            tracking_id=invocation.tracking_id,
            status=invocation.status,
            source=invocation.source_agent_id,
            target=invocation.target_agent_id,
            operation=invocation.operation,
            result=invocation.result,
            error=invocation.error,
            started_at=invocation.started_at,
            completed_at=invocation.completed_at,
        )

    # ============================================
    # NATS MESSAGE HANDLERS
    # ============================================

    async def _handle_kb_query_msg(self, message: dict[str, Any]) -> None:
        """Handle KB query request from NATS."""
        try:
            request = KBQueryRequest(**message)
            response = await self.route_kb_query(request)
            # In a real implementation, would reply to NATS request
            logger.debug(f"KB query response: {response}")
        except Exception as e:
            logger.error(f"Failed to handle KB query message: {e}")

    async def _handle_agent_invoke_msg(self, message: dict[str, Any]) -> None:
        """Handle agent invocation request from NATS."""
        try:
            request = AgentInvokeRequest(**message)
            response = await self.route_agent_invoke(request)
            # In a real implementation, would reply to NATS request
            logger.debug(f"Agent invoke response: {response}")
        except Exception as e:
            logger.error(f"Failed to handle agent invoke message: {e}")

    async def _handle_completion_msg(self, message: dict[str, Any]) -> None:
        """
        Handle completion notification from target agent.

        When an agent completes an invocation, it publishes to mesh.routing.completion.
        This handler updates the invocation record and notifies the source agent.
        """
        try:
            tracking_id = message.get("tracking_id", "")
            status = message.get("status", "complete")
            result = message.get("result")
            error = message.get("error")

            if not tracking_id:
                logger.warning("Completion message missing tracking_id")
                return

            invocation = self.invocations.get(tracking_id)
            if not invocation:
                logger.warning(f"Completion for unknown tracking_id: {tracking_id}")
                return

            # Update invocation record
            invocation.completed_at = datetime.now(UTC)
            if status == "complete":
                invocation.status = InvocationStatus.COMPLETED
                invocation.result = result
            else:
                invocation.status = InvocationStatus.FAILED
                invocation.error = error

            # Log completion event
            await self.persistence.log_event(
                AuditEvent(
                    event_type=AuditEventType.INVOKE,
                    source_id=invocation.source_agent_id,
                    target_id=invocation.target_agent_id,
                    outcome=AuditOutcome.SUCCESS
                    if status == "complete"
                    else AuditOutcome.ERROR,
                    request_metadata={
                        "operation": invocation.operation,
                        "tracking_id": tracking_id,
                        "status": status,
                        "latency_ms": (
                            invocation.completed_at - invocation.started_at
                        ).total_seconds()
                        * 1000,
                    },
                )
            )

            # Notify source agent
            await self.nats.publish(
                f"mesh.agent.{invocation.source_agent_id}.notifications",
                {
                    "type": "invocation_complete",
                    "tracking_id": tracking_id,
                    "status": status,
                    "result": result,
                    "error": error,
                },
            )

            logger.info(f"Invocation completed: {tracking_id} (status={status})")

        except Exception as e:
            logger.error(f"Failed to handle completion message: {e}")
