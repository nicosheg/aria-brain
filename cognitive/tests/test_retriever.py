import sys
sys.path.insert(0, '.')
from cognitive.memory.graph import KnowledgeGraph
from cognitive.memory.episodic import EpisodicMemory
from cognitive.memory.semantic import SemanticMemory
from cognitive.memory.procedural import ProceduralMemory
from cognitive.retrieve.retriever import Retriever


def test_retriever_basic():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    # Add some data
    entity = graph.get_or_create_entity("Nicholas", "person")
    entity2 = graph.get_or_create_entity("ARIA", "concept")
    
    # Add relationship
    change = graph.propose_change("ADD_RELATIONSHIP", {
        "source_id": entity.id,
        "target_id": entity2.id,
        "relation_type": "builds"
    })
    graph.validate_and_commit(change)
    
    # Add episode with entities involved
    episodic.add(
        summary="Nicholas built ARIA",
        full_text="Nicholas built ARIA to help people",
        importance=0.8,
        entities=["Nicholas"]  # <-- Add this
    )
    
    # Add semantic fact
    semantic.add("Nicholas builds ARIA", confidence=0.9)
    
    # Add procedure
    procedural.add("Build ARIA", "Build the ARIA system", ["Design", "Code", "Test"], "When building ARIA")
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    results = retriever.retrieve("Nicholas built ARIA", limit=5)
    
    assert "entities" in results
    assert "relationships" in results
    assert "episodes" in results
    assert "semantic_facts" in results
    assert "procedures" in results
    
    assert len(results["entities"]) > 0
    assert len(results["relationships"]) > 0
    assert len(results["episodes"]) > 0
    assert len(results["semantic_facts"]) > 0
    print("✅ Retriever basic: OK")


def test_retriever_by_entity():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    entity = graph.get_or_create_entity("Nicholas", "person")
    entity2 = graph.get_or_create_entity("ARIA", "concept")
    
    change = graph.propose_change("ADD_RELATIONSHIP", {
        "source_id": entity.id,
        "target_id": entity2.id,
        "relation_type": "builds"
    })
    graph.validate_and_commit(change)
    
    episodic.add(
        summary="Nicholas built ARIA",
        full_text="Nicholas built ARIA",
        importance=0.8,
        entities=["Nicholas"]
    )
    semantic.add("Nicholas is a builder", confidence=0.9)
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    results = retriever.retrieve_by_entity("Nicholas", limit=5)
    
    assert "entity" in results
    assert results["entity"].canonical_name == "Nicholas"
    assert len(results["relationships"]) > 0
    assert len(results["episodes"]) > 0
    assert len(results["beliefs"]) > 0
    print("✅ Retriever by_entity: OK")


def test_retriever_similar():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    graph.get_or_create_entity("Nicholas", "person")
    graph.get_or_create_entity("Nick", "person")
    graph.get_or_create_entity("ARIA", "concept")
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    results = retriever.retrieve_similar("Nick", threshold=0.3)
    
    assert len(results) > 0
    print("✅ Retriever similar: OK")


def test_retriever_empty():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    results = retriever.retrieve("something not in memory", limit=5)
    
    assert len(results["entities"]) == 0
    assert len(results["relationships"]) == 0
    assert len(results["episodes"]) == 0
    assert len(results["semantic_facts"]) == 0
    assert len(results["procedures"]) == 0
    print("✅ Retriever empty: OK")


if __name__ == "__main__":
    test_retriever_basic()
    test_retriever_by_entity()
    test_retriever_similar()
    test_retriever_empty()
    print("\n🎉 All Retriever tests passed!")
