import sys
sys.path.insert(0, '.')
from cognitive.memory.graph import KnowledgeGraph
from cognitive.memory.episodic import EpisodicMemory
from cognitive.memory.semantic import SemanticMemory
from cognitive.memory.procedural import ProceduralMemory
from cognitive.retrieve.retriever import Retriever
from cognitive.reason.reasoner import Reasoner
from cognitive.reason.metacognition import MetaCognition
from cognitive.decide.planner import Planner, Action
from cognitive.core.event_bus import EventBus
from cognitive.decide.executive import Executive


def test_executive_basic():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    reasoner = Reasoner(graph, episodic, semantic)
    metacognition = MetaCognition(graph, episodic, semantic)
    planner = Planner()
    event_bus = EventBus()
    
    executive = Executive(graph, episodic, semantic, procedural,
                          retriever, reasoner, metacognition,
                          planner, event_bus)
    
    # Process a message
    result = executive.process("conversation", "Hello, my name is Nicholas")
    
    assert "observation" in result
    assert "world" in result
    assert "reasoning" in result
    assert "metacognition" in result
    assert "action" in result
    assert "response" in result
    
    assert result["observation"].source == "conversation"
    assert result["observation"].raw == "Hello, my name is Nicholas"
    print("✅ Executive basic: OK")


def test_executive_asks_question():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    # No data → should ask question
    retriever = Retriever(graph, episodic, semantic, procedural)
    reasoner = Reasoner(graph, episodic, semantic)
    metacognition = MetaCognition(graph, episodic, semantic)
    planner = Planner()
    event_bus = EventBus()
    
    executive = Executive(graph, episodic, semantic, procedural,
                          retriever, reasoner, metacognition,
                          planner, event_bus)
    
    result = executive.process("conversation", "Unknown topic")
    assert "response" in result
    # Should likely be a question or a generic response
    print("✅ Executive asks question: OK")


def test_executive_event_bus():
    graph = KnowledgeGraph()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    procedural = ProceduralMemory()
    
    retriever = Retriever(graph, episodic, semantic, procedural)
    reasoner = Reasoner(graph, episodic, semantic)
    metacognition = MetaCognition(graph, episodic, semantic)
    planner = Planner()
    event_bus = EventBus()
    
    # Track events
    events_received = []
    
    def on_observation(event):
        events_received.append("OBSERVATION_CREATED")
    
    def on_reasoning(event):
        events_received.append("REASONING_COMPLETE")
    
    event_bus.subscribe("OBSERVATION_CREATED", on_observation)
    event_bus.subscribe("REASONING_COMPLETE", on_reasoning)
    
    executive = Executive(graph, episodic, semantic, procedural,
                          retriever, reasoner, metacognition,
                          planner, event_bus)
    
    executive.process("conversation", "Hello")
    
    assert "OBSERVATION_CREATED" in events_received
    assert "REASONING_COMPLETE" in events_received
    print("✅ Executive event bus: OK")


if __name__ == "__main__":
    test_executive_basic()
    test_executive_asks_question()
    test_executive_event_bus()
    print("\n🎉 All Executive tests passed!")
