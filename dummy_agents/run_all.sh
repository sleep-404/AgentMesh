#!/bin/bash
# Script to run both servers

echo "Starting Dummy Agents servers..."

# Generate gRPC code if not already generated
if [ ! -f "dummy_agents/protos/agent_service_pb2.py" ]; then
    echo "Generating gRPC Python code..."
    python dummy_agents/generate_grpc.py
fi

# Start gRPC server in background
echo "Starting gRPC server on port 50051..."
python dummy_agents/grpc_server.py &
GRPC_PID=$!

# Wait a bit for gRPC server to start
sleep 2

# Start REST API server in background
echo "Starting REST API server on port 8000..."
python dummy_agents/rest_server.py &
REST_PID=$!

echo ""
echo "✓ Both servers are running!"
echo "  - gRPC server: localhost:50051 (PID: $GRPC_PID)"
echo "  - REST API server: http://localhost:8000 (PID: $REST_PID)"
echo "  - API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers..."

# Wait for Ctrl+C
trap "echo 'Stopping servers...'; kill $GRPC_PID $REST_PID 2>/dev/null; exit" INT
wait
