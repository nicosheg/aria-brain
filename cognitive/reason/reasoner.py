# cognitive/reason/reasoner.py

from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
from cognitive.memory.graph import KnowledgeGraph, Entity, Relationship
from cognitive.memory.episodic import EpisodicMemory, Episode
from cognitive.memory.semantic import SemanticMemory, SemanticFact
from cognitive.retrieve.world_model import WorldModel


class Reasoner:
    """
    The Reasoner detects contradictions, patterns, and hypotheses.
    It operates on the World Model and the knowledge graph.
    """
    
    def __init__(self, graph: KnowledgeGraph, episodic: EpisodicMemory, semantic: SemanticMemory):
        self.graph = graph
        self.episodic = episodic
        self.semantic = semantic
    
    def reason(self, world: WorldModel) -> Dict:
        """
        Main reasoning entry point.
        Returns a summary of reasoning results.
        """
        result = {
            "contradictions": self.detect_contradictions(world),
            "patterns": self.detect_patterns(world),
            "hypotheses": self.generate_hypotheses(world),
            "uncertainty": self.assess_uncertainty(world),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        return result
    
    # ─── Contradiction Detection ────────────────────────────────
    
    def detect_contradictions(self, world: WorldModel) -> List[Dict]:
        """
        Find contradictory relationships or beliefs.
        Returns list of contradiction descriptions.
        """
        contradictions = []
        
        # 1. Check relationships for opposing types
        rels = world.relationships
        for i, r1 in enumerate(rels):
            for r2 in rels[i+1:]:
                # Same source and target?
                if r1.source_id == r2.source_id and r1.target_id == r2.target_id:
                    # Check if relation types are opposites
                    if self._are_opposites(r1.relation_type, r2.relation_type):
                        contradictions.append({
                            "type": "relationship_contradiction",
                            "source": self._get_entity_name(r1.source_id),
                            "target": self._get_entity_name(r1.target_id),
                            "relation1": r1.relation_type,
                            "relation2": r2.relation_type,
                            "confidence1": r1.confidence,
                            "confidence2": r2.confidence,
                            "evidence": r1.evidence + r2.evidence
                        })
        
        # 2. Check beliefs (semantic facts) for contradiction
        beliefs = world.beliefs
        for i, b1 in enumerate(beliefs):
            for b2 in beliefs[i+1:]:
                if self._are_opposite_statements(b1.statement, b2.statement):
                    contradictions.append({
                        "type": "belief_contradiction",
                        "statement1": b1.statement,
                        "statement2": b2.statement,
                        "confidence1": b1.confidence,
                        "confidence2": b2.confidence,
                        "evidence": b1.source_episode_ids + b2.source_episode_ids
                    })
        
        return contradictions
    
    # ─── Pattern Detection ──────────────────────────────────────
    
    def detect_patterns(self, world: WorldModel) -> List[Dict]:
        """
        Detect patterns from episodes and entities.
        """
        patterns = []
        
        # 1. Recurring entity mentions
        episodes = world.recent_episodes
        entity_counts: Dict[str, int] = {}
        for ep in episodes:
            for ent in ep.entities_involved:
                entity_counts[ent] = entity_counts.get(ent, 0) + 1
        
        for entity, count in entity_counts.items():
            if count >= 3:
                patterns.append({
                    "type": "recurring_entity",
                    "entity": entity,
                    "count": count,
                    "significance": min(1.0, count / 5),
                    "evidence": [ep.id for ep in episodes if entity in ep.entities_involved]
                })
        
        # 2. Recurring topics (keywords)
        topic_counts: Dict[str, int] = {}
        for ep in episodes:
            words = ep.full_text.lower().split()
            for word in words:
                if len(word) > 4:  # ignore short words
                    topic_counts[word] = topic_counts.get(word, 0) + 1
        
        for topic, count in topic_counts.items():
            if count >= 3:
                patterns.append({
                    "type": "recurring_topic",
                    "topic": topic,
                    "count": count,
                    "significance": min(1.0, count / 5),
                    "evidence": [ep.id for ep in episodes if topic in ep.full_text.lower()]
                })
        
        # 3. Temporal patterns: e.g., episodes becoming more important
        if len(episodes) >= 3:
            importances = [ep.importance for ep in episodes]
            if importances[-1] > importances[0] * 1.2:
                patterns.append({
                    "type": "increasing_importance",
                    "description": "Recent episodes have higher importance",
                    "significance": 0.7,
                    "evidence": [ep.id for ep in episodes[-3:]]
                })
        
        return patterns
    
    # ─── Hypothesis Generation ──────────────────────────────────
    
    def generate_hypotheses(self, world: WorldModel) -> List[Dict]:
        """
        Generate new hypotheses (possible relationships or beliefs).
        """
        hypotheses = []
        
        # 1. If entity A builds B and B helps C, hypothesize A helps C
        rels = world.relationships
        for r1 in rels:
            if r1.relation_type in ["builds", "creates", "develops"]:
                for r2 in rels:
                    if r2.source_id == r1.target_id and r2.relation_type in ["helps", "solves"]:
                        # Check if relationship already exists
                        source_name = self._get_entity_name(r1.source_id)
                        target_name = self._get_entity_name(r2.target_id)
                        if not self._relationship_exists(source_name, target_name, "helps"):
                            hypotheses.append({
                                "type": "inferred_relationship",
                                "source": source_name,
                                "target": target_name,
                                "relation": "helps",
                                "confidence": min(r1.confidence, r2.confidence) * 0.8,
                                "evidence": [r1.id, r2.id],
                                "explanation": f"{source_name} builds {self._get_entity_name(r1.target_id)} which helps {target_name}"
                            })
        
        # 2. If entity wants X and X requires Y, hypothesize entity needs Y
        for r1 in rels:
            if r1.relation_type == "wants":
                for r2 in rels:
                    if r2.source_id == r1.target_id and r2.relation_type == "requires":
                        source_name = self._get_entity_name(r1.source_id)
                        target_name = self._get_entity_name(r2.target_id)
                        if not self._relationship_exists(source_name, target_name, "needs"):
                            hypotheses.append({
                                "type": "inferred_relationship",
                                "source": source_name,
                                "target": target_name,
                                "relation": "needs",
                                "confidence": min(r1.confidence, r2.confidence) * 0.7,
                                "evidence": [r1.id, r2.id],
                                "explanation": f"{source_name} wants {self._get_entity_name(r1.target_id)} which requires {target_name}"
                            })
        
        return hypotheses
    
    # ─── Uncertainty Assessment ──────────────────────────────────
    
    def assess_uncertainty(self, world: WorldModel) -> Dict:
        """
        Assess what ARIA is uncertain about.
        Returns a dictionary of uncertainty items with confidence gaps.
        """
        uncertainty = {}
        
        # 1. Check for entities with no relationships
        for entity in world.entities:
            rels = self.graph.get_relationships_of(entity.id)
            if not rels:
                uncertainty[f"entity_{entity.canonical_name}_no_relations"] = {
                    "type": "missing_relationships",
                    "entity": entity.canonical_name,
                    "description": f"No relationships found for {entity.canonical_name}",
                    "confidence_gap": 0.8
                }
        
        # 2. Check for relationships with low confidence
        for rel in world.relationships:
            if rel.confidence < 0.4:
                source = self.graph.get_entity(rel.source_id)
                target = self.graph.get_entity(rel.target_id)
                uncertainty[f"rel_{rel.id}"] = {
                    "type": "low_confidence_relationship",
                    "source": source.canonical_name if source else rel.source_id,
                    "target": target.canonical_name if target else rel.target_id,
                    "relation": rel.relation_type,
                    "confidence": rel.confidence,
                    "confidence_gap": 1 - rel.confidence
                }
        
        # 3. Check for contradictions in evidence
        for belief in world.beliefs:
            if belief.confidence < 0.5:
                uncertainty[f"belief_{belief.id[:6]}"] = {
                    "type": "low_confidence_belief",
                    "statement": belief.statement,
                    "confidence": belief.confidence,
                    "confidence_gap": 1 - belief.confidence
                }
        
        return uncertainty
    
    # ─── Helpers ──────────────────────────────────────────────────
    
    def _get_entity_name(self, entity_id: str) -> str:
        entity = self.graph.get_entity(entity_id)
        return entity.canonical_name if entity else entity_id
    
    def _are_opposites(self, rel1: str, rel2: str) -> bool:
        opposites = {
            ("likes", "dislikes"),
            ("wants", "doesnt_want"),
            ("can", "cannot"),
            ("is", "isnt"),
            ("has", "hasnt"),
            ("builds", "destroys"),
            ("helps", "hinders")
        }
        return (rel1, rel2) in opposites or (rel2, rel1) in opposites
    
    def _are_opposite_statements(self, s1: str, s2: str) -> bool:
        # Simple: check if one contains negation of the other
        s1_lower = s1.lower()
        s2_lower = s2.lower()
        if "not" in s1_lower and s2_lower in s1_lower.replace("not", "").strip():
            return True
        if "not" in s2_lower and s1_lower in s2_lower.replace("not", "").strip():
            return True
        return False
    
    def _relationship_exists(self, source_name: str, target_name: str, relation_type: str) -> bool:
        source = self.graph.get_entity_by_name(source_name)
        target = self.graph.get_entity_by_name(target_name)
        if not source or not target:
            return False
        for rel in self.graph.get_relationships_of(source.id):
            if rel.target_id == target.id and rel.relation_type == relation_type:
                return True
        return False
