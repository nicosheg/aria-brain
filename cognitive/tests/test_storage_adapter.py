import sys
sys.path.insert(0, '.')
from cognitive.memory.storage_adapter import InMemoryAdapter
from cognitive.memory.graph import Entity, Relationship, Assertion
from cognitive.memory.episodic import Episode
from cognitive.memory.semantic import SemanticFact
from cognitive.memory.procedural import Procedure
from cognitive.memory.assertions import AssertionType

def test_adapter_entity():
    adapter = InMemoryAdapter()
    e = Entity(canonical_name="Nicholas", entity_type="person")
    adapter.save_entity(e)
    retrieved = adapter.get_entity(e.id)
    assert retrieved.canonical_name == "Nicholas"
    assert adapter.get_entity_by_name("Nicholas").id == e.id
    assert len(adapter.get_all_entities()) == 1
    print("✅ Entity adapter: OK")

def test_adapter_relationship():
    adapter = InMemoryAdapter()
    e1 = Entity(canonical_name="Nicholas")
    e2 = Entity(canonical_name="ARIA")
    adapter.save_entity(e1)
    adapter.save_entity(e2)
    
    rel = Relationship(source_id=e1.id, target_id=e2.id, relation_type="builds")
    adapter.save_relationship(rel)
    
    retrieved = adapter.get_relationship(rel.id)
    assert retrieved.relation_type == "builds"
    rels = adapter.get_relationships_of(e1.id)
    assert len(rels) == 1
    print("✅ Relationship adapter: OK")

def test_adapter_transaction():
    adapter = InMemoryAdapter()
    adapter.begin_transaction()
    e = Entity(canonical_name="Temp")
    adapter.save_entity(e)
    assert adapter.get_entity_by_name("Temp") is not None
    adapter.rollback_transaction()
    assert adapter.get_entity_by_name("Temp") is None
    print("✅ Transaction adapter: OK")

def test_adapter_all_memory_types():
    adapter = InMemoryAdapter()
    
    # Entity
    e = Entity(canonical_name="Test")
    adapter.save_entity(e)
    
    # Relationship
    rel = Relationship(source_id="s1", target_id="t1", relation_type="knows")
    adapter.save_relationship(rel)
    
    # Assertion
    a = Assertion(statement="Test assertion", confidence=0.8)
    adapter.save_assertion(a)
    
    # Episode
    ep = Episode(summary="Test episode", full_text="Full text")
    adapter.save_episode(ep)
    
    # Semantic Fact
    f = SemanticFact(statement="Test fact", confidence=0.9)
    adapter.save_semantic_fact(f)
    
    # Procedure
    p = Procedure(name="Test procedure", description="A test", steps=["Step1"])
    adapter.save_procedure(p)
    
    assert len(adapter.get_all_entities()) == 1
    assert len(adapter.get_all_relationships()) == 1
    assert len(adapter.get_all_assertions()) == 1
    assert len(adapter.get_episodes(limit=10)) == 1
    assert len(adapter.get_semantic_facts(limit=10)) == 1
    assert len(adapter.get_procedures(limit=10)) == 1
    print("✅ All memory types adapter: OK")

if __name__ == "__main__":
    test_adapter_entity()
    test_adapter_relationship()
    test_adapter_transaction()
    test_adapter_all_memory_types()
    print("\n🎉 All Storage Adapter tests passed!")
