"""gRPC server for Langraph and Lyzr agents."""
import json
from concurrent import futures
from pathlib import Path

import grpc
from dotenv import load_dotenv

from dummy_agents.agents.langraph_agent import LangraphAgent
from dummy_agents.agents.lyzr_agent import LyzrAgent
from dummy_agents.protos import agent_service_pb2, agent_service_pb2_grpc

# Load environment variables from project root .env file
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")


class AgentServiceServicer(agent_service_pb2_grpc.AgentServiceServicer):
    """gRPC servicer for agent execution."""

    def ExecuteLangraphAgent(self, request, context):
        """Execute Langraph agent.

        Args:
            request: AgentRequest with task
            context: gRPC context

        Returns:
            AgentResponse with execution result
        """
        try:
            # Spawn agent
            agent = LangraphAgent(task=request.task)

            # Execute task
            result = agent.execute()

            # Extract details for JSON serialization
            details = {"steps_executed": result.get("steps_executed", [])}

            # Return response
            return agent_service_pb2.AgentResponse(
                agent_type=result["agent_type"],
                task=result["task"],
                result=result["result"],
                details=json.dumps(details),
                status=result["status"],
            )
        except ValueError as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return agent_service_pb2.AgentResponse()
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error executing Langraph agent: {str(e)}")
            return agent_service_pb2.AgentResponse()

    def ExecuteLyzrAgent(self, request, context):
        """Execute Lyzr agent.

        Args:
            request: AgentRequest with task
            context: gRPC context

        Returns:
            AgentResponse with execution result
        """
        try:
            # Spawn agent
            agent = LyzrAgent(task=request.task)

            # Execute task
            result = agent.execute()

            # Extract details for JSON serialization
            details = {"workflow_stages": result.get("workflow_stages", [])}

            # Return response
            return agent_service_pb2.AgentResponse(
                agent_type=result["agent_type"],
                task=result["task"],
                result=result["result"],
                details=json.dumps(details),
                status=result["status"],
            )
        except ImportError as e:
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
            context.set_details(str(e))
            return agent_service_pb2.AgentResponse()
        except ValueError as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return agent_service_pb2.AgentResponse()
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error executing Lyzr agent: {str(e)}")
            return agent_service_pb2.AgentResponse()


def serve(port: int = 50051):
    """Start the gRPC server.

    Args:
        port: Port to listen on (default: 50051)
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    agent_service_pb2_grpc.add_AgentServiceServicer_to_server(
        AgentServiceServicer(), server
    )
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"gRPC server started on port {port}")
    print("Available endpoints:")
    print("  - ExecuteLangraphAgent")
    print("  - ExecuteLyzrAgent")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
