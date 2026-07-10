#!/usr/bin/env python
import sys
sys.path.insert(0, '.')

from cognitive.core.orchestrator import Orchestrator

print("🧠 Testing ARIA Memory...\n")

orch = Orchestrator("test_user")

# 1. Tell ARIA your name
print("📝 Telling ARIA: My name is Nicholas")
result1 = orch.process("conversation", "My name is Nicholas")
print(f"   Response: {result1.get('response')}")

# 2. Ask what your name is
print("\n❓ Asking: What is my name?")
result2 = orch.process("conversation", "What is my name?")
print(f"   Response: {result2.get('response')}")

# 3. Show what ARIA knows
print("\n📊 ARIA's Knowledge:")
state = orch.get_state()
print(f"   Entities: {state.get('total_entities')}")
print(f"   Episodes: {state.get('total_episodes')}")
print(f"   Facts: {state.get('total_facts')}")

# 4. Show the world model
world = orch.get_world_model("Nicholas")
print(f"   Entities in world: {len(world.get('entities', []))}")

print("\n✅ ARIA remembers you!")
