#!/usr/bin/env python
import sys
sys.path.insert(0, '.')

print("🧪 Testing ARIA Foundation...\n")

# Test Observation
try:
    from cognitive.observe.observation import Observation
    obs = Observation(source="test", raw="Hello")
    assert obs.id is not None, "Observation ID is None"
    assert obs.source == "test", "Source is wrong"
    print("✅ Observation: OK")
except Exception as e:
    print(f"❌ Observation: FAILED - {e}")
    sys.exit(1)

# Test Assertion
try:
    from cognitive.memory.assertions import Assertion, AssertionType
    a = Assertion(statement="Test", confidence=0.8)
    assert a.confidence == 0.8, "Confidence is wrong"
    a.update_confidence(0.9, "ev1")
    assert a.confidence > 0.8, "Confidence didn't update"
    print("✅ Assertion: OK")
except Exception as e:
    print(f"❌ Assertion: FAILED - {e}")
    sys.exit(1)

# Test Graph
try:
    from cognitive.memory.graph import KnowledgeGraph
    g = KnowledgeGraph()
    e = g.get_or_create_entity("Nicholas", "person")
    assert e.canonical_name == "Nicholas", "Entity name wrong"
    assert g.get_entity_by_name("Nicholas") is not None, "Entity lookup failed"
    print("✅ Graph: OK")
except Exception as e:
    print(f"❌ Graph: FAILED - {e}")
    sys.exit(1)

# Test Relationship
try:
    e1 = g.get_or_create_entity("Nicholas")
    e2 = g.get_or_create_entity("ARIA")
    change = g.propose_change("ADD_RELATIONSHIP", {
        "source_id": e1.id,
        "target_id": e2.id,
        "relation_type": "builds",
        "source": "test",
        "created_by": "obs1"
    })
    ok, msg = g.validate_and_commit(change)
    assert ok, f"Relationship commit failed: {msg}"
    assert len(g.relationships_by_id) == 1, "Relationship not stored"
    print("✅ Relationship: OK")
except Exception as e:
    print(f"❌ Relationship: FAILED - {e}")
    sys.exit(1)

# Test Transaction
try:
    g.begin_transaction()
    temp = g.get_or_create_entity("Temp", "concept")
    g.rollback_transaction()
    assert g.get_entity_by_name("Temp") is None, "Transaction rollback failed"
    print("✅ Transaction: OK")
except Exception as e:
    print(f"❌ Transaction: FAILED - {e}")
    sys.exit(1)

# Test Invariants
try:
    bad_change = g.propose_change("ADD_RELATIONSHIP", {
        "source_id": "nonexistent",
        "target_id": "another",
        "relation_type": "knows"
    })
    ok, msg = g.validate_and_commit(bad_change)
    assert not ok, "Invariant check should have failed"
    assert "Invariant" in msg, "Wrong error message"
    print("✅ Invariants: OK")
except Exception as e:
    print(f"❌ Invariants: FAILED - {e}")
    sys.exit(1)

print("\n🎉 ALL TESTS PASSED!")
print("Foundation is solid. Ready for Phase 2.")
