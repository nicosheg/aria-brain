# cognitive/retrieve/world_model.py

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from cognitive.memory.graph import KnowledgeGraph, Entity, Relationship
from cognitive.memory.episodic import EpisodicMemory, Episode
from cognitive.memory.semantic import SemanticMemory, SemanticFact
from cognitive.memory.procedural import ProceduralMemory, Procedure
from cognitive.retrieve.retriever import Retriever
from cognitive.core.config import ARIAConfig


@dataclass
class WorldModel:
    """
    Immutable, on-demand view of ARIA's understanding.
    Generated fresh for each reasoning cycle.
    NEVER persisted.
    """
    # Core knowledge
    entities: List[Entity] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    beliefs: List[SemanticFact] = field(default_factory=list)
    
    # Recent context
    recent_episodes: List[Episode] = field(default_factory=list)
    recent_facts: List[SemanticFact] = field(default_factory=list)
    
    # Skills/procedures
    available_procedures: List[Procedure] = field(default_factory=list)
    
    # Derived understanding
    patterns: List[Dict] = field(default_factory=list)
    uncertainty: Dict = field(default_factory=dict)
    temporal_context: Dict = field(default_factory=dict)
    
    # Metadata
    built_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    query: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization (for LLM input)."""
        return {
            "entities": [{
                "name": e.canonical_name,
                "type": e.entity_type,
                "confidence": e.confidence,
                "importance": e.importance
            } for e in self.entities],
            "relationships": [{
                "source": "unknown",  # Will be resolved in to_dict_full
                "target": "unknown",
                "type": r.relation_type,
                "confidence": r.confidence
            } for r in self.relationships],
            "beliefs": [{
                "statement": b.statement,
                "confidence": b.confidence
            } for b in self.beliefs[:5]],
            "recent_episodes": [{
                "summary": e.summary,
                "importance": e.importance
            } for e in self.recent_episodes[:3]],
            "available_procedures": [{
                "name": p.name,
                "success_rate": p.success_rate
            } for p in self.available_procedures[:3]],
            "patterns": self.patterns[:3],
            "uncertainty": self.uncertainty,
            "temporal_context": self.temporal_context
        }
    
    def to_dict_full(self, graph: KnowledgeGraph) -> Dict:
        """Full serialization with entity names resolved."""
        data = self.to_dict()
        
        # Resolve entity names in relationships
        resolved_relationships = []
        for rel in self.relationships:
            source = graph.get_entity(rel.source_id)
            target = graph.get_entity(rel.target_id)
            resolved_relationships.append({
                "source": source.canonical_name if source else rel.source_id,
                "target": target.canonical_name if target else rel.target_id,
                "type": rel.relation_type,
                "confidence": rel.confidence
            })
        data["relationships"] = resolved_relationships
        
        return data


class WorldModelBuilder:
    """
    Builds an immutable World Model on-demand.
    Uses the Retriever to fetch relevant knowledge.
    """
    
    def __init__(self, graph: KnowledgeGraph, retriever: Retriever,
                 episodic: EpisodicMemory, semantic: SemanticMemory,
                 procedural: ProceduralMemory):
        self.graph = graph
        self.retriever = retriever
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural
    
    def build(self, query: str, limit: int = 10) -> WorldModel:
        """
        Build a World Model from the current state.
        This is the main entry point.
        """
        # 1. Retrieve relevant knowledge
        retrieved = self.retriever.retrieve(query, limit=limit)
        
        # 2. Build the model
        model = WorldModel(
            query=query,
            entities=retrieved.get("entities", []),
            relationships=retrieved.get("relationships", []),
            beliefs=retrieved.get("semantic_facts", []),
            recent_episodes=retrieved.get("episodes", [])[:5],
            recent_facts=retrieved.get("semantic_facts", [])[:5],
            available_procedures=retrieved.get("procedures", [])
        )
        
        # 3. Detect patterns
        model.patterns = self._detect_patterns(model)
        
        # 4. Assess uncertainty
        model.uncertainty = self._assess_uncertainty(model)
        
        # 5. Build temporal context
        model.temporal_context = self._build_temporal_context()
        
        return model
    
    def build_from_entity(self, entity_name: str, limit: int = 10) -> WorldModel:
        """Build a World Model focused on a specific entity."""
        retrieved = self.retriever.retrieve_by_entity(entity_name, limit=limit)
        
        model = WorldModel(
            query=f"Entity: {entity_name}",
            entities=[retrieved.get("entity")] if retrieved.get("entity") else [],
            relationships=retrieved.get("relationships", []),
            beliefs=retrieved.get("beliefs", [])
        )
        
        # Get recent episodes involving this entity
        model.recent_episodes = self.episodic.get_by_entity(entity_name, limit=5)
        
        # Get relevant procedures
        model.available_procedures = self.procedural.search(entity_name)[:5]
        
        # Detect patterns
        model.patterns = self._detect_patterns(model)
        
        # Assess uncertainty
        model.uncertainty = self._assess_uncertainty(model)
        
        return model
    
    def build_empty(self) -> WorldModel:
        """Build an empty World Model (for initialization)."""
        return WorldModel(query="")
    
    # ─── Pattern Detection ──────────────────────────────────────
    
    def _detect_patterns(self, model: WorldModel) -> List[Dict]:
        """Detect patterns from entities and episodes."""
        patterns = []
        
        # 1. Entity frequency pattern
        if len(model.entities) > 3:
            patterns.append({
                "type": "multiple_entities",
                "description": f"Multiple entities ({len(model.entities)}) are involved in this context",
                "significance": 0.5
            })
        
        # 2. Relationship pattern
        if len(model.relationships) > 2:
            relation_types = [r.relation_type for r in model.relationships]
            unique_types = set(relation_types)
            if len(unique_types) >= 2:
                patterns.append({
                    "type": "relationship_diversity",
                    "description": f"Multiple relationship types: {', '.join(unique_types)}",
                    "significance": 0.6
                })
        
        # 3. Recent episode pattern
        if len(model.recent_episodes) >= 3:
            importances = [e.importance for e in model.recent_episodes]
            avg_importance = sum(importances) / len(importances)
            if avg_importance > 0.7:
                patterns.append({
                    "type": "high_importance_episodes",
                    "description": "Recent episodes are of high importance",
                    "significance": 0.7
                })
        
        return patterns
    
    # ─── Uncertainty Assessment ─────────────────────────────────
    
    def _assess_uncertainty(self, model: WorldModel) -> Dict:
        """Assess what ARIA is uncertain about."""
        uncertainty = {}
        
        # 1. Check if we have entities but no relationships
        if model.entities and not model.relationships:
            uncertainty["missing_relationships"] = {
                "description": "Entities exist but no relationships found",
                "confidence_gap": 0.8
            }
        
        # 2. Check if we have beliefs with low confidence
        for belief in model.beliefs:
            if belief.confidence < 0.5:
                uncertainty[f"low_confidence_belief_{belief.id[:6]}"] = {
                    "description": f"Low confidence in: {belief.statement[:50]}...",
                    "confidence_gap": 0.7
                }
        
        # 3. Check if there are entities with no episodes
        for entity in model.entities:
            episodes = self.episodic.get_by_entity(entity.canonical_name, limit=1)
            if not episodes and len(model.entities) > 1:
                uncertainty[f"entity_without_episodes_{entity.canonical_name}"] = {
                    "description": f"No episodes for entity: {entity.canonical_name}",
                    "confidence_gap": 0.6
                }
                break
        
        return uncertainty
    
    # ─── Temporal Context ──────────────────────────────────────
    
    def _build_temporal_context(self) -> Dict:
        """Build temporal context from recent episodes."""
        recent = self.episodic.get_recent(5)
        
        if not recent:
            return {
                "has_recent_activity": False,
                "recent_count": 0
            }
        
        # Calculate average importance of recent episodes
        importances = [e.importance for e in recent]
        avg_importance = sum(importances) / len(importances)
        
        # Check if there's an episode from today
        now = datetime.now(timezone.utc)
        today_episodes = []
        for ep in recent:
            ep_date = datetime.fromisoformat(ep.timestamp)
            if (now - ep_date).days < 1:
                today_episodes.append(ep)
        
        return {
            "has_recent_activity": True,
            "recent_count": len(recent),
            "average_importance": avg_importance,
            "today_episodes": len(today_episodes),
            "most_recent": recent[0].summary if recent else ""
        }
