"""Script to generate gRPC Python code from proto files."""
import subprocess
import sys
from pathlib import Path


def generate_grpc_code():
    """Generate Python code from proto files."""
    # Get the directory containing this script
    script_dir = Path(__file__).parent
    protos_dir = script_dir / "protos"

    # Proto file
    proto_file = protos_dir / "agent_service.proto"

    if not proto_file.exists():
        print(f"Error: Proto file not found at {proto_file}")
        sys.exit(1)

    # Generate Python code
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"--proto_path={script_dir}",
        f"--python_out={script_dir}",
        f"--grpc_python_out={script_dir}",
        str(proto_file.relative_to(script_dir)),
    ]

    print(f"Generating gRPC code from {proto_file}")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("Error generating gRPC code:")
        print(result.stderr)
        sys.exit(1)

    print("✓ Successfully generated gRPC Python code")
    print(f"  - {protos_dir / 'agent_service_pb2.py'}")
    print(f"  - {protos_dir / 'agent_service_pb2_grpc.py'}")

    # Fix import in generated grpc file
    grpc_file = protos_dir / "agent_service_pb2_grpc.py"
    if grpc_file.exists():
        content = grpc_file.read_text()
        content = content.replace(
            "from protos import agent_service_pb2",
            "from dummy_agents.protos import agent_service_pb2",
        )
        grpc_file.write_text(content)
        print("✓ Fixed imports in generated gRPC code")


if __name__ == "__main__":
    generate_grpc_code()
