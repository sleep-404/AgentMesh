"""Test configuration and fixtures for Knowledge Base adapters."""

import asyncio
import os
import subprocess
import time

import pytest


@pytest.fixture(scope="session")
def docker_compose_file():
    """Path to the docker-compose test file."""
    return os.path.join(os.path.dirname(__file__), "docker-compose.test.yaml")


@pytest.fixture(scope="session")
def docker_compose_project_name():
    """Docker Compose project name for test isolation."""
    return "agentmesh_test"


@pytest.fixture(scope="session", autouse=True)
def setup_test_databases(docker_compose_file, docker_compose_project_name):
    """Set up test databases using Docker Compose."""
    # Start the containers
    subprocess.run(
        [
            "docker-compose",
            "-f",
            docker_compose_file,
            "-p",
            docker_compose_project_name,
            "up",
            "-d",
        ],
        check=True,
    )

    # Wait for PostgreSQL to be ready
    max_retries = 30
    for _ in range(max_retries):
        result = subprocess.run(
            [
                "docker-compose",
                "-f",
                docker_compose_file,
                "-p",
                docker_compose_project_name,
                "exec",
                "-T",
                "postgres-test",
                "pg_isready",
                "-U",
                "postgres",
            ],
            capture_output=True,
        )
        if result.returncode == 0:
            print("PostgreSQL is ready!")
            break
        time.sleep(1)
    else:
        raise Exception("PostgreSQL failed to start")

    # Wait for Neo4j to be ready
    for _ in range(max_retries):
        result = subprocess.run(
            [
                "docker-compose",
                "-f",
                docker_compose_file,
                "-p",
                docker_compose_project_name,
                "exec",
                "-T",
                "neo4j-test",
                "wget",
                "--spider",
                "-q",
                "http://localhost:7474",
            ],
            capture_output=True,
        )
        if result.returncode == 0:
            print("Neo4j is ready!")
            break
        time.sleep(1)
    else:
        raise Exception("Neo4j failed to start")

    # Give databases a bit more time to fully initialize
    time.sleep(3)

    yield

    # Teardown: Stop and remove containers
    subprocess.run(
        [
            "docker-compose",
            "-f",
            docker_compose_file,
            "-p",
            docker_compose_project_name,
            "down",
            "-v",
        ],
        check=True,
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
