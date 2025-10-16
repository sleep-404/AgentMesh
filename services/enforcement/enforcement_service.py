"""Enforcement service for policy evaluation and data masking."""

import logging
from datetime import UTC, datetime
from typing import Any

from adapters.knowledge_base.neo4j.adapter import Neo4jAdapter
from adapters.knowledge_base.postgres.adapter import PostgresAdapter
from adapters.persistence.base import BasePersistenceAdapter
from adapters.persistence.schemas import AuditEvent, AuditEventType, AuditOutcome
from adapters.policy.opa_client import OPAClient
from services.enforcement.exceptions import AccessDeniedError, MaskingError

logger = logging.getLogger(__name__)


class EnforcementService:
    """
    Enforcement service that orchestrates policy evaluation, KB access, and response masking.

    This service is the key governance layer that:
    1. Evaluates policies using OPA
    2. Executes approved operations on KBs
    3. Applies field-level masking to responses
    4. Logs all operations to audit trail
    """

    def __init__(
        self,
        opa_client: OPAClient,
        persistence: BasePersistenceAdapter,
        kb_adapters: dict[str, PostgresAdapter | Neo4jAdapter],
    ):
        """Initialize enforcement service.

        Args:
            opa_client: OPA client for policy evaluation
            persistence: Persistence adapter for audit logging and registry lookups
            kb_adapters: Dictionary mapping kb_type -> adapter instance
        """
        self.opa = opa_client
        self.persistence = persistence
        self.kb_adapters = kb_adapters

    async def enforce_kb_access(
        self,
        requester_id: str,
        kb_id: str,
        operation: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Enforce KB access with full governance flow.

        Flow:
        1. Look up KB in registry
        2. Evaluate policy using OPA
        3. If denied, log and raise error
        4. If allowed, execute operation on KB
        5. Apply masking to response
        6. Log audit event
        7. Return masked response

        Args:
            requester_id: Agent/user requesting access
            kb_id: Target KB identifier
            operation: Operation to perform (e.g., 'sql_query', 'cypher_query')
            params: Operation parameters

        Returns:
            Masked response from KB

        Raises:
            AccessDeniedError: If policy denies access
            Exception: If KB lookup or operation fails
        """
        start_time = datetime.now(UTC)

        try:
            # Step 1: Look up KB in registry
            kb_record = await self.persistence.get_kb(kb_id)
            if not kb_record:
                await self._log_denied_access(
                    requester_id, kb_id, operation, "KB not found"
                )
                raise AccessDeniedError(f"KB {kb_id} not found in registry")

            # Step 2: Evaluate policy using OPA
            decision = await self.opa.evaluate_policy(
                principal_type="agent",
                principal_id=requester_id,
                resource_type="kb",
                resource_id=kb_id,
                action=operation,
                context={"kb_type": kb_record.kb_type},
            )

            # Step 3: Check if access is allowed
            if not decision.get("allow", False):
                reason = decision.get("reason", "Policy denied access")
                await self._log_denied_access(requester_id, kb_id, operation, reason)
                raise AccessDeniedError(
                    f"Access denied: {reason} (principal={requester_id}, resource={kb_id}, action={operation})"
                )

            # Step 4: Execute operation on KB
            masking_rules = decision.get("masking_rules", [])
            kb_adapter = self.kb_adapters.get(kb_record.kb_type)

            if not kb_adapter:
                raise Exception(f"No adapter found for KB type: {kb_record.kb_type}")

            # Execute the operation
            raw_response = await self._execute_kb_operation(
                kb_adapter, operation, params
            )

            # Step 5: Apply masking to response
            masked_response = self._apply_masking(raw_response, masking_rules)

            # Step 6: Log successful access
            await self._log_successful_access(
                requester_id, kb_id, operation, masking_rules, start_time
            )

            # Step 7: Return masked response
            return {
                "status": "success",
                "data": masked_response,
                "masked_fields": masking_rules,
                "policy": decision.get("reason", ""),
            }

        except AccessDeniedError:
            raise
        except Exception as e:
            logger.error(f"Enforcement failed for {requester_id} -> {kb_id}: {e}")
            await self._log_error(requester_id, kb_id, operation, str(e))
            raise

    async def enforce_agent_invoke(
        self,
        source_agent_id: str,
        target_agent_id: str,
        operation: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Enforce agent-to-agent invocation with policy check.

        Flow:
        1. Evaluate policy using OPA
        2. If denied, log and raise error
        3. If allowed, return approval (actual invocation handled by router)
        4. Log audit event

        Args:
            source_agent_id: Agent requesting invocation
            target_agent_id: Target agent to invoke
            operation: Operation to perform on target
            payload: Operation payload

        Returns:
            Approval response with tracking info

        Raises:
            AccessDeniedError: If policy denies invocation
        """
        try:
            # Step 1: Evaluate policy using OPA
            decision = await self.opa.evaluate_policy(
                principal_type="agent",
                principal_id=source_agent_id,
                resource_type="agent",
                resource_id=target_agent_id,
                action="invoke",
                context={"operation": operation},
            )

            # Step 2: Check if invocation is allowed
            if not decision.get("allow", False):
                reason = decision.get("reason", "Policy denied invocation")
                await self._log_denied_invoke(
                    source_agent_id, target_agent_id, operation, reason
                )
                raise AccessDeniedError(
                    f"Invocation denied: {reason} (source={source_agent_id}, target={target_agent_id})"
                )

            # Step 3: Log successful authorization (actual invocation logged separately)
            await self.persistence.log_event(
                AuditEvent(
                    event_type=AuditEventType.INVOKE,
                    source_id=source_agent_id,
                    target_id=target_agent_id,
                    outcome=AuditOutcome.SUCCESS,
                    request_metadata={
                        "operation": operation,
                        "authorization": "granted",
                    },
                    policy_decision=decision,
                )
            )

            # Step 4: Return approval
            return {
                "status": "authorized",
                "source": source_agent_id,
                "target": target_agent_id,
                "operation": operation,
                "policy": decision.get("reason", ""),
            }

        except AccessDeniedError:
            raise
        except Exception as e:
            logger.error(
                f"Enforcement failed for invocation {source_agent_id} -> {target_agent_id}: {e}"
            )
            await self._log_error(source_agent_id, target_agent_id, "invoke", str(e))
            raise

    async def _execute_kb_operation(
        self,
        kb_adapter: PostgresAdapter | Neo4jAdapter,
        operation: str,
        params: dict[str, Any],
    ) -> Any:
        """Execute operation on KB adapter."""
        # Map operation to adapter method
        if operation in ["sql_query", "query"]:
            return await kb_adapter.execute(
                operation, query=params.get("query", ""), params=params.get("params")
            )
        elif operation == "insert":
            return await kb_adapter.execute(
                operation, table=params.get("table"), data=params.get("data")
            )
        elif operation == "update":
            return await kb_adapter.execute(
                operation,
                table=params.get("table"),
                data=params.get("data"),
                where=params.get("where"),
            )
        elif operation == "delete":
            return await kb_adapter.execute(
                operation, table=params.get("table"), where=params.get("where")
            )
        elif operation == "cypher_query":
            return await kb_adapter.execute(
                operation,
                query=params.get("query", ""),
                parameters=params.get("parameters"),
            )
        elif operation == "create_node":
            return await kb_adapter.execute(
                operation,
                labels=params.get("labels"),
                properties=params.get("properties"),
            )
        elif operation == "create_relationship":
            return await kb_adapter.execute(
                operation,
                from_node_query=params.get("from_node_query"),
                to_node_query=params.get("to_node_query"),
                relationship_type=params.get("relationship_type"),
                properties=params.get("properties"),
            )
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    def _apply_masking(self, data: Any, masking_rules: list[str]) -> Any:
        """
        Apply field-level masking to response data.

        Args:
            data: Raw data from KB (can be dict, list, or primitive)
            masking_rules: List of field names to mask

        Returns:
            Data with masked fields
        """
        if not masking_rules:
            return data

        try:
            # Handle different data types
            if isinstance(data, dict):
                return self._mask_dict(data, masking_rules)
            elif isinstance(data, list):
                return [self._apply_masking(item, masking_rules) for item in data]
            else:
                return data
        except Exception as e:
            logger.error(f"Failed to apply masking: {e}")
            raise MaskingError(f"Masking failed: {e}") from e

    def _mask_dict(
        self, data: dict[str, Any], masking_rules: list[str]
    ) -> dict[str, Any]:
        """Mask fields in a dictionary."""
        masked: dict[str, Any] = {}
        for key, value in data.items():
            if key in masking_rules:
                masked[key] = "[REDACTED]"
            elif isinstance(value, dict):
                masked[key] = self._mask_dict(value, masking_rules)
            elif isinstance(value, list):
                masked[key] = [
                    self._apply_masking(item, masking_rules) for item in value
                ]
            else:
                masked[key] = value
        return masked

    async def _log_denied_access(
        self, requester_id: str, kb_id: str, operation: str, reason: str
    ) -> None:
        """Log denied KB access."""
        await self.persistence.log_event(
            AuditEvent(
                event_type=AuditEventType.QUERY,
                source_id=requester_id,
                target_id=kb_id,
                outcome=AuditOutcome.DENIED,
                request_metadata={"operation": operation, "reason": reason},
            )
        )

    async def _log_successful_access(
        self,
        requester_id: str,
        kb_id: str,
        operation: str,
        masked_fields: list[str],
        start_time: datetime,
    ) -> None:
        """Log successful KB access."""
        latency = (datetime.now(UTC) - start_time).total_seconds() * 1000
        await self.persistence.log_event(
            AuditEvent(
                event_type=AuditEventType.QUERY,
                source_id=requester_id,
                target_id=kb_id,
                outcome=AuditOutcome.SUCCESS,
                request_metadata={"operation": operation, "latency_ms": latency},
                masked_fields=masked_fields,
            )
        )

    async def _log_denied_invoke(
        self, source_id: str, target_id: str, operation: str, reason: str
    ) -> None:
        """Log denied agent invocation."""
        await self.persistence.log_event(
            AuditEvent(
                event_type=AuditEventType.INVOKE,
                source_id=source_id,
                target_id=target_id,
                outcome=AuditOutcome.DENIED,
                request_metadata={"operation": operation, "reason": reason},
            )
        )

    async def _log_error(
        self, source_id: str, target_id: str, operation: str, error: str
    ) -> None:
        """Log error during enforcement."""
        await self.persistence.log_event(
            AuditEvent(
                event_type=AuditEventType.QUERY,
                source_id=source_id,
                target_id=target_id,
                outcome=AuditOutcome.ERROR,
                request_metadata={"operation": operation, "error": error},
            )
        )
