import sys
sys.path.insert(0, '.')
from cognitive.memory.episodic import EpisodicMemory, Episode
from cognitive.core.config import ARIAConfig

def test_episodic_uses_config_defaults():
    mem = EpisodicMemory()
    # Check that default values are from config
    assert mem.max_size == ARIAConfig.EPISODIC_MAX_SIZE
    assert mem.importance_weight == ARIAConfig.EPISODIC_CONSOLIDATION_IMPORTANCE_WEIGHT
    assert mem.recency_weight == ARIAConfig.EPISODIC_CONSOLIDATION_RECENCY_WEIGHT
    assert mem.recency_days == ARIAConfig.EPISODIC_RECENCY_DAYS
    assert mem.importance_threshold == ARIAConfig.EPISODIC_IMPORTANCE_THRESHOLD
    print("✅ Episodic uses config defaults: OK")

def test_episodic_add():
    mem = EpisodicMemory()
    ep = mem.add("Test summary", "Full text here", importance=0.8)
    assert ep.id is not None
    assert ep.summary == "Test summary"
    assert ep.importance == 0.8
    assert mem.count() == 1
    print("✅ Episodic add: OK")

def test_episodic_get_recent():
    mem = EpisodicMemory()
    mem.add("First", "First text")
    mem.add("Second", "Second text")
    recent = mem.get_recent(1)
    assert len(recent) == 1
    assert recent[0].summary == "Second"
    print("✅ Episodic get_recent: OK")

def test_episodic_get_important():
    mem = EpisodicMemory()
    mem.add("Low", "Low text", importance=0.3)
    mem.add("High", "High text", importance=0.9)
    important = mem.get_important(threshold=0.7)
    assert len(important) == 1
    assert important[0].summary == "High"
    print("✅ Episodic get_important: OK")

def test_episodic_consolidation():
    mem = EpisodicMemory(max_size=10)
    for i in range(15):
        mem.add(f"Episode {i}", f"Text {i}", importance=0.5 + (i * 0.02))
    # After consolidation, size should be <= max_size (10)
    assert mem.count() <= mem.max_size
    print("✅ Episodic consolidation: OK")

def test_episodic_get_by_importance_and_recency():
    mem = EpisodicMemory()
    # Add episodes with different importance and recency
    # We can't easily control recency, but we can test the score function
    # Add a few episodes and verify sorting
    for i in range(5):
        mem.add(f"Episode {i}", f"Text {i}", importance=0.3 + i*0.1)
    results = mem.get_by_importance_and_recency(limit=3)
    assert len(results) == 3
    # The highest importance should be first
    assert results[0].importance >= results[-1].importance
    print("✅ Episodic get_by_importance_and_recency: OK")

if __name__ == "__main__":
    test_episodic_uses_config_defaults()
    test_episodic_add()
    test_episodic_get_recent()
    test_episodic_get_important()
    test_episodic_consolidation()
    test_episodic_get_by_importance_and_recency()
    print("\n🎉 All Episodic Memory tests passed (with config)!")
