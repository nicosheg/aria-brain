# cognitive/memory/storage_adapter.py

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from cognitive.memory.episodic import Episode
from cognitive.memory.semantic import SemanticFact
from cognitive.memory.procedural import Procedure
from cognitive.memory.graph import Entity, Relationship, Assertion


class StorageAdapter(ABC):
    """
    Pluggable storage interface for all memory types.
    
    Implementations:
    - InMemoryAdapter (testing)
    - FirestoreAdapter (production)
    - SQLiteAdapter (local)
    - Neo4jAdapter (graph)
    """
    
    # ─── Entity ──────────────────────────────────────────────────
    @abstractmethod
    def save_entity(self, entity: Entity) -> str:
        """Save an entity. Returns entity ID."""
        pass
    
    @abstractmethod
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by ID."""
        pass
    
    @abstractmethod
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        """Get an entity by canonical name."""
        pass
    
    @abstractmethod
    def get_all_entities(self) -> List[Entity]:
        """Get all entities."""
        pass
    
    @abstractmethod
    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity."""
        pass
    
    # ─── Relationship ────────────────────────────────────────────
    @abstractmethod
    def save_relationship(self, rel: Relationship) -> str:
        """Save a relationship. Returns relationship ID."""
        pass
    
    @abstractmethod
    def get_relationship(self, rel_id: str) -> Optional[Relationship]:
        """Get a relationship by ID."""
        pass
    
    @abstractmethod
    def get_relationships_of(self, entity_id: str) -> List[Relationship]:
        """Get all relationships involving an entity."""
        pass
    
    @abstractmethod
    def get_all_relationships(self) -> List[Relationship]:
        """Get all relationships."""
        pass
    
    @abstractmethod
    def delete_relationship(self, rel_id: str) -> bool:
        """Delete a relationship."""
        pass
    
    # ─── Assertion ───────────────────────────────────────────────
    @abstractmethod
    def save_assertion(self, assertion: Assertion) -> str:
        """Save an assertion. Returns assertion ID."""
        pass
    
    @abstractmethod
    def get_assertion(self, assertion_id: str) -> Optional[Assertion]:
        """Get an assertion by ID."""
        pass
    
    @abstractmethod
    def get_assertions_for(self, entity_id: str) -> List[Assertion]:
        """Get all assertions for an entity."""
        pass
    
    @abstractmethod
    def get_all_assertions(self) -> List[Assertion]:
        """Get all assertions."""
        pass
    
    @abstractmethod
    def delete_assertion(self, assertion_id: str) -> bool:
        """Delete an assertion."""
        pass
    
    # ─── Episode ─────────────────────────────────────────────────
    @abstractmethod
    def save_episode(self, episode: Episode) -> str:
        """Save an episode. Returns episode ID."""
        pass
    
    @abstractmethod
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get an episode by ID."""
        pass
    
    @abstractmethod
    def get_episodes(self, limit: int = 100) -> List[Episode]:
        """Get recent episodes."""
        pass
    
    @abstractmethod
    def get_episodes_by_entity(self, entity_name: str, limit: int = 10) -> List[Episode]:
        """Get episodes involving an entity."""
        pass
    
    @abstractmethod
    def delete_episode(self, episode_id: str) -> bool:
        """Delete an episode."""
        pass
    
    # ─── Semantic Fact ────────────────────────────────────────────
    @abstractmethod
    def save_semantic_fact(self, fact: SemanticFact) -> str:
        """Save a semantic fact. Returns fact ID."""
        pass
    
    @abstractmethod
    def get_semantic_fact(self, fact_id: str) -> Optional[SemanticFact]:
        """Get a semantic fact by ID."""
        pass
    
    @abstractmethod
    def get_semantic_facts(self, limit: int = 100) -> List[SemanticFact]:
        """Get recent semantic facts."""
        pass
    
    @abstractmethod
    def delete_semantic_fact(self, fact_id: str) -> bool:
        """Delete a semantic fact."""
        pass
    
    # ─── Procedure ───────────────────────────────────────────────
    @abstractmethod
    def save_procedure(self, procedure: Procedure) -> str:
        """Save a procedure. Returns procedure ID."""
        pass
    
    @abstractmethod
    def get_procedure(self, procedure_id: str) -> Optional[Procedure]:
        """Get a procedure by ID."""
        pass
    
    @abstractmethod
    def get_procedures(self, limit: int = 100) -> List[Procedure]:
        """Get recent procedures."""
        pass
    
    @abstractmethod
    def delete_procedure(self, procedure_id: str) -> bool:
        """Delete a procedure."""
        pass
    
    # ─── Lifecycle ───────────────────────────────────────────────
    @abstractmethod
    def begin_transaction(self):
        """Begin a transaction."""
        pass
    
    @abstractmethod
    def commit_transaction(self):
        """Commit a transaction."""
        pass
    
    @abstractmethod
    def rollback_transaction(self):
        """Rollback a transaction."""
        pass
    
    @abstractmethod
    def close(self):
        """Close the storage connection."""
        pass


class InMemoryAdapter(StorageAdapter):
    """In-memory implementation for testing."""
    
    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.entities_by_name: Dict[str, str] = {}
        self.relationships: Dict[str, Relationship] = {}
        self.assertions: Dict[str, Assertion] = {}
        self.episodes: Dict[str, Episode] = {}
        self.semantic_facts: Dict[str, SemanticFact] = {}
        self.procedures: Dict[str, Procedure] = {}
        
        self._transaction_active = False
        self._transaction_backup = None
    
    # ─── Entity ──────────────────────────────────────────────────
    def save_entity(self, entity: Entity) -> str:
        self.entities[entity.id] = entity
        self.entities_by_name[entity.canonical_name.lower()] = entity.id
        return entity.id
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self.entities.get(entity_id)
    
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        entity_id = self.entities_by_name.get(name.lower())
        if entity_id:
            return self.entities.get(entity_id)
        return None
    
    def get_all_entities(self) -> List[Entity]:
        return list(self.entities.values())
    
    def delete_entity(self, entity_id: str) -> bool:
        if entity_id in self.entities:
            del self.entities[entity_id]
            return True
        return False
    
    # ─── Relationship ────────────────────────────────────────────
    def save_relationship(self, rel: Relationship) -> str:
        self.relationships[rel.id] = rel
        return rel.id
    
    def get_relationship(self, rel_id: str) -> Optional[Relationship]:
        return self.relationships.get(rel_id)
    
    def get_relationships_of(self, entity_id: str) -> List[Relationship]:
        results = []
        for rel in self.relationships.values():
            if rel.source_id == entity_id or rel.target_id == entity_id:
                results.append(rel)
        return results
    
    def get_all_relationships(self) -> List[Relationship]:
        return list(self.relationships.values())
    
    def delete_relationship(self, rel_id: str) -> bool:
        if rel_id in self.relationships:
            del self.relationships[rel_id]
            return True
        return False
    
    # ─── Assertion ───────────────────────────────────────────────
    def save_assertion(self, assertion: Assertion) -> str:
        self.assertions[assertion.id] = assertion
        return assertion.id
    
    def get_assertion(self, assertion_id: str) -> Optional[Assertion]:
        return self.assertions.get(assertion_id)
    
    def get_assertions_for(self, entity_id: str) -> List[Assertion]:
        results = []
        for assertion in self.assertions.values():
            if entity_id in assertion.evidence:
                results.append(assertion)
        return results
    
    def get_all_assertions(self) -> List[Assertion]:
        return list(self.assertions.values())
    
    def delete_assertion(self, assertion_id: str) -> bool:
        if assertion_id in self.assertions:
            del self.assertions[assertion_id]
            return True
        return False
    
    # ─── Episode ─────────────────────────────────────────────────
    def save_episode(self, episode: Episode) -> str:
        self.episodes[episode.id] = episode
        return episode.id
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        return self.episodes.get(episode_id)
    
    def get_episodes(self, limit: int = 100) -> List[Episode]:
        sorted_eps = sorted(self.episodes.values(), key=lambda x: x.timestamp, reverse=True)
        return sorted_eps[:limit]
    
    def get_episodes_by_entity(self, entity_name: str, limit: int = 10) -> List[Episode]:
        results = []
        for ep in self.episodes.values():
            if entity_name.lower() in [e.lower() for e in ep.entities_involved]:
                results.append(ep)
        return sorted(results, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def delete_episode(self, episode_id: str) -> bool:
        if episode_id in self.episodes:
            del self.episodes[episode_id]
            return True
        return False
    
    # ─── Semantic Fact ───────────────────────────────────────────
    def save_semantic_fact(self, fact: SemanticFact) -> str:
        self.semantic_facts[fact.id] = fact
        return fact.id
    
    def get_semantic_fact(self, fact_id: str) -> Optional[SemanticFact]:
        return self.semantic_facts.get(fact_id)
    
    def get_semantic_facts(self, limit: int = 100) -> List[SemanticFact]:
        sorted_facts = sorted(self.semantic_facts.values(), key=lambda x: x.created, reverse=True)
        return sorted_facts[:limit]
    
    def delete_semantic_fact(self, fact_id: str) -> bool:
        if fact_id in self.semantic_facts:
            del self.semantic_facts[fact_id]
            return True
        return False
    
    # ─── Procedure ───────────────────────────────────────────────
    def save_procedure(self, procedure: Procedure) -> str:
        self.procedures[procedure.id] = procedure
        return procedure.id
    
    def get_procedure(self, procedure_id: str) -> Optional[Procedure]:
        return self.procedures.get(procedure_id)
    
    def get_procedures(self, limit: int = 100) -> List[Procedure]:
        sorted_procs = sorted(self.procedures.values(), key=lambda x: x.created, reverse=True)
        return sorted_procs[:limit]
    
    def delete_procedure(self, procedure_id: str) -> bool:
        if procedure_id in self.procedures:
            del self.procedures[procedure_id]
            return True
        return False
    
    # ─── Lifecycle ───────────────────────────────────────────────
    def begin_transaction(self):
        if self._transaction_active:
            raise Exception("Transaction already active")
        self._transaction_active = True
        self._transaction_backup = {
            "entities": self.entities.copy(),
            "relationships": self.relationships.copy(),
            "assertions": self.assertions.copy(),
            "episodes": self.episodes.copy(),
            "semantic_facts": self.semantic_facts.copy(),
            "procedures": self.procedures.copy()
        }
    
    def commit_transaction(self):
        if not self._transaction_active:
            raise Exception("No active transaction")
        self._transaction_active = False
        self._transaction_backup = None
    
    def rollback_transaction(self):
        if not self._transaction_active:
            raise Exception("No active transaction")
        self.entities = self._transaction_backup["entities"]
        self.relationships = self._transaction_backup["relationships"]
        self.assertions = self._transaction_backup["assertions"]
        self.episodes = self._transaction_backup["episodes"]
        self.semantic_facts = self._transaction_backup["semantic_facts"]
        self.procedures = self._transaction_backup["procedures"]
        self._transaction_active = False
        self._transaction_backup = None
    
    def close(self):
        self.entities.clear()
        self.relationships.clear()
        self.assertions.clear()
        self.episodes.clear()
        self.semantic_facts.clear()
        self.procedures.clear()
