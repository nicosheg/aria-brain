# cognitive/memory/assertions.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import uuid
from datetime import datetime, timezone
from enum import Enum

class AssertionType(Enum):
    FACT = "fact"              # Verified truth
    BELIEF = "belief"          # Probabilistic understanding
    HYPOTHESIS = "hypothesis"  # Tentative
    CONTRADICTION = "contradiction"

@dataclass
class Assertion:
    """
    An assertion with confidence separate from the entity itself.
    
    - Facts are statements with confidence
    - Confidence belongs to the assertion, not the entity
    - Multiple assertions can coexist (competing truths)
    - Every assertion has provenance
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    statement: str = ""
    assertion_type: AssertionType = AssertionType.BELIEF
    confidence: float = 0.5
    evidence: List[str] = field(default_factory=list)  # Episode IDs
    contradictions: List[str] = field(default_factory=list)  # Assertion IDs
    source: str = "conversation"
    created_by: str = ""  # observation_id
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_verified: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1

    def update_confidence(self, new_confidence: float, evidence_id: str):
        """Bayesian confidence update."""
        prior = self.confidence
        likelihood = new_confidence
        posterior = prior + (likelihood * 0.3 * (1 - prior))
        self.confidence = min(0.99, posterior)
        self.evidence.append(evidence_id)
        self.last_updated = datetime.now(timezone.utc).isoformat()
        self.version += 1

    def add_contradiction(self, assertion_id: str):
        """Add a contradiction."""
        if assertion_id not in self.contradictions:
            self.contradictions.append(assertion_id)
            self.confidence *= 0.7
            self.last_updated = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "statement": self.statement,
            "assertion_type": self.assertion_type.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "contradictions": self.contradictions,
            "source": self.source,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "last_verified": self.last_verified,
            "version": self.version
  }
