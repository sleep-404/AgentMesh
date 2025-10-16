"""Client examples for testing the agent APIs."""
import asyncio
import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_grpc_clients():
    """Test gRPC endpoints for Langraph and Lyzr agents."""
    import grpc

    from dummy_agents.protos import agent_service_pb2, agent_service_pb2_grpc

    print("=" * 60)
    print("Testing gRPC Endpoints")
    print("=" * 60)

    # Create channel
    channel = grpc.insecure_channel("localhost:50051")
    stub = agent_service_pb2_grpc.AgentServiceStub(channel)

    # Test Langraph agent
    print("\n1. Testing Langraph Agent")
    print("-" * 60)
    try:
        request = agent_service_pb2.AgentRequest(task="Analyze sales data for Q4")
        response = stub.ExecuteLangraphAgent(request)
        print(f"Agent Type: {response.agent_type}")
        print(f"Task: {response.task}")
        print(f"Result: {response.result}")
        print(f"Status: {response.status}")
        details = json.loads(response.details)
        print(f"Steps Executed: {details.get('steps_executed', [])}")
        print("✓ Langraph agent executed successfully")
    except grpc.RpcError as e:
        print(f"✗ Error: {e.code()} - {e.details()}")

    # Test Lyzr agent
    print("\n2. Testing Lyzr Agent")
    print("-" * 60)
    try:
        request = agent_service_pb2.AgentRequest(task="Generate monthly report")
        response = stub.ExecuteLyzrAgent(request)
        print(f"Agent Type: {response.agent_type}")
        print(f"Task: {response.task}")
        print(f"Result: {response.result}")
        print(f"Status: {response.status}")
        details = json.loads(response.details)
        print(f"Workflow Stages: {details.get('workflow_stages', [])}")
        print("✓ Lyzr agent executed successfully")
    except grpc.RpcError as e:
        print(f"✗ Error: {e.code()} - {e.details()}")

    channel.close()


def test_rest_clients():
    """Test REST endpoints for CrewAI and OpenAI agents."""
    import requests

    print("\n" + "=" * 60)
    print("Testing REST API Endpoints")
    print("=" * 60)

    base_url = "http://localhost:8000"

    # Test CrewAI agent
    print("\n3. Testing CrewAI Agent")
    print("-" * 60)
    try:
        response = requests.post(
            f"{base_url}/api/agents/crewai",
            json={"task": "Analyze market trends for tech sector"},
        )
        response.raise_for_status()
        data = response.json()
        print(f"Agent Type: {data['agent_type']}")
        print(f"Task: {data['task']}")
        print(f"Result: {data['result']}")
        print(f"Status: {data['status']}")
        print(f"Role: {data['details'].get('role')}")
        print(f"Crew Steps: {data['details'].get('crew_steps', [])}")
        print("✓ CrewAI agent executed successfully")
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")

    # Test OpenAI agent
    print("\n4. Testing OpenAI Agent")
    print("-" * 60)
    try:
        response = requests.post(
            f"{base_url}/api/agents/openai",
            json={"task": "Summarize the latest AI research papers"},
        )
        response.raise_for_status()
        data = response.json()
        print(f"Agent Type: {data['agent_type']}")
        print(f"Task: {data['task']}")
        print(f"Result: {data['result']}")
        print(f"Status: {data['status']}")
        print(f"Prompt: {data['details'].get('prompt')}")
        print(f"Execution Log: {data['details'].get('execution_log', [])}")
        print("✓ OpenAI agent executed successfully")
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")


def test_rest_api_info():
    """Test REST API root endpoint."""
    import requests

    print("\n" + "=" * 60)
    print("Testing REST API Info")
    print("=" * 60)

    try:
        response = requests.get("http://localhost:8000/")
        response.raise_for_status()
        data = response.json()
        print(f"Message: {data.get('message')}")
        print(f"Available Endpoints: {json.dumps(data.get('endpoints', {}), indent=2)}")
        print("\n✓ REST API is accessible")
        print("  Swagger UI: http://localhost:8000/docs")
        print("  ReDoc: http://localhost:8000/redoc")
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")


async def test_concurrent_requests():
    """Test multiple concurrent agent requests."""
    from concurrent.futures import ThreadPoolExecutor

    import requests

    print("\n" + "=" * 60)
    print("Testing Concurrent Agent Execution")
    print("=" * 60)

    def execute_agent(agent_type: str, task: str):
        """Execute a single agent request."""
        if agent_type in ["crewai", "openai"]:
            response = requests.post(
                f"http://localhost:8000/api/agents/{agent_type}", json={"task": task}
            )
            return response.json()
        return None

    tasks = [
        ("crewai", "Task 1: Market analysis"),
        ("openai", "Task 2: Document summary"),
        ("crewai", "Task 3: Customer segmentation"),
        ("openai", "Task 4: Sentiment analysis"),
    ]

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(execute_agent, agent_type, task)
            for agent_type, task in tasks
        ]
        results = [future.result() for future in futures]

    print(f"\n✓ Executed {len(results)} agents concurrently")
    for i, result in enumerate(results, 1):
        if result:
            print(f"  Agent {i}: {result['agent_type']} - {result['status']}")


def main():
    """Run all client examples."""
    print("\n" + "=" * 60)
    print("DUMMY AGENTS - CLIENT EXAMPLES")
    print("=" * 60)
    print("\nMake sure both servers are running:")
    print("  1. gRPC server: python dummy_agents/grpc_server.py")
    print("  2. REST API server: python dummy_agents/rest_server.py")
    print("\nOr use: bash dummy_agents/run_all.sh")

    input("\nPress Enter to start testing...")

    try:
        # Test REST API info first
        test_rest_api_info()

        # Test individual agents
        test_grpc_clients()
        test_rest_clients()

        # Test concurrent execution
        asyncio.run(test_concurrent_requests())

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
