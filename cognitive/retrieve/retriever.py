# cognitive/retrieve/retriever.py

from typing import Dict, List, Optional, Any, Tuple
from cognitive.memory.graph import KnowledgeGraph, Entity, Relationship
from cognitive.memory.episodic import EpisodicMemory, Episode
from cognitive.memory.semantic import SemanticMemory, SemanticFact
from cognitive.memory.procedural import ProceduralMemory, Procedure
from cognitive.core.config import ARIAConfig


class Retriever:
    """
    Unified retriever.
    - Traverses the Knowledge Graph
    - Fetches relevant episodes, semantic facts, and procedures
    - Ranks results by relevance
    - Returns a unified context for reasoning
    """
    
    def __init__(self, graph: KnowledgeGraph, episodic: EpisodicMemory,
                 semantic: SemanticMemory, procedural: ProceduralMemory):
        self.graph = graph
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural
        
        # Weights for ranking (configurable)
        self.graph_weight = 0.45
        self.semantic_weight = 0.30
        self.recency_weight = 0.15
        self.importance_weight = 0.10
    
    def retrieve(self, query: str, limit: int = 10) -> Dict:
        """
        Retrieve relevant information for a query.
        Returns a unified context dictionary.
        """
        results = {
            "entities": [],
            "relationships": [],
            "episodes": [],
            "semantic_facts": [],
            "procedures": [],
            "concepts": []
        }
        
        # 1. Find entities mentioned in query
        query_words = set(query.lower().split())
        for entity in self.graph.entities_by_id.values():
            entity_words = set(entity.canonical_name.lower().split())
            # Also check aliases
            for alias in entity.aliases:
                entity_words.update(alias.lower().split())
            
            overlap = len(query_words & entity_words)
            if overlap > 0:
                results["entities"].append({
                    "entity": entity,
                    "relevance": overlap / max(len(query_words), 1)
                })
        
        # 2. Get relationships for found entities
        for item in results["entities"]:
            entity = item["entity"]
            rels = self.graph.get_relationships_of(entity.id)
            for rel in rels:
                results["relationships"].append(rel)
        
        # 3. Get episodes involving found entities
        entity_names = [e["entity"].canonical_name for e in results["entities"]]
        for name in entity_names:
            eps = self.episodic.get_by_entity(name, limit=5)
            results["episodes"].extend(eps)
        
        # 4. Get relevant semantic facts
        facts = self.semantic.get_relevant(query, limit=5)
        results["semantic_facts"].extend(facts)
        
        # 5. Get relevant procedures
        procs = self.procedural.search(query)
        results["procedures"].extend(procs)
        
        # 6. Rank and limit results
        results["entities"] = self._rank_entities(results["entities"])
        results["relationships"] = self._rank_relationships(results["relationships"], query)
        results["episodes"] = self._rank_episodes(results["episodes"], query)
        results["semantic_facts"] = self._rank_semantic_facts(results["semantic_facts"], query)
        results["procedures"] = self._rank_procedures(results["procedures"], query)
        
        # 7. Limit each category
        results["entities"] = [e["entity"] for e in results["entities"][:limit]]
        results["relationships"] = results["relationships"][:limit]
        results["episodes"] = results["episodes"][:limit]
        results["semantic_facts"] = results["semantic_facts"][:limit]
        results["procedures"] = results["procedures"][:limit]
        
        return results
    
    def retrieve_by_entity(self, entity_name: str, limit: int = 10) -> Dict:
        """
        Retrieve information about a specific entity.
        """
        entity = self.graph.get_entity_by_name(entity_name)
        if not entity:
            return {}
        
        results = {
            "entity": entity,
            "relationships": [],
            "episodes": [],
            "beliefs": []
        }
        
        # Get relationships
        rels = self.graph.get_relationships_of(entity.id)
        results["relationships"] = rels[:limit]
        
        # Get episodes
        eps = self.episodic.get_by_entity(entity_name, limit=limit)
        results["episodes"] = eps
        
        # Get beliefs (semantic facts)
        facts = self.semantic.get_relevant(entity_name, limit=limit)
        results["beliefs"] = facts
        
        return results
    
    def retrieve_similar(self, query: str, threshold: float = 0.3) -> List[Dict]:
        """
        Retrieve similar concepts/entities.
        """
        results = []
        query_words = set(query.lower().split())
        
        for entity in self.graph.entities_by_id.values():
            entity_words = set(entity.canonical_name.lower().split())
            for alias in entity.aliases:
                entity_words.update(alias.lower().split())
            
            overlap = len(query_words & entity_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                if score >= threshold:
                    results.append({
                        "entity": entity,
                        "score": score,
                        "type": "graph_match"
                    })
        
        return sorted(results, key=lambda x: x["score"], reverse=True)[:10]
    
    # ─── Ranking Methods ──────────────────────────────────────────
    
    def _rank_entities(self, entities: List[Dict]) -> List[Dict]:
        """Rank entities by relevance and importance."""
        for item in entities:
            entity = item["entity"]
            item["rank"] = item.get("relevance", 0) * (0.6 + entity.importance * 0.4)
        return sorted(entities, key=lambda x: x["rank"], reverse=True)
    
    def _rank_relationships(self, relationships: List[Relationship], query: str) -> List[Relationship]:
        """Rank relationships by recency and confidence."""
        scored = []
        query_words = set(query.lower().split())
        
        for rel in relationships:
            # Calculate score based on evidence and query overlap
            evidence_score = 0
            for evidence in rel.evidence:
                evidence_words = set(evidence.lower().split())
                overlap = len(query_words & evidence_words)
                evidence_score += overlap / max(len(query_words), 1)
            
            if rel.evidence:
                evidence_score = evidence_score / len(rel.evidence)
            
            score = (rel.confidence * 0.6) + (evidence_score * 0.4)
            scored.append((score, rel))
        
        scored.sort(reverse=True, key=lambda x: x[0])
        return [rel for _, rel in scored]
    
    def _rank_episodes(self, episodes: List[Episode], query: str) -> List[Episode]:
        """Rank episodes by recency, importance, and query relevance."""
        scored = []
        query_words = set(query.lower().split())
        
        for ep in episodes:
            # Relevance score
            ep_words = set(ep.full_text.lower().split())
            overlap = len(query_words & ep_words)
            relevance = overlap / max(len(query_words), 1) if query_words else 0.5
            
            # Importance score
            importance = ep.importance
            
            # Combined score
            score = (relevance * 0.4) + (importance * 0.3)
            scored.append((score, ep))
        
        scored.sort(reverse=True, key=lambda x: x[0])
        return [ep for _, ep in scored]
    
    def _rank_semantic_facts(self, facts: List[SemanticFact], query: str) -> List[SemanticFact]:
        """Rank semantic facts by relevance and confidence."""
        scored = []
        query_words = set(query.lower().split())
        
        for fact in facts:
            fact_words = set(fact.statement.lower().split())
            overlap = len(query_words & fact_words)
            relevance = overlap / max(len(query_words), 1) if query_words else 0.5
            
            score = (relevance * 0.5) + (fact.confidence * 0.5)
            scored.append((score, fact))
        
        scored.sort(reverse=True, key=lambda x: x[0])
        return [fact for _, fact in scored]
    
    def _rank_procedures(self, procedures: List[Procedure], query: str) -> List[Procedure]:
        """Rank procedures by relevance and success rate."""
        scored = []
        query_words = set(query.lower().split())
        
        for proc in procedures:
            # Check name, description, when_to_use
            text = f"{proc.name} {proc.description} {proc.when_to_use}"
            proc_words = set(text.lower().split())
            overlap = len(query_words & proc_words)
            relevance = overlap / max(len(query_words), 1) if query_words else 0.5
            
            score = (relevance * 0.6) + (proc.success_rate * 0.4)
            scored.append((score, proc))
        
        scored.sort(reverse=True, key=lambda x: x[0])
        return [proc for _, proc in scored]
    
    def to_dict(self, results: Dict) -> Dict:
        """Convert results to dictionary for serialization."""
        return {
            "entities": [{
                "id": e.id,
                "canonical_name": e.canonical_name,
                "entity_type": e.entity_type
            } for e in results.get("entities", [])],
            "relationships": [{
                "source": self.graph.get_entity(rel.source_id).canonical_name if self.graph.get_entity(rel.source_id) else rel.source_id,
                "target": self.graph.get_entity(rel.target_id).canonical_name if self.graph.get_entity(rel.target_id) else rel.target_id,
                "relation_type": rel.relation_type
            } for rel in results.get("relationships", [])],
            "episodes": [{
                "summary": ep.summary,
                "importance": ep.importance
            } for ep in results.get("episodes", [])],
            "semantic_facts": [{
                "statement": f.statement,
                "confidence": f.confidence
            } for f in results.get("semantic_facts", [])],
            "procedures": [{
                "name": p.name,
                "success_rate": p.success_rate
            } for p in results.get("procedures", [])]
        }
