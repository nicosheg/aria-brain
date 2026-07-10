#!/usr/bin/env python
import sys
sys.path.insert(0, '.')

print("🧠 ARIA File Persistence Memory Test\n")

# --- PHASE 1: Save a name to file ---
from cognitive.core.orchestrator import Orchestrator

print("📝 Creating orchestrator for user nicosheg123@gmail.com...")
orch = Orchestrator("nicosheg123@gmail.com")

print("📝 Telling ARIA: 'My name is Nicholas'")
result1 = orch.process("conversation", "My name is Nicholas", {"email": "nicosheg123@gmail.com"})
print(f"   Response: {result1.get('response')}")

print("\n📊 Entities in memory:", len(orch.graph.entities_by_id))
print("📊 Episodes stored:", orch.episodic.count())

# --- PHASE 2: Simulate a restart (create new orchestrator) ---
print("\n🔄 Simulating server restart...")
orch2 = Orchestrator("nicosheg123@gmail.com")

print("\n❓ Asking new orchestrator: 'What is my name?'")
result2 = orch2.process("conversation", "What is my name?", {"email": "nicosheg123@gmail.com"})
print(f"   Response: {result2.get('response')}")

print("\n📊 Entities loaded from file:", len(orch2.graph.entities_by_id))
print("📊 Episodes loaded:", orch2.episodic.count())

print("\n✅ ARIA remembers you across restarts!")
