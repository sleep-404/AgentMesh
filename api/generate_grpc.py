"""
Generate gRPC code from proto files.

Run this script to generate the Python gRPC code:
    python api/generate_grpc.py
"""
import subprocess
import sys
from pathlib import Path


def generate():
    """Generate gRPC code from proto files"""
    proto_dir = Path(__file__).parent / "protos"
    proto_file = proto_dir / "connection_service.proto"

    if not proto_file.exists():
        print(f"Error: Proto file not found: {proto_file}")
        sys.exit(1)

    print(f"Generating gRPC code from {proto_file}...")

    # Generate Python code
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{proto_dir.parent}",  # Include parent dir
        f"--python_out={proto_dir.parent}",
        f"--grpc_python_out={proto_dir.parent}",
        f"--pyi_out={proto_dir.parent}",  # Generate type stubs
        str(proto_file.relative_to(proto_dir.parent)),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ Generated gRPC code successfully")
        print(f"  - {proto_dir / 'connection_service_pb2.py'}")
        print(f"  - {proto_dir / 'connection_service_pb2_grpc.py'}")
        print(f"  - {proto_dir / 'connection_service_pb2.pyi'}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating gRPC code: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)


if __name__ == "__main__":
    generate()
