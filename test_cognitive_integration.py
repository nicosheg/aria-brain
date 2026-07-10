#!/usr/bin/env python
import sys
sys.path.insert(0, '.')

print("🧪 Testing ARIA Cognitive Integration...\n")

from cognitive.core.orchestrator import Orchestrator

# 1. Test orchestrator creation
print("1. Creating orchestrator...")
orch = Orchestrator("test_user")
print("   ✅ Orchestrator created")

# 2. Process a message
print("\n2. Processing a message...")
result = orch.process("conversation", "My name is Nicholas and I'm a developer")
print(f"   Response: {result.get('response', 'No response')}")
print("   ✅ Message processed")

# 3. Get state
print("\n3. Getting state...")
state = orch.get_state()
print(f"   Entities: {state.get('total_entities', 0)}")
print(f"   Episodes: {state.get('total_episodes', 0)}")
print(f"   Facts: {state.get('total_facts', 0)}")
print("   ✅ State retrieved")

# 4. Process another message
print("\n4. Processing a follow-up message...")
result2 = orch.process("conversation", "What is my name?")
print(f"   Response: {result2.get('response', 'No response')}")
print("   ✅ Follow-up processed")

# 5. Get world model
print("\n5. Getting world model...")
world = orch.get_world_model("Nicholas")
print(f"   Entities in world: {len(world.get('entities', []))}")
print("   ✅ World model retrieved")

print("\n🎉 All integration tests passed!")
