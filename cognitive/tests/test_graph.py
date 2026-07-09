import sys
sys.path.insert(0, '.')
from cognitive.memory.graph import KnowledgeGraph

def test_entity_creation():
    g = KnowledgeGraph()
    e = g.get_or_create_entity("Nicholas", "person")
    assert e.canonical_name == "Nicholas"
    assert g.get_entity_by_name("Nicholas") == e

def test_transaction_rollback():
    g = KnowledgeGraph()
    g.begin_transaction()
    e = g.get_or_create_entity("Temp", "concept")
    g.rollback_transaction()
    assert g.get_entity_by_name("Temp") is None
