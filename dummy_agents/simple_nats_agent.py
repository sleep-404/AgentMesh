"""
Simple NATS Agent - Base class for truly agentic testing.

This agent has ZERO knowledge of AgentMesh internals.
It only knows:
- How to connect to NATS
- Which NATS subjects to use
- Message formats for registration, discovery, and queries

This represents how external agents will interact with the mesh.
"""
import asyncio
import json
import logging
from typing import Any

import nats
from nats.aio.client import Client as NATS

logger = logging.getLogger(__name__)


class SimpleNATSAgent:
    """
    A simple agent that interacts with AgentMesh via NATS only.
    
    This agent demonstrates the external agent perspective:
    - No imports from services.* or adapters.*
    - All interactions via NATS subjects
    - Agent identity used as authentication
    - Dynamic discovery of capabilities
    """

    def __init__(self, nats_url: str = "nats://localhost:4222"):
        """
        Initialize agent.
        
        Args:
            nats_url: NATS server URL
        """
        self.nats_url = nats_url
        self.nc: NATS | None = None
        self.identity: str | None = None
        self.subscriptions = []

    async def connect_to_mesh(self) -> None:
        """
        Connect to the mesh via NATS.
        
        This is the ONLY connection method - no direct access to mesh services.
        """
        try:
            self.nc = await nats.connect(self.nats_url)
            logger.info(f"✅ Connected to NATS at {self.nats_url}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to NATS: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from the mesh."""
        if self.nc:
            # Unsubscribe from all subscriptions
            for sub in self.subscriptions:
                await sub.unsubscribe()
            self.subscriptions.clear()

            await self.nc.close()
            logger.info("✅ Disconnected from NATS")

    async def register_with_mesh(
        self,
        identity: str,
        version: str = "1.0.0",
        capabilities: list[str] | None = None,
        operations: list[str] | None = None,
        health_endpoint: str | None = None,
    ) -> dict[str, Any]:
        """
        Register this agent with the mesh via NATS.
        
        Args:
            identity: Unique agent identifier (e.g., "sales-agent-1")
            version: Agent version (semantic versioning)
            capabilities: List of capabilities (e.g., ["query_kb", "invoke_agent"])
            operations: List of operations (e.g., ["query", "invoke"])
            health_endpoint: HTTP health check endpoint
            
        Returns:
            Registration response with agent_id and status
        """
        if not self.nc:
            raise RuntimeError("Not connected to mesh. Call connect_to_mesh() first.")

        capabilities = capabilities or ["query_kb"]
        operations = operations or ["query"]
        health_endpoint = health_endpoint or f"http://localhost:8000/{identity}/health"

        registration_msg = {
            "identity": identity,
            "version": version,
            "capabilities": capabilities,
            "operations": operations,
            "health_endpoint": health_endpoint,
            "schemas": {},
            "metadata": {},
        }

        logger.info(f"📤 Registering agent: {identity}")

        try:
            # Send registration request via NATS request-reply
            response = await self.nc.request(
                "mesh.registry.agent.register",
                json.dumps(registration_msg).encode(),
                timeout=5.0,
            )

            result = json.loads(response.data.decode())

            if "error" in result:
                logger.error(f"❌ Registration failed: {result['error']}")
                raise RuntimeError(f"Registration failed: {result['error']}")

            self.identity = identity
            logger.info(f"✅ Agent registered: {identity} (status: {result.get('status')})")
            return result

        except asyncio.TimeoutError:
            logger.error("❌ Registration timeout - is mesh service running?")
            raise RuntimeError("Registration timeout")

    async def register_kb(
        self,
        kb_id: str,
        kb_type: str,
        endpoint: str,
        operations: list[str],
        kb_schema: dict[str, Any] | None = None,
        credentials: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Register a knowledge base with the mesh via NATS.
        
        Args:
            kb_id: Unique KB identifier
            kb_type: Type of KB (postgres, neo4j, etc.)
            endpoint: Connection endpoint
            operations: Supported operations
            kb_schema: Optional schema definition
            credentials: Optional credentials
            
        Returns:
            Registration response
        """
        if not self.nc:
            raise RuntimeError("Not connected to mesh. Call connect_to_mesh() first.")

        registration_msg = {
            "kb_id": kb_id,
            "kb_type": kb_type,
            "endpoint": endpoint,
            "operations": operations,
            "metadata": {},
        }

        if kb_schema:
            registration_msg["kb_schema"] = kb_schema

        if credentials:
            registration_msg["credentials"] = credentials

        logger.info(f"📤 Registering KB: {kb_id}")

        try:
            response = await self.nc.request(
                "mesh.registry.kb.register",
                json.dumps(registration_msg).encode(),
                timeout=5.0,
            )

            result = json.loads(response.data.decode())

            if "error" in result:
                logger.error(f"❌ KB registration failed: {result['error']}")
                raise RuntimeError(f"KB registration failed: {result['error']}")

            logger.info(f"✅ KB registered: {kb_id} (status: {result.get('status')})")
            return result

        except asyncio.TimeoutError:
            logger.error("❌ KB registration timeout")
            raise RuntimeError("KB registration timeout")

    async def discover_agents(
        self,
        capability_filter: str | None = None,
        status_filter: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        """
        Discover other agents in the mesh via NATS.
        
        Args:
            capability_filter: Optional filter by capability
            status_filter: Optional filter by status (active, offline)
            limit: Maximum results
            
        Returns:
            Dictionary with "agents" list and "total_count"
        """
        if not self.nc:
            raise RuntimeError("Not connected to mesh. Call connect_to_mesh() first.")

        query_msg = {
            "type": "agents",
            "limit": limit,
        }

        if capability_filter:
            query_msg["capability_filter"] = capability_filter

        if status_filter:
            query_msg["status_filter"] = status_filter

        logger.debug(f"📤 Querying directory: {query_msg}")

        try:
            response = await self.nc.request(
                "mesh.directory.query",
                json.dumps(query_msg).encode(),
                timeout=5.0,
            )

            result = json.loads(response.data.decode())

            if "error" in result:
                logger.error(f"❌ Discovery failed: {result['error']}")
                raise RuntimeError(f"Discovery failed: {result['error']}")

            logger.debug(f"✅ Discovered {result.get('total_count', 0)} agents")
            return result

        except asyncio.TimeoutError:
            logger.error("❌ Discovery timeout")
            raise RuntimeError("Discovery timeout")

    async def discover_kbs(
        self,
        type_filter: str | None = None,
        status_filter: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        """
        Discover knowledge bases in the mesh via NATS.
        
        Args:
            type_filter: Optional filter by KB type (postgres, neo4j)
            status_filter: Optional filter by status
            limit: Maximum results
            
        Returns:
            Dictionary with "kbs" list and "total_count"
        """
        if not self.nc:
            raise RuntimeError("Not connected to mesh. Call connect_to_mesh() first.")

        query_msg = {
            "type": "kbs",
            "limit": limit,
        }

        if type_filter:
            query_msg["type_filter"] = type_filter

        if status_filter:
            query_msg["status_filter"] = status_filter

        logger.debug(f"📤 Querying directory for KBs: {query_msg}")

        try:
            response = await self.nc.request(
                "mesh.directory.query",
                json.dumps(query_msg).encode(),
                timeout=5.0,
            )

            result = json.loads(response.data.decode())

            if "error" in result:
                logger.error(f"❌ KB discovery failed: {result['error']}")
                raise RuntimeError(f"KB discovery failed: {result['error']}")

            logger.debug(f"✅ Discovered {result.get('total_count', 0)} KBs")
            return result

        except asyncio.TimeoutError:
            logger.error("❌ KB discovery timeout")
            raise RuntimeError("KB discovery timeout")

    async def query_kb(
        self,
        kb_id: str,
        operation: str,
        params: dict[str, Any],
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """
        Query a knowledge base through the mesh.
        
        The mesh handles:
        - Policy evaluation
        - KB adapter routing
        - Response masking
        - Audit logging
        
        Args:
            kb_id: KB identifier
            operation: Operation name (sql_query, cypher_query, etc.)
            params: Operation parameters
            timeout: Request timeout in seconds
            
        Returns:
            Query response with data and masked_fields
        """
        if not self.nc:
            raise RuntimeError("Not connected to mesh. Call connect_to_mesh() first.")

        if not self.identity:
            raise RuntimeError("Agent not registered. Call register_with_mesh() first.")

        query_msg = {
            "requester_id": self.identity,
            "kb_id": kb_id,
            "operation": operation,
            "params": params,
        }

        logger.info(f"📤 Querying KB: {kb_id} (operation: {operation})")

        try:
            response = await self.nc.request(
                "mesh.routing.kb_query",
                json.dumps(query_msg).encode(),
                timeout=timeout,
            )

            result = json.loads(response.data.decode())

            if result.get("status") == "denied":
                logger.warning(f"🚫 KB query denied: {result.get('error')}")
            elif result.get("status") == "error":
                logger.error(f"❌ KB query failed: {result.get('error')}")
            else:
                logger.info(f"✅ KB query successful")

            return result

        except asyncio.TimeoutError:
            logger.error("❌ KB query timeout")
            raise RuntimeError("KB query timeout")

    async def invoke_agent(
        self,
        target_agent_id: str,
        operation: str,
        payload: dict[str, Any],
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """
        Invoke another agent through the mesh.
        
        The mesh handles:
        - Policy evaluation
        - Tracking ID assignment
        - Target agent notification
        - Lifecycle tracking
        
        Args:
            target_agent_id: Target agent identifier
            operation: Operation to invoke
            payload: Operation payload
            timeout: Request timeout in seconds
            
        Returns:
            Invocation response with tracking_id
        """
        if not self.nc:
            raise RuntimeError("Not connected to mesh. Call connect_to_mesh() first.")

        if not self.identity:
            raise RuntimeError("Agent not registered. Call register_with_mesh() first.")

        invoke_msg = {
            "source_agent_id": self.identity,
            "target_agent_id": target_agent_id,
            "operation": operation,
            "payload": payload,
        }

        logger.info(f"📤 Invoking agent: {target_agent_id} (operation: {operation})")

        try:
            response = await self.nc.request(
                "mesh.routing.agent_invoke",
                json.dumps(invoke_msg).encode(),
                timeout=timeout,
            )

            result = json.loads(response.data.decode())

            if result.get("status") == "denied":
                logger.warning(f"🚫 Agent invocation denied: {result.get('error')}")
            elif result.get("status") == "error":
                logger.error(f"❌ Agent invocation failed: {result.get('error')}")
            else:
                logger.info(
                    f"✅ Agent invocation initiated (tracking_id: {result.get('tracking_id')})"
                )

            return result

        except asyncio.TimeoutError:
            logger.error("❌ Agent invocation timeout")
            raise RuntimeError("Agent invocation timeout")

    async def subscribe_to_directory_updates(self, callback) -> None:
        """
        Subscribe to directory updates (new agents/KBs registered).
        
        Args:
            callback: Async callback function(message: dict)
        """
        if not self.nc:
            raise RuntimeError("Not connected to mesh. Call connect_to_mesh() first.")

        async def handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await callback(data)
            except Exception as e:
                logger.error(f"❌ Error in directory update handler: {e}")

        sub = await self.nc.subscribe("mesh.directory.updates", cb=handler)
        self.subscriptions.append(sub)
        logger.info("✅ Subscribed to directory updates")

    async def subscribe_to_invocations(self, callback) -> None:
        """
        Subscribe to invocation requests for this agent.
        
        Args:
            callback: Async callback function(message: dict)
        """
        if not self.nc:
            raise RuntimeError("Not connected to mesh. Call connect_to_mesh() first.")

        if not self.identity:
            raise RuntimeError("Agent not registered. Call register_with_mesh() first.")

        async def handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await callback(data)
            except Exception as e:
                logger.error(f"❌ Error in invocation handler: {e}")

        subject = f"mesh.agent.{self.identity}.invoke"
        sub = await self.nc.subscribe(subject, cb=handler)
        self.subscriptions.append(sub)
        logger.info(f"✅ Subscribed to invocations on {subject}")

    async def subscribe_to_notifications(self, callback) -> None:
        """
        Subscribe to notifications for this agent.
        
        Args:
            callback: Async callback function(message: dict)
        """
        if not self.nc:
            raise RuntimeError("Not connected to mesh. Call connect_to_mesh() first.")

        if not self.identity:
            raise RuntimeError("Agent not registered. Call register_with_mesh() first.")

        async def handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await callback(data)
            except Exception as e:
                logger.error(f"❌ Error in notification handler: {e}")

        subject = f"mesh.agent.{self.identity}.notifications"
        sub = await self.nc.subscribe(subject, cb=handler)
        self.subscriptions.append(sub)
        logger.info(f"✅ Subscribed to notifications on {subject}")

    async def send_completion(
        self,
        tracking_id: str,
        status: str = "complete",
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """
        Send completion notification for an invocation.
        
        Args:
            tracking_id: Tracking ID from invocation request
            status: Completion status ("complete" or "failed")
            result: Optional result data
            error: Optional error message
        """
        if not self.nc:
            raise RuntimeError("Not connected to mesh. Call connect_to_mesh() first.")

        completion_msg = {
            "tracking_id": tracking_id,
            "status": status,
        }

        if result:
            completion_msg["result"] = result

        if error:
            completion_msg["error"] = error

        await self.nc.publish(
            "mesh.routing.completion", json.dumps(completion_msg).encode()
        )
        logger.info(f"✅ Sent completion for tracking_id: {tracking_id}")

    async def query_audit_logs(
        self,
        event_type: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
        outcome: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Query audit logs from the mesh.
        
        The mesh handles:
        - Accessing audit logs from persistence
        - Filtering by event type, source, target, outcome, time range
        - Returning audit records with metadata
        
        Args:
            event_type: Filter by event type (query, invoke, register, policy_update, write)
            source_id: Filter by source (agent/user ID)
            target_id: Filter by target (KB/agent ID)
            outcome: Filter by outcome (success, denied, error)
            start_time: Filter by start time (ISO format)
            end_time: Filter by end time (ISO format)
            limit: Maximum results
            
        Returns:
            Dictionary with "audit_logs" list and "total_count"
        """
        if not self.nc:
            raise RuntimeError("Not connected to mesh. Call connect_to_mesh() first.")

        query_msg = {
            "limit": limit,
        }

        if event_type:
            query_msg["event_type"] = event_type

        if source_id:
            query_msg["source_id"] = source_id

        if target_id:
            query_msg["target_id"] = target_id

        if outcome:
            query_msg["outcome"] = outcome

        if start_time:
            query_msg["start_time"] = start_time

        if end_time:
            query_msg["end_time"] = end_time

        logger.info(f"📤 Querying audit logs: {query_msg}")

        try:
            response = await self.nc.request(
                "mesh.audit.query",
                json.dumps(query_msg).encode(),
                timeout=10.0,
            )

            result = json.loads(response.data.decode())

            if "error" in result:
                logger.error(f"❌ Audit query failed: {result['error']}")
                raise RuntimeError(f"Audit query failed: {result['error']}")

            logger.info(f"✅ Audit query successful: {result.get('total_count', 0)} records")
            return result

        except asyncio.TimeoutError:
            logger.error("❌ Audit query timeout")
            raise RuntimeError("Audit query timeout")

