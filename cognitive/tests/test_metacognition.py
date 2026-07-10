import sys
sys.path.insert(0, '.')
from cognitive.memory.graph import KnowledgeGraph
from cognitive.memory.episodic import EpisodicMemory
from cognitive.memory.semantic import SemanticMemory
from cognitive.memory.procedural import ProceduralMemory
from cognitive.retrieve.world_model import WorldModel, WorldModelBuilder
from cognitive.retrieve.retriever import Retriever
from cognitive.reason.metacognition import MetaCognition


def test_metacognition_certainty():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()  # <-- Fix: use empty ProceduralMemory
    
    # Add some data
    e = graph.get_or_create_entity("Nicholas", "person", confidence=0.9)
    semantic.add("Nicholas is a developer", confidence=0.85)
    semantic.add("ARIA is an AI", confidence=0.95)
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    builder = WorldModelBuilder(graph, retriever, episodic, semantic, procedural)
    world = builder.build("Nicholas")
    
    meta = MetaCognition(graph, episodic, semantic)
    certainty = meta.assess_certainty(world)
    
    assert "overall_certainty" in certainty
    assert len(certainty["belief_certainties"]) >= 1
    assert len(certainty["entity_certainties"]) >= 1
    print("✅ Metacognition certainty: OK")


def test_metacognition_hallucination():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    # Low-confidence entity and beliefs
    e = graph.get_or_create_entity("Unknown", "concept", confidence=0.2)
    semantic.add("Unknown is something", confidence=0.3)
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    builder = WorldModelBuilder(graph, retriever, episodic, semantic, procedural)
    world = builder.build("Unknown")
    
    meta = MetaCognition(graph, episodic, semantic)
    # Set thresholds low for testing
    meta.hallucination_threshold = 0.3
    hallucination = meta.detect_hallucination_risk(world)
    
    assert "risk_score" in hallucination
    assert hallucination["risk_score"] >= 0.3
    print("✅ Metacognition hallucination: OK")


def test_metacognition_should_ask():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    # No data -> should ask
    retriever = Retriever(graph, episodic, semantic, procedural)
    builder = WorldModelBuilder(graph, retriever, episodic, semantic, procedural)
    world = builder.build("nonexistent")
    
    meta = MetaCognition(graph, episodic, semantic)
    meta.certainty_threshold = 0.5
    meta.ask_threshold = 0.5
    
    # Simulate reasoning result
    reasoning_result = {
        "certainty": meta.assess_certainty(world),
        "hallucination_risk": meta.detect_hallucination_risk(world),
        "uncertainty": {}
    }
    
    decision = meta.should_ask_question(world, reasoning_result)
    
    assert "should_ask" in decision
    assert decision["should_ask"] is True
    assert len(decision["questions"]) > 0
    print("✅ Metacognition should_ask: OK")


def test_metacognition_evaluate_reasoning():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    # Add good data
    e = graph.get_or_create_entity("Nicholas", "person", confidence=0.9)
    semantic.add("Nicholas is a builder", confidence=0.9)
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    builder = WorldModelBuilder(graph, retriever, episodic, semantic, procedural)
    world = builder.build("Nicholas")
    
    meta = MetaCognition(graph, episodic, semantic)
    reasoning_result = {
        "certainty": meta.assess_certainty(world),
        "hallucination_risk": meta.detect_hallucination_risk(world),
        "uncertainty": {}
    }
    
    evaluation = meta.evaluate_reasoning(world, reasoning_result)
    
    assert "quality_score" in evaluation
    assert evaluation["quality_score"] >= 0.5
    print("✅ Metacognition evaluate_reasoning: OK")


if __name__ == "__main__":
    test_metacognition_certainty()
    test_metacognition_hallucination()
    test_metacognition_should_ask()
    test_metacognition_evaluate_reasoning()
    print("\n🎉 All Metacognition tests passed!")
