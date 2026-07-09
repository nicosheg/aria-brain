# cognitive/memory/semantic.py

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class SemanticFact:
    """
    A distilled semantic fact.
    Facts are extracted from episodes and stored with confidence.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    statement: str = ""
    confidence: float = 0.5
    source_episode_ids: List[str] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "statement": self.statement,
            "confidence": self.confidence,
            "source_episode_ids": self.source_episode_ids,
            "created": self.created,
            "last_updated": self.last_updated,
            "version": self.version
        }


class SemanticMemory:
    """
    Stores distilled semantic facts.
    Facts are extracted from episodes and can be retrieved by relevance.
    """
    
    def __init__(self):
        self.facts: List[SemanticFact] = []
    
    def add(self, statement: str, confidence: float = 0.5,
            source_episode_ids: List[str] = None) -> SemanticFact:
        """Add a new semantic fact."""
        # Check if fact already exists (exact match)
        for fact in self.facts:
            if fact.statement.lower() == statement.lower():
                # Update confidence (Bayesian-like)
                fact.confidence = min(0.99, fact.confidence + (confidence * 0.3 * (1 - fact.confidence)))
                fact.source_episode_ids.extend(source_episode_ids or [])
                fact.last_updated = datetime.now(timezone.utc).isoformat()
                fact.version += 1
                return fact
        
        # Create new fact
        fact = SemanticFact(
            statement=statement,
            confidence=confidence,
            source_episode_ids=source_episode_ids or []
        )
        self.facts.append(fact)
        return fact
    
    def get_by_statement(self, statement: str) -> Optional[SemanticFact]:
        """Get a fact by exact statement match."""
        for fact in self.facts:
            if fact.statement.lower() == statement.lower():
                return fact
        return None
    
    def get_relevant(self, query: str, limit: int = 5) -> List[SemanticFact]:
        """Get facts relevant to a query (keyword matching)."""
        query_words = set(query.lower().split())
        scored = []
        
        for fact in self.facts:
            fact_words = set(fact.statement.lower().split())
            overlap = len(query_words & fact_words)
            if overlap > 0:
                # Score = overlap + confidence bonus
                score = overlap + (fact.confidence * 0.5)
                scored.append((score, fact))
        
        scored.sort(reverse=True, key=lambda x: x[0])
        return [fact for _, fact in scored[:limit]]
    
    def get_high_confidence(self, threshold: float = 0.7) -> List[SemanticFact]:
        """Get facts with confidence above threshold."""
        return [f for f in self.facts if f.confidence >= threshold]
    
    def get_recent(self, limit: int = 10) -> List[SemanticFact]:
        """Get most recently added facts."""
        return sorted(self.facts, key=lambda x: x.created, reverse=True)[:limit]
    
    def get_all(self) -> List[SemanticFact]:
        """Get all facts."""
        return self.facts
    
    def count(self) -> int:
        """Get number of facts."""
        return len(self.facts)
    
    def clear(self):
        """Clear all facts."""
        self.facts = []
    
    def to_dict(self) -> Dict:
        """Serialize all facts."""
        return {
            "facts": [f.to_dict() for f in self.facts],
            "count": len(self.facts)
        }
