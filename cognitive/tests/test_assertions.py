import sys
sys.path.insert(0, '.')
from cognitive.memory.assertions import Assertion, AssertionType

def test_assertion_creation():
    a = Assertion(statement="Test", confidence=0.8)
    assert a.id is not None
    assert a.confidence == 0.8
    assert a.assertion_type == AssertionType.BELIEF

def test_assertion_bayesian_update():
    a = Assertion(statement="Test", confidence=0.5)
    a.update_confidence(0.9, "ev1")
    assert a.confidence > 0.5
    assert "ev1" in a.evidence
    assert a.version == 2
