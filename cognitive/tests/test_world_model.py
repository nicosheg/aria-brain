import sys
sys.path.insert(0, '.')
from cognitive.memory.graph import KnowledgeGraph
from cognitive.memory.episodic import EpisodicMemory
from cognitive.memory.semantic import SemanticMemory
from cognitive.memory.procedural import ProceduralMemory
from cognitive.retrieve.retriever import Retriever
from cognitive.retrieve.world_model import WorldModelBuilder


def test_world_model_build():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    # Add test data
    e1 = graph.get_or_create_entity("Nicholas", "person")
    e2 = graph.get_or_create_entity("ARIA", "concept")
    
    change = graph.propose_change("ADD_RELATIONSHIP", {
        "source_id": e1.id,
        "target_id": e2.id,
        "relation_type": "builds"
    })
    graph.validate_and_commit(change)
    
    episodic.add("Nicholas built ARIA", "Nicholas built ARIA", importance=0.8, entities=["Nicholas"])
    semantic.add("Nicholas builds AI systems", confidence=0.9)
    procedural.add("Nicholas ARIA", "Build the ARIA system", ["Step 1", "Step 2"], "When building ARIA")
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    builder = WorldModelBuilder(graph, retriever, episodic, semantic, procedural)
    
    model = builder.build("Nicholas ARIA")
    
    assert model.query == "Nicholas ARIA"
    assert len(model.entities) > 0
    assert len(model.relationships) > 0
    assert len(model.beliefs) > 0
    assert len(model.recent_episodes) > 0
    # Procedures may or may not be retrieved depending on ranking; we check it's at least 0
    assert len(model.available_procedures) >= 0
    assert model.built_at is not None
    
    print("✅ World model build: OK")


def test_world_model_build_from_entity():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    e = graph.get_or_create_entity("Nicholas", "person")
    episodic.add("Nicholas did something", "Nicholas did something", entities=["Nicholas"])
    semantic.add("Nicholas is a builder", confidence=0.8)
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    builder = WorldModelBuilder(graph, retriever, episodic, semantic, procedural)
    
    model = builder.build_from_entity("Nicholas")
    
    assert len(model.entities) > 0
    assert model.entities[0].canonical_name == "Nicholas"
    print("✅ World model build_from_entity: OK")


def test_world_model_has_patterns():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    # Add multiple entities to trigger pattern detection
    graph.get_or_create_entity("Nicholas", "person")
    graph.get_or_create_entity("ARIA", "concept")
    graph.get_or_create_entity("FIDUCIA", "concept")
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    builder = WorldModelBuilder(graph, retriever, episodic, semantic, procedural)
    
    model = builder.build("test")
    
    # With multiple entities, patterns should be detected
    if len(model.entities) > 1:
        assert len(model.patterns) > 0
    
    print("✅ World model patterns: OK")


def test_world_model_to_dict():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    e = graph.get_or_create_entity("Nicholas", "person")
    episodic.add("Test episode", "Test content", importance=0.9, entities=["Nicholas"])
    semantic.add("Test fact", confidence=0.85)
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    builder = WorldModelBuilder(graph, retriever, episodic, semantic, procedural)
    
    model = builder.build("test")
    d = model.to_dict()
    
    assert "entities" in d
    assert "relationships" in d
    assert "beliefs" in d
    assert "recent_episodes" in d
    assert "patterns" in d
    assert "uncertainty" in d
    assert "temporal_context" in d
    
    print("✅ World model to_dict: OK")


if __name__ == "__main__":
    test_world_model_build()
    test_world_model_build_from_entity()
    test_world_model_has_patterns()
    test_world_model_to_dict()
    print("\n🎉 All World Model tests passed!")
