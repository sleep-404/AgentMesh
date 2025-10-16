"""OPA (Open Policy Agent) client for policy evaluation."""

import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OPAClient:
    """Client for interacting with OPA policy engine."""

    def __init__(
        self,
        url: str = "http://localhost:8181",
        timeout: int = 5,
        policies_dir: str = "policies",
    ):
        """Initialize OPA client.

        Args:
            url: OPA server URL (default: http://localhost:8181)
            timeout: Request timeout in seconds (default: 5)
            policies_dir: Directory to persist policy files (default: policies)
        """
        self.url = url
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self.policies_dir = Path(policies_dir)

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

    async def get_policy(self, policy_id: str) -> dict[str, Any]:
        """Get a specific policy by ID.

        Args:
            policy_id: Policy identifier

        Returns:
            Policy content and metadata
        """
        try:
            response = await self.client.get(f"{self.url}/v1/policies/{policy_id}")
            response.raise_for_status()
            policy: dict[str, Any] = response.json()
            return policy
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"error": f"Policy '{policy_id}' not found"}
            logger.error(f"Failed to get policy {policy_id}: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Failed to get policy {policy_id}: {e}")
            return {"error": str(e)}

    async def get_policy_content(self, policy_id: str) -> dict[str, Any]:
        """Get just the policy content (raw Rego code) by ID.

        Args:
            policy_id: Policy identifier

        Returns:
            Dictionary with policy_id, content, and success status
        """
        try:
            policy = await self.get_policy(policy_id)

            if "error" in policy:
                return policy

            # Extract raw content from OPA response
            raw_content = policy.get("result", {}).get("raw", "")

            return {
                "success": True,
                "policy_id": policy_id,
                "content": raw_content,
                "size": len(raw_content),
            }
        except Exception as e:
            logger.error(f"Failed to get policy content {policy_id}: {e}")
            return {"success": False, "error": str(e)}

    async def upload_policy(
        self, policy_id: str, policy_content: str, persist: bool = True
    ) -> dict[str, Any]:
        """Upload or update a policy in OPA and optionally persist to disk.

        Args:
            policy_id: Unique policy identifier (e.g., 'agentmesh' or 'my-custom-policy')
            policy_content: Rego policy content as string
            persist: Whether to save policy to disk for persistence (default: True)

        Returns:
            Success/error status with file path if persisted
        """
        try:
            # Upload to OPA
            response = await self.client.put(
                f"{self.url}/v1/policies/{policy_id}",
                content=policy_content,
                headers={"Content-Type": "text/plain"},
            )
            response.raise_for_status()

            logger.info(f"Successfully uploaded policy to OPA: {policy_id}")

            # Persist to disk if requested
            file_path = None
            if persist:
                try:
                    # Ensure policies directory exists
                    self.policies_dir.mkdir(parents=True, exist_ok=True)

                    # Save to file
                    policy_file = self.policies_dir / f"{policy_id}.rego"
                    policy_file.write_text(policy_content)
                    file_path = str(policy_file)

                    logger.info(f"Policy persisted to disk: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to persist policy to disk: {e}")
                    # Continue - policy is still uploaded to OPA

            return {
                "success": True,
                "message": f"Policy '{policy_id}' uploaded successfully"
                + (f" and saved to {file_path}" if file_path else ""),
                "policy_id": policy_id,
                "file_path": file_path,
                "persisted": persist and file_path is not None,
            }
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            logger.error(f"Failed to upload policy {policy_id}: {error_detail}")
            return {
                "success": False,
                "error": f"Failed to upload policy: {error_detail}",
            }
        except Exception as e:
            logger.error(f"Failed to upload policy {policy_id}: {e}")
            return {"success": False, "error": str(e)}

    async def delete_policy(
        self, policy_id: str, delete_file: bool = True
    ) -> dict[str, Any]:
        """Delete a policy from OPA and optionally from disk.

        Args:
            policy_id: Policy identifier to delete
            delete_file: Whether to also delete the policy file from disk (default: True)

        Returns:
            Success/error status
        """
        try:
            # Delete from OPA
            response = await self.client.delete(f"{self.url}/v1/policies/{policy_id}")
            response.raise_for_status()

            logger.info(f"Successfully deleted policy from OPA: {policy_id}")

            # Delete from disk if requested
            file_deleted = False
            if delete_file:
                try:
                    policy_file = self.policies_dir / f"{policy_id}.rego"
                    if policy_file.exists():
                        policy_file.unlink()
                        file_deleted = True
                        logger.info(f"Policy file deleted: {policy_file}")
                except Exception as e:
                    logger.warning(f"Failed to delete policy file: {e}")

            return {
                "success": True,
                "message": f"Policy '{policy_id}' deleted successfully"
                + (" (including file)" if file_deleted else ""),
                "file_deleted": file_deleted,
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"success": False, "error": f"Policy '{policy_id}' not found"}
            logger.error(f"Failed to delete policy {policy_id}: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Failed to delete policy {policy_id}: {e}")
            return {"success": False, "error": str(e)}
