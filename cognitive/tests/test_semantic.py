import sys
sys.path.insert(0, '.')
from cognitive.memory.semantic import SemanticMemory

def test_semantic_add():
    mem = SemanticMemory()
    fact = mem.add("Nicholas builds ARIA", confidence=0.8)
    assert fact.id is not None
    assert fact.statement == "Nicholas builds ARIA"
    assert fact.confidence == 0.8
    assert mem.count() == 1
    print("✅ Semantic add: OK")

def test_semantic_duplicate_update():
    mem = SemanticMemory()
    f1 = mem.add("Nicholas builds ARIA", confidence=0.6)
    f2 = mem.add("Nicholas builds ARIA", confidence=0.9)
    assert f1.id == f2.id
    assert f1.confidence > 0.6
    assert f1.version == 2
    print("✅ Semantic duplicate update: OK")

def test_semantic_get_relevant():
    mem = SemanticMemory()
    mem.add("Nicholas is a developer", confidence=0.8)
    mem.add("ARIA is a cognitive system", confidence=0.9)
    mem.add("Python is a programming language", confidence=0.7)
    
    results = mem.get_relevant("Nicholas developer", limit=2)
    # Only the first fact contains both "Nicholas" and "developer"
    assert len(results) == 1
    assert "developer" in results[0].statement.lower()
    print("✅ Semantic get_relevant: OK")

def test_semantic_high_confidence():
    mem = SemanticMemory()
    mem.add("Fact 1", confidence=0.9)
    mem.add("Fact 2", confidence=0.6)
    mem.add("Fact 3", confidence=0.8)
    
    high = mem.get_high_confidence(threshold=0.7)
    assert len(high) == 2
    print("✅ Semantic high_confidence: OK")

if __name__ == "__main__":
    test_semantic_add()
    test_semantic_duplicate_update()
    test_semantic_get_relevant()
    test_semantic_high_confidence()
    print("\n🎉 All Semantic Memory tests passed!")
