"""
gRPC Server for Agent Connections.

Provides gRPC endpoints for agents to connect to the mesh.
"""
import asyncio
import logging
from concurrent import futures

import grpc

from adapters.messaging.nats_client import NATSWrapper
from services.connection import (
    AgentConnectionRequest,
    AgentConnectionService,
)
from services.connection.schemas import AgentDisconnectRequest, AgentHeartbeat

# Import generated proto files (will be generated)
try:
    from api.protos import (  # type: ignore[attr-defined]
        connection_service_pb2,
        connection_service_pb2_grpc,
    )
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning(
        "Proto files not generated. Run: python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. api/protos/connection_service.proto"
    )
    connection_service_pb2 = None  # type: ignore[assignment]
    connection_service_pb2_grpc = None  # type: ignore[assignment]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionServiceServicer:
    """gRPC servicer for connection service"""

    def __init__(self, connection_service: AgentConnectionService):
        self.connection_service = connection_service

    async def ConnectAgent(self, request, context):
        """Connect an agent to the mesh"""
        try:
            # Convert proto to Pydantic model
            conn_request = AgentConnectionRequest(
                endpoint=request.endpoint,
                token=request.token,
                metadata=dict(request.metadata) if request.metadata else {},
            )

            # Connect agent
            response = await self.connection_service.connect_agent(conn_request)

            # Convert to proto response
            return connection_service_pb2.ConnectResponse(
                agent_id=response.agent_id,
                private_subject=response.private_subject,
                global_subjects=response.global_subjects,
                connection_status=response.connection_status,
                connected_at=response.connected_at.isoformat(),
                message=response.message,
            )

        except ValueError as e:
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details(str(e))
            return connection_service_pb2.ConnectResponse()
        except Exception as e:
            logger.error(f"Error connecting agent: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return connection_service_pb2.ConnectResponse()

    async def DisconnectAgent(self, request, context):
        """Disconnect an agent from the mesh"""
        try:
            disconnect_request = AgentDisconnectRequest(
                agent_id=request.agent_id,
                reason=request.reason or "Normal disconnect",
            )

            await self.connection_service.disconnect_agent(
                disconnect_request.agent_id, disconnect_request.reason
            )

            return connection_service_pb2.DisconnectResponse(
                status="success",
                message=f"Agent '{request.agent_id}' disconnected",
            )

        except Exception as e:
            logger.error(f"Error disconnecting agent: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return connection_service_pb2.DisconnectResponse()

    async def Heartbeat(self, request, context):
        """Handle heartbeat from agent"""
        try:
            from datetime import datetime

            heartbeat = AgentHeartbeat(
                agent_id=request.agent_id,
                timestamp=datetime.fromisoformat(request.timestamp),
                status=request.status or "active",
                metadata=dict(request.metadata) if request.metadata else {},
            )

            response = await self.connection_service.handle_heartbeat(heartbeat)

            return connection_service_pb2.HeartbeatResponse(
                status=response["status"],
                message=response["message"],
            )

        except Exception as e:
            logger.error(f"Error handling heartbeat: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return connection_service_pb2.HeartbeatResponse()

    async def ListConnectedAgents(self, request, context):
        """List all connected agents"""
        try:
            agents = await self.connection_service.get_connected_agents()

            agent_infos = []
            for agent in agents:
                agent_infos.append(
                    connection_service_pb2.AgentInfo(
                        agent_id=agent["agent_id"],
                        endpoint=agent["endpoint"],
                        private_subject=agent["private_subject"],
                        connected_at=agent["connected_at"],
                        last_heartbeat=agent["last_heartbeat"],
                    )
                )

            return connection_service_pb2.ListAgentsResponse(
                agents=agent_infos,
                count=len(agent_infos),
            )

        except Exception as e:
            logger.error(f"Error listing agents: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return connection_service_pb2.ListAgentsResponse()


async def serve(port: int = 50052):
    """Start the gRPC server"""
    if not connection_service_pb2 or not connection_service_pb2_grpc:
        logger.error("Proto files not generated. Cannot start gRPC server.")
        return

    logger.info("Starting AgentMesh gRPC server...")

    # Initialize NATS
    nats_client = NATSWrapper()
    try:
        await nats_client.connect()
        logger.info("Connected to NATS")
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        raise

    # Initialize connection service
    connection_service = AgentConnectionService(nats_client)
    await connection_service.start_monitoring(check_interval=30)
    logger.info("Connection service initialized")

    # Create gRPC server
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))

    servicer = ConnectionServiceServicer(connection_service)
    connection_service_pb2_grpc.add_ConnectionServiceServicer_to_server(
        servicer, server
    )

    server.add_insecure_port(f"[::]:{port}")
    await server.start()

    logger.info(f"gRPC server started on port {port}")
    logger.info("Available endpoints:")
    logger.info("  - ConnectAgent")
    logger.info("  - DisconnectAgent")
    logger.info("  - Heartbeat")
    logger.info("  - ListConnectedAgents")

    try:
        await server.wait_for_termination()
    finally:
        await connection_service.stop_monitoring()
        await nats_client.disconnect()


def main():
    """Main entry point"""
    asyncio.run(serve())


if __name__ == "__main__":
    main()
