import pytest
from cognitive.memory.graph import KnowledgeGraph

def test_entity_creation():
    g = KnowledgeGraph()
    e = g.get_or_create_entity("Nicholas", "person")
    assert e.canonical_name == "Nicholas"
    assert g.get_entity_by_name("Nicholas") == e

def test_entity_alias():
    g = KnowledgeGraph()
    e = g.get_or_create_entity("Nicholas", "person")
    e.add_alias("Nick")
    assert "Nick" in e.aliases
    assert g.get_entity_by_name("Nick") == e

def test_relationship_creation():
    g = KnowledgeGraph()
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
    assert ok
    assert len(g.relationships_by_id) == 1

def test_assertion_commit():
    g = KnowledgeGraph()
    change = g.propose_change("ADD_ASSERTION", {
        "statement": "Nicholas builds ARIA",
        "confidence": 0.9,
        "source": "test",
        "created_by": "obs1"
    })
    ok, msg = g.validate_and_commit(change)
    assert ok
    assert len(g.assertions_by_id) == 1
    a = list(g.assertions_by_id.values())[0]
    assert a.statement == "Nicholas builds ARIA"
    assert a.confidence == 0.9

def test_transaction_rollback():
    g = KnowledgeGraph()
    g.begin_transaction()
    e = g.get_or_create_entity("Temp", "concept")
    g.rollback_transaction()
    assert g.get_entity_by_name("Temp") is None

def test_invariant_violation():
    g = KnowledgeGraph()
    change = g.propose_change("ADD_RELATIONSHIP", {
        "source_id": "nonexistent",
        "target_id": "another",
        "relation_type": "knows"
    })
    ok, msg = g.validate_and_commit(change)
    assert not ok
    assert "Invariant" in msg
