import pytest
from cognitive.observe.observation import Observation

def test_observation_creation():
    obs = Observation(source="test", raw="Hello world")
    assert obs.id is not None
    assert obs.source == "test"
    assert obs.raw == "Hello world"
    assert obs.timestamp is not None
    assert obs.importance == 0.5
    assert obs.processed is False

def test_observation_serialization():
    obs = Observation(source="test", raw="Hello", metadata={"key": "value"})
    d = obs.to_dict()
    assert d["source"] == "test"
    assert d["metadata"]["key"] == "value"
