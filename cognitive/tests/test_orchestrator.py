import sys
sys.path.insert(0, '.')
from cognitive.core.orchestrator import Orchestrator


def test_orchestrator_basic():
    orch = Orchestrator("test_user")
    
    # Process a message
    result = orch.process("conversation", "Hello, my name is Nicholas")
    
    assert "observation" in result
    assert "world" in result
    assert "reasoning" in result
    assert "metacognition" in result
    assert "action" in result
    assert "response" in result
    print("✅ Orchestrator basic: OK")


def test_orchestrator_ask():
    orch = Orchestrator("test_user")
    
    # Use the ask() method
    response = orch.ask("What is my name?")
    
    assert isinstance(response, str)
    print("✅ Orchestrator ask: OK")


def test_orchestrator_world_model():
    orch = Orchestrator("test_user")
    orch.process("conversation", "Nicholas is a developer")
    orch.process("conversation", "ARIA is an AI system")
    
    world = orch.get_world_model("Nicholas")
    
    assert "entities" in world
    print("✅ Orchestrator world model: OK")


def test_orchestrator_state():
    orch = Orchestrator("test_user")
    orch.process("conversation", "Hello")
    
    state = orch.get_state()
    
    assert "user_id" in state
    assert "total_episodes" in state
    assert "total_entities" in state
    print("✅ Orchestrator state: OK")


if __name__ == "__main__":
    test_orchestrator_basic()
    test_orchestrator_ask()
    test_orchestrator_world_model()
    test_orchestrator_state()
    print("\n🎉 All Orchestrator tests passed!")
