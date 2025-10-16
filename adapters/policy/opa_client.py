"""OPA (Open Policy Agent) client for policy evaluation."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OPAClient:
    """Client for interacting with OPA policy engine."""

    def __init__(self, url: str = "http://localhost:8181", timeout: int = 5):
        """Initialize OPA client.

        Args:
            url: OPA server URL (default: http://localhost:8181)
            timeout: Request timeout in seconds (default: 5)
        """
        self.url = url
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def evaluate_policy(
        self,
        principal_type: str,
        principal_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate policy using OPA.

        Args:
            principal_type: Type of principal (e.g., 'agent', 'user')
            principal_id: Unique identifier of the principal
            resource_type: Type of resource (e.g., 'kb', 'agent')
            resource_id: Unique identifier of the resource
            action: Action being performed (e.g., 'read', 'write', 'invoke')
            context: Optional additional context for policy evaluation

        Returns:
            Policy decision with structure:
            {
                "allow": bool,
                "masking_rules": list[str],
                "reason": str
            }

        Raises:
            Exception: If OPA is unreachable or returns an error
        """
        try:
            # Build input for OPA
            opa_input: dict[str, Any] = {
                "principal_type": principal_type,
                "principal_id": principal_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
            }

            # Add optional context
            if context:
                opa_input["context"] = context

            # Query OPA decision endpoint
            response = await self.client.post(
                f"{self.url}/v1/data/agentmesh/decision",
                json={"input": opa_input},
            )
            response.raise_for_status()

            result = response.json()
            decision: dict[str, Any] = result.get("result", {})

            logger.debug(
                f"OPA decision for {principal_id} -> {resource_id}.{action}: {decision}"
            )

            return decision

        except httpx.TimeoutException:
            logger.error(f"OPA request timed out after {self.timeout}s")
            # Default deny on timeout
            return {
                "allow": False,
                "masking_rules": [],
                "reason": "Policy evaluation timed out (default deny)",
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"OPA returned error status {e.response.status_code}: {e}")
            # Default deny on error
            return {
                "allow": False,
                "masking_rules": [],
                "reason": f"Policy evaluation failed: {e}",
            }
        except Exception as e:
            logger.error(f"Failed to evaluate policy: {e}")
            # Default deny on any error
            return {
                "allow": False,
                "masking_rules": [],
                "reason": f"Policy evaluation error: {e}",
            }

    async def health_check(self) -> bool:
        """Check if OPA server is healthy.

        Returns:
            True if OPA is reachable and healthy, False otherwise
        """
        try:
            response = await self.client.get(f"{self.url}/health")
            is_healthy: bool = response.status_code == 200
            return is_healthy
        except Exception as e:
            logger.error(f"OPA health check failed: {e}")
            return False

    async def list_policies(self) -> dict[str, Any]:
        """List all loaded policies in OPA.

        Returns:
            Dictionary of loaded policies
        """
        try:
            response = await self.client.get(f"{self.url}/v1/policies")
            response.raise_for_status()
            policies: dict[str, Any] = response.json()
            return policies
        except Exception as e:
            logger.error(f"Failed to list OPA policies: {e}")
            return {"result": []}
