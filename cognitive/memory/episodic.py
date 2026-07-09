# cognitive/memory/episodic.py

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from cognitive.core.config import ARIAConfig


@dataclass
class Episode:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    summary: str = ""
    full_text: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    importance: float = ARIAConfig.DEFAULT_IMPORTANCE
    source: str = "conversation"
    entities_involved: List[str] = field(default_factory=list)
    relationships_changed: List[str] = field(default_factory=list)
    beliefs_affected: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "summary": self.summary,
            "full_text": self.full_text,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "source": self.source,
            "entities_involved": self.entities_involved,
            "relationships_changed": self.relationships_changed,
            "beliefs_affected": self.beliefs_affected,
            "metadata": self.metadata
        }


class EpisodicMemory:
    def __init__(self, max_size: int = None):
        self.max_size = max_size or ARIAConfig.EPISODIC_MAX_SIZE
        self.episodes: List[Episode] = []
        self.importance_weight = ARIAConfig.EPISODIC_CONSOLIDATION_IMPORTANCE_WEIGHT
        self.recency_weight = ARIAConfig.EPISODIC_CONSOLIDATION_RECENCY_WEIGHT
        self.recency_days = ARIAConfig.EPISODIC_RECENCY_DAYS
        self.importance_threshold = ARIAConfig.EPISODIC_IMPORTANCE_THRESHOLD
    
    def add(self, summary: str, full_text: str, importance: float = None,
            source: str = "conversation", entities: List[str] = None,
            relationships: List[str] = None, beliefs: List[str] = None,
            metadata: Dict = None) -> Episode:
        importance = importance if importance is not None else ARIAConfig.DEFAULT_IMPORTANCE
        episode = Episode(
            summary=summary,
            full_text=full_text,
            importance=importance,
            source=source,
            entities_involved=entities or [],
            relationships_changed=relationships or [],
            beliefs_affected=beliefs or [],
            metadata=metadata or {}
        )
        self.episodes.append(episode)
        if len(self.episodes) > self.max_size:
            self._consolidate()
        return episode
    
    def get_recent(self, limit: int = 10) -> List[Episode]:
        sorted_eps = sorted(self.episodes, key=lambda x: x.timestamp, reverse=True)
        return sorted_eps[:limit]
    
    def get_important(self, threshold: float = None) -> List[Episode]:
        threshold = threshold if threshold is not None else self.importance_threshold
        return [e for e in self.episodes if e.importance >= threshold]
    
    def get_by_entity(self, entity_name: str, limit: int = 10) -> List[Episode]:
        results = []
        for ep in self.episodes:
            if entity_name.lower() in [e.lower() for e in ep.entities_involved]:
                results.append(ep)
        return sorted(results, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def get_by_topic(self, keyword: str, limit: int = 10) -> List[Episode]:
        results = []
        keyword_lower = keyword.lower()
        for ep in self.episodes:
            if keyword_lower in ep.full_text.lower() or keyword_lower in ep.summary.lower():
                results.append(ep)
        return sorted(results, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def get_by_importance_and_recency(self, importance_weight: float = None,
                                      recency_weight: float = None,
                                      limit: int = 10) -> List[Episode]:
        iw = importance_weight if importance_weight is not None else self.importance_weight
        rw = recency_weight if recency_weight is not None else self.recency_weight
        
        def score(ep: Episode) -> float:
            now = datetime.now(timezone.utc)
            days = (now - datetime.fromisoformat(ep.timestamp)).days
            recency_score = max(0, 1 - (days / self.recency_days))
            return (ep.importance * iw) + (recency_score * rw)
        
        scored = [(score(ep), ep) for ep in self.episodes]
        scored.sort(reverse=True, key=lambda x: x[0])
        return [ep for _, ep in scored[:limit]]
    
    def get_all(self) -> List[Episode]:
        return self.episodes
    
    def count(self) -> int:
        return len(self.episodes)
    
    def clear(self):
        self.episodes = []
    
    def _consolidate(self):
        scored = []
        now = datetime.now(timezone.utc)
        for ep in self.episodes:
            days = (now - datetime.fromisoformat(ep.timestamp)).days
            recency_score = max(0, 1 - (days / self.recency_days))
            score = (ep.importance * self.importance_weight) + (recency_score * self.recency_weight)
            scored.append((score, ep))
        scored.sort(reverse=True, key=lambda x: x[0])
        keep = int(self.max_size * 0.8)
        self.episodes = [ep for _, ep in scored[:keep]]
    
    def to_dict(self) -> Dict:
        return {
            "episodes": [ep.to_dict() for ep in self.episodes],
            "count": len(self.episodes),
            "max_size": self.max_size
        }
