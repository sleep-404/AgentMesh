#!/usr/bin/env python3
"""
Scenario 3: Real-Time Agent Discovery

This script demonstrates:
1. Starting an agent that subscribes to mesh directory updates
2. Registering new agents/KBs while the subscriber is running
3. Receiving real-time notifications via NATS pub/sub
4. Querying the directory to discover available capabilities

Prerequisites:
- Docker services running (docker-compose up -d)
- NATS server on localhost:4222
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from adapters.messaging.nats_client import NATSWrapper


class DiscoveryAgent:
    """Sample agent that demonstrates real-time discovery."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.nats_client = NATSWrapper()
        self.discovered_agents = []
        self.discovered_kbs = []

    async def connect(self):
        """Connect to NATS and subscribe to directory updates."""
        print(f"🔌 [{self.agent_id}] Connecting to NATS...")
        await self.nats_client.connect()
        print(f"✅ [{self.agent_id}] Connected to NATS\n")

        # Subscribe to directory updates
        print(f"📡 [{self.agent_id}] Subscribing to mesh.directory.updates...")
        await self.nats_client.subscribe(
            subject="mesh.directory.updates", callback=self.handle_directory_update
        )
        print(f"✅ [{self.agent_id}] Subscribed to directory updates\n")

    async def handle_directory_update(self, message: dict):
        """Handle directory update notifications."""
        update_type = message.get("type")
        timestamp = message.get("timestamp", datetime.now().isoformat())
        data = message.get("data", {})

        print("-" * 70)
        print(f"📨 [{self.agent_id}] Received notification: {update_type}")
        print(f"   Timestamp: {timestamp}")

        if update_type == "agent_registered":
            identity = data.get("identity")
            capabilities = data.get("capabilities", [])

            self.discovered_agents.append(
                {
                    "identity": identity,
                    "capabilities": capabilities,
                    "timestamp": timestamp,
                }
            )

            print(f"   🤖 New agent discovered: {identity}")
            print(f"   📋 Capabilities: {', '.join(capabilities)}")
            print(f"   ✅ Total agents discovered: {len(self.discovered_agents)}")

        elif update_type == "kb_registered":
            kb_id = data.get("kb_id")
            kb_type = data.get("kb_type")
            operations = data.get("operations", [])

            self.discovered_kbs.append(
                {
                    "kb_id": kb_id,
                    "kb_type": kb_type,
                    "operations": operations,
                    "timestamp": timestamp,
                }
            )

            print(f"   💾 New KB discovered: {kb_id}")
            print(f"   📊 Type: {kb_type}")
            print(f"   🔧 Operations: {', '.join(operations)}")
            print(f"   ✅ Total KBs discovered: {len(self.discovered_kbs)}")

        elif update_type == "agent_capability_updated":
            identity = data.get("identity")
            new_capabilities = data.get("capabilities", [])

            print(f"   🔄 Agent updated: {identity}")
            print(f"   📋 New capabilities: {', '.join(new_capabilities)}")

        print("-" * 70)
        print()

    async def query_directory(self):
        """Query the mesh directory for all registered agents and KBs."""
        print(f"🔍 [{self.agent_id}] Querying mesh directory...")

        request = {
            "request_id": f"{self.agent_id}-{datetime.now().timestamp()}",
            "filter": None,  # Get all agents and KBs
        }

        try:
            response = await self.nats_client.request(
                subject="mesh.directory.query", data=request, timeout=5.0
            )

            agents = response.get("agents", [])
            kbs = response.get("kbs", [])

            print("✅ Directory query successful")
            print(f"   📊 Found {len(agents)} agents")
            print(f"   📊 Found {len(kbs)} knowledge bases")
            print()

            if agents:
                print("   🤖 Registered Agents:")
                for agent in agents:
                    print(f"      - {agent.get('identity')}")
                    print(
                        f"        Capabilities: {', '.join(agent.get('capabilities', []))}"
                    )
                    print(f"        Status: {agent.get('status')}")
                print()

            if kbs:
                print("   💾 Registered Knowledge Bases:")
                for kb in kbs:
                    print(f"      - {kb.get('kb_id')} ({kb.get('kb_type')})")
                    print(f"        Operations: {', '.join(kb.get('operations', []))}")
                print()

            return response

        except Exception as e:
            print(f"❌ Directory query failed: {e}")
            return None

    async def disconnect(self):
        """Disconnect from NATS."""
        print(f"\n🔌 [{self.agent_id}] Disconnecting from NATS...")
        await self.nats_client.disconnect()
        print(f"✅ [{self.agent_id}] Disconnected\n")


async def main():
    print("=" * 70)
    print("Scenario 3: Real-Time Agent Discovery")
    print("=" * 70)
    print()

    # Create discovery agent
    agent = DiscoveryAgent("discovery-agent-demo")

    # Connect and subscribe
    await agent.connect()

    # Query current directory state
    print("Step 1: Query Current Directory State")
    print("=" * 70)
    await agent.query_directory()

    # Wait for updates
    print("Step 2: Listening for Real-Time Updates")
    print("=" * 70)
    print("📡 Waiting for new agents/KBs to register...")
    print("💡 Tip: In another terminal, register agents/KBs via MCP tools")
    print("   Example: Use Claude Desktop to register a new agent")
    print()
    print("⏱️  Will listen for 10 seconds (for demo purposes)...")
    print()

    try:
        # Listen for 10 seconds (shortened for demo)
        await asyncio.sleep(10)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")

    # Show discovery summary
    print("\n" + "=" * 70)
    print("Discovery Summary")
    print("=" * 70)
    print(f"✅ Total agents discovered: {len(agent.discovered_agents)}")
    print(f"✅ Total KBs discovered: {len(agent.discovered_kbs)}")
    print()

    if agent.discovered_agents:
        print("🤖 Agents discovered during this session:")
        for a in agent.discovered_agents:
            print(f"   - {a['identity']} at {a['timestamp']}")
        print()

    if agent.discovered_kbs:
        print("💾 KBs discovered during this session:")
        for kb in agent.discovered_kbs:
            print(f"   - {kb['kb_id']} ({kb['kb_type']}) at {kb['timestamp']}")
        print()

    # Final directory query
    print("Step 3: Final Directory State")
    print("=" * 70)
    await agent.query_directory()

    # Disconnect
    await agent.disconnect()

    print("=" * 70)
    print("✅ Scenario 3 Complete!")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("1. Agents can subscribe to real-time mesh updates via NATS")
    print("2. New agents/KBs are instantly discoverable (< 100ms)")
    print("3. No polling needed - pub/sub provides instant notifications")
    print("4. Agents can query directory anytime for current state")


if __name__ == "__main__":
    asyncio.run(main())
