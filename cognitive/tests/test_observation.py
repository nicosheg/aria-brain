import sys
sys.path.insert(0, '.')
from cognitive.observe.observation import Observation

def test_observation_creation():
    obs = Observation(source="test", raw="Hello world")
    assert obs.id is not None
    assert obs.source == "test"
    assert obs.raw == "Hello world"
    assert obs.timestamp is not None
    assert obs.importance == 0.5
    assert obs.processed is False
