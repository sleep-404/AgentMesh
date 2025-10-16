"""
Standalone AgentMesh service.

This service runs ALL mesh infrastructure in one process:
- Persistence layer (SQLite)
- NATS messaging
- Policy enforcement (OPA)
- Registry services (Agent, KB, Directory)
- Routing service
- Directory subscriber

Agents connect to this service via NATS only - they have ZERO knowledge of internals.
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from adapters.policy.opa_client import OPAClient
from services.enforcement.enforcement_service import EnforcementService
from services.registry.agent_service import AgentService
from services.registry.directory_service import DirectoryService
from services.registry.kb_service import KBService
from services.registry.schemas import (
    AgentListRequest,
    AgentRegistrationRequest,
    KBListRequest,
    KBRegistrationRequest,
)
from services.routing.request_router import RequestRouter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class MeshService:
    """
    Standalone mesh service that agents connect to via NATS.
    
    This service encapsulates all mesh internals and exposes only NATS subjects.
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        opa_url: str = "http://localhost:8181",
        persistence_config_path: str = "adapters/persistence/sqlite/config.yaml",
    ):
        """
        Initialize mesh service.
        
        Args:
            nats_url: NATS server URL
            opa_url: OPA server URL
            persistence_config_path: Path to persistence adapter config file
        """
        self.nats_url = nats_url
        self.opa_url = opa_url
        self.persistence_config_path = persistence_config_path

        # Core components (initialized in start())
        self.nats_client: NATSWrapper | None = None
        self.persistence: SQLitePersistenceAdapter | None = None
        self.opa_client: OPAClient | None = None
        self.kb_adapters: dict = {}
        
        # Services
        self.agent_service: AgentService | None = None
        self.kb_service: KBService | None = None
        self.directory_service: DirectoryService | None = None
        self.enforcement_service: EnforcementService | None = None
        self.request_router: RequestRouter | None = None

        self._running = False

    async def start(self) -> None:
        """Start all mesh services and subscribe to NATS subjects."""
        logger.info("🚀 Starting AgentMesh Service...")

        try:
            # Step 1: Initialize persistence
            logger.info("📊 Initializing persistence layer...")
            self.persistence = SQLitePersistenceAdapter(self.persistence_config_path)
            await self.persistence.connect()
            logger.info("✅ Persistence initialized")

            # Step 2: Initialize NATS
            logger.info("📡 Connecting to NATS...")
            self.nats_client = NATSWrapper(self.nats_url)
            await self.nats_client.connect()
            logger.info(f"✅ Connected to NATS at {self.nats_url}")

            # Step 3: Initialize OPA
            logger.info("🔒 Connecting to OPA...")
            self.opa_client = OPAClient(self.opa_url)
            logger.info(f"✅ Connected to OPA at {self.opa_url}")

            # Step 4: Initialize KB adapters (empty dict - will be populated when KBs register)
            logger.info("🗄️  Initializing KB adapters...")
            self.kb_adapters = {}
            logger.info("✅ KB adapters initialized")

            # Step 5: Initialize services
            logger.info("⚙️  Initializing mesh services...")
            
            self.agent_service = AgentService(
                persistence_adapter=self.persistence,
                nats_client=self.nats_client,
            )
            
            self.kb_service = KBService(
                persistence_adapter=self.persistence,
                nats_client=self.nats_client,
            )
            
            self.directory_service = DirectoryService(
                persistence_adapter=self.persistence,
            )
            
            self.enforcement_service = EnforcementService(
                opa_client=self.opa_client,
                persistence=self.persistence,
                kb_adapters=self.kb_adapters,
            )
            
            self.request_router = RequestRouter(
                enforcement=self.enforcement_service,
                persistence=self.persistence,
                nats_client=self.nats_client,
            )
            
            logger.info("✅ All services initialized")

            # Step 6: Start request router (subscribes to routing subjects)
            logger.info("🔀 Starting request router...")
            await self.request_router.start()
            logger.info("✅ Request router started")

            # Step 7: Subscribe to NATS subjects for registration and discovery
            logger.info("📡 Subscribing to mesh subjects...")
            await self._subscribe_to_subjects()
            logger.info("✅ Subscribed to all mesh subjects")

            self._running = True
            logger.info("✅ AgentMesh Service is ready!")
            logger.info("📡 Agents can now connect via NATS subjects:")
            logger.info("   - mesh.registry.agent.register")
            logger.info("   - mesh.registry.kb.register")
            logger.info("   - mesh.directory.query")
            logger.info("   - mesh.routing.kb_query")
            logger.info("   - mesh.routing.agent_invoke")
            logger.info("   - mesh.audit.query")

        except Exception as e:
            logger.error(f"❌ Failed to start mesh service: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop all mesh services and cleanup."""
        logger.info("🛑 Stopping AgentMesh Service...")
        self._running = False

        if self.request_router:
            await self.request_router.stop()

        if self.nats_client:
            await self.nats_client.disconnect()

        if self.persistence:
            await self.persistence.disconnect()

        logger.info("✅ AgentMesh Service stopped")

    async def _subscribe_to_subjects(self) -> None:
        """Subscribe to NATS subjects for agent/KB registration and discovery."""
        if not self.nats_client or not self.nats_client.nc:
            raise RuntimeError("NATS client not initialized")

        # Agent registration (request-reply)
        await self.nats_client.nc.subscribe(
            "mesh.registry.agent.register",
            cb=self._handle_agent_registration,
        )

        # KB registration (request-reply)
        await self.nats_client.nc.subscribe(
            "mesh.registry.kb.register",
            cb=self._handle_kb_registration,
        )

        # Directory query (request-reply)
        await self.nats_client.nc.subscribe(
            "mesh.directory.query",
            cb=self._handle_directory_query,
        )

        # Health check (request-reply)
        await self.nats_client.nc.subscribe(
            "mesh.health",
            cb=self._handle_health_check,
        )

        # Audit query (request-reply)
        await self.nats_client.nc.subscribe(
            "mesh.audit.query",
            cb=self._handle_audit_query,
        )

    # ============================================
    # NATS REQUEST-REPLY HANDLERS
    # ============================================

    async def _handle_agent_registration(self, msg) -> None:
        """Handle agent registration request from NATS."""
        try:
            # Parse request
            request_data = json.loads(msg.data.decode())
            logger.info(f"📥 Received agent registration: {request_data.get('identity')}")

            # Create registration request
            request = AgentRegistrationRequest(
                identity=request_data.get("identity", ""),
                version=request_data.get("version", ""),
                capabilities=request_data.get("capabilities", []),
                operations=request_data.get("operations", []),
                health_endpoint=request_data.get("health_endpoint", ""),
                schemas=request_data.get("schemas") or {},
                metadata=request_data.get("metadata") or {},
            )

            # Register agent via service
            response = await self.agent_service.register_agent(request)

            # Send response
            response_data = {
                "agent_id": response.agent_id,
                "identity": response.identity,
                "version": response.version,
                "status": response.status,
                "registered_at": response.registered_at.isoformat(),
            }

            await self.nats_client.nc.publish(
                msg.reply, json.dumps(response_data).encode()
            )
            logger.info(f"✅ Agent registered: {response.identity} (status: {response.status})")

        except Exception as e:
            logger.error(f"❌ Agent registration failed: {e}")
            error_response = {
                "error": str(e),
                "message": "Agent registration failed",
            }
            await self.nats_client.nc.publish(
                msg.reply, json.dumps(error_response).encode()
            )

    async def _handle_kb_registration(self, msg) -> None:
        """Handle KB registration request from NATS."""
        try:
            # Parse request
            request_data = json.loads(msg.data.decode())
            logger.info(f"📥 Received KB registration: {request_data.get('kb_id')}")

            # Create registration request
            request = KBRegistrationRequest(
                kb_id=request_data.get("kb_id", ""),
                kb_type=request_data.get("kb_type", ""),
                endpoint=request_data.get("endpoint", ""),
                operations=request_data.get("operations", []),
                kb_schema=request_data.get("kb_schema") or {},
                credentials=request_data.get("credentials") or {},
                metadata=request_data.get("metadata") or {},
            )

            # Register KB via service
            response = await self.kb_service.register_kb(request)

            # Send response
            response_data = {
                "kb_id": response.kb_id,
                "kb_type": response.kb_type,
                "status": response.status,
                "registered_at": response.registered_at.isoformat(),
                "message": response.message,
            }

            await self.nats_client.nc.publish(
                msg.reply, json.dumps(response_data).encode()
            )
            logger.info(f"✅ KB registered: {response.kb_id} (status: {response.status})")

        except Exception as e:
            logger.error(f"❌ KB registration failed: {e}")
            error_response = {
                "error": str(e),
                "message": "KB registration failed",
            }
            await self.nats_client.nc.publish(
                msg.reply, json.dumps(error_response).encode()
            )

    async def _handle_directory_query(self, msg) -> None:
        """Handle directory query request from NATS."""
        try:
            # Parse request
            request_data = json.loads(msg.data.decode())
            query_type = request_data.get("type", "agents")
            logger.debug(f"📥 Received directory query: type={query_type}")

            if query_type == "agents":
                # List agents
                request = AgentListRequest(
                    capability_filter=request_data.get("capability_filter"),
                    status_filter=request_data.get("status_filter"),
                    limit=request_data.get("limit", 1000),
                )
                response = await self.directory_service.list_agents(request)

                response_data = {
                    "agents": [
                        {
                            "agent_id": agent.agent_id,
                            "identity": agent.identity,
                            "version": agent.version,
                            "capabilities": agent.capabilities,
                            "operations": agent.operations,
                            "status": agent.status,
                            "registered_at": agent.registered_at.isoformat(),
                        }
                        for agent in response.agents
                    ],
                    "total_count": response.total_count,
                    "filters_applied": response.filters_applied,
                }

            elif query_type == "kbs":
                # List KBs
                request = KBListRequest(
                    type_filter=request_data.get("type_filter"),
                    status_filter=request_data.get("status_filter"),
                    limit=request_data.get("limit", 1000),
                )
                response = await self.directory_service.list_kbs(request)

                response_data = {
                    "kbs": [
                        {
                            "kb_id": kb.kb_id,
                            "kb_type": kb.kb_type,
                            "operations": kb.operations,
                            "status": kb.status,
                            "registered_at": kb.registered_at.isoformat(),
                        }
                        for kb in response.kbs
                    ],
                    "total_count": response.total_count,
                    "filters_applied": response.filters_applied,
                }

            else:
                raise ValueError(f"Unknown query type: {query_type}")

            await self.nats_client.nc.publish(
                msg.reply, json.dumps(response_data).encode()
            )
            logger.debug(f"✅ Directory query completed: {query_type}")

        except Exception as e:
            logger.error(f"❌ Directory query failed: {e}")
            error_response = {
                "error": str(e),
                "message": "Directory query failed",
            }
            await self.nats_client.nc.publish(
                msg.reply, json.dumps(error_response).encode()
            )

    async def _handle_health_check(self, msg) -> None:
        """Handle health check request from NATS."""
        try:
            health_data = {
                "status": "healthy",
                "services": {
                    "persistence": self.persistence is not None,
                    "nats": self.nats_client is not None and self.nats_client.is_connected,
                    "opa": self.opa_client is not None,
                    "router": self.request_router is not None,
                },
            }
            await self.nats_client.nc.publish(
                msg.reply, json.dumps(health_data).encode()
            )
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")

    async def _handle_audit_query(self, msg) -> None:
        """Handle audit log query request from NATS."""
        try:
            from adapters.persistence.schemas import AuditQuery, AuditEventType, AuditOutcome
            from datetime import datetime
            
            # Parse request
            request_data = json.loads(msg.data.decode())
            logger.debug(f"📥 Received audit query: {request_data}")

            # Build audit query
            query_params = {
                "limit": request_data.get("limit", 100),
            }
            
            if request_data.get("event_type"):
                query_params["event_type"] = AuditEventType(request_data["event_type"])
            
            if request_data.get("source_id"):
                query_params["source_id"] = request_data["source_id"]
            
            if request_data.get("target_id"):
                query_params["target_id"] = request_data["target_id"]
            
            if request_data.get("outcome"):
                query_params["outcome"] = AuditOutcome(request_data["outcome"])
            
            if request_data.get("start_time"):
                query_params["start_time"] = datetime.fromisoformat(request_data["start_time"])
            
            if request_data.get("end_time"):
                query_params["end_time"] = datetime.fromisoformat(request_data["end_time"])
            
            query = AuditQuery(**query_params)
            
            # Query audit logs via persistence
            audit_records = await self.persistence.query_audit_logs(query)

            # Build response
            response_data = {
                "audit_logs": [
                    {
                        "id": record.id,
                        "event_type": record.event_type.value,
                        "source_id": record.source_id,
                        "target_id": record.target_id,
                        "outcome": record.outcome.value,
                        "timestamp": record.timestamp.isoformat(),
                        "request_metadata": record.request_metadata,
                        "policy_decision": record.policy_decision,
                        "masked_fields": record.masked_fields,
                    }
                    for record in audit_records
                ],
                "total_count": len(audit_records),
                "filters_applied": {
                    k: v.value if hasattr(v, "value") else (v.isoformat() if hasattr(v, "isoformat") else v)
                    for k, v in query_params.items()
                },
            }

            await self.nats_client.nc.publish(
                msg.reply, json.dumps(response_data).encode()
            )
            logger.debug(f"✅ Audit query completed: {len(audit_records)} records")

        except Exception as e:
            logger.error(f"❌ Audit query failed: {e}")
            error_response = {
                "error": str(e),
                "message": "Audit query failed",
            }
            await self.nats_client.nc.publish(
                msg.reply, json.dumps(error_response).encode()
            )

    async def run_forever(self) -> None:
        """Run the service until interrupted."""
        try:
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal")
        finally:
            await self.stop()


async def main():
    """Main entry point for standalone mesh service."""
    # Parse environment variables
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    opa_url = os.getenv("OPA_URL", "http://localhost:8181")
    persistence_config = os.getenv("PERSISTENCE_CONFIG", "adapters/persistence/sqlite/config.yaml")

    # Create and start mesh service
    mesh = MeshService(nats_url=nats_url, opa_url=opa_url, persistence_config_path=persistence_config)
    await mesh.start()
    await mesh.run_forever()


if __name__ == "__main__":
    asyncio.run(main())

