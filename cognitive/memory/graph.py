# cognitive/memory/graph.py

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import uuid
from datetime import datetime, timezone
from .assertions import Assertion


@dataclass
class Entity:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    canonical_name: str = ""
    aliases: List[str] = field(default_factory=list)
    entity_type: str = "concept"
    properties: Dict = field(default_factory=dict)
    confidence: float = 0.5          # How confident we are this entity exists
    importance: float = 0.5          # How important this entity is
    version: int = 1
    history: List[Dict] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_alias(self, alias: str):
        if alias not in self.aliases:
            self.aliases.append(alias)
            self._bump_version()

    def _bump_version(self):
        self.history.append({
            "version": self.version,
            "timestamp": self.last_updated,
            "properties": self.properties.copy()
        })
        self.version += 1
        self.last_updated = datetime.now(timezone.utc).isoformat()


@dataclass
class Relationship:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    relation_type: str = ""
    confidence: float = 0.5
    evidence: List[str] = field(default_factory=list)
    source: str = "conversation"
    created_by: str = ""
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1


@dataclass
class ProposedChange:
    change_type: str
    payload: Dict
    evidence: List[str] = field(default_factory=list)
    source: str = "conversation"
    observation_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class KnowledgeGraph:
    
    def __init__(self):
        self.entities_by_id: Dict[str, Entity] = {}
        self.entities_by_alias: Dict[str, str] = {}
        self.relationships_by_id: Dict[str, Relationship] = {}
        self.assertions_by_id: Dict[str, Assertion] = {}
        self.event_log: List[Dict] = []
        self._transaction_active = False
        self._transaction_backup = None

    # ─── Transaction Support ────────────────────────────────────
    
    def begin_transaction(self):
        if self._transaction_active:
            raise Exception("Transaction already active")
        self._transaction_active = True
        self._transaction_backup = {
            "entities": self.entities_by_id.copy(),
            "relationships": self.relationships_by_id.copy(),
            "assertions": self.assertions_by_id.copy(),
            "aliases": self.entities_by_alias.copy()
        }

    def commit_transaction(self):
        if not self._transaction_active:
            raise Exception("No active transaction")
        self._transaction_active = False
        self._transaction_backup = None

    def rollback_transaction(self):
        if not self._transaction_active:
            raise Exception("No active transaction")
        self.entities_by_id = self._transaction_backup["entities"]
        self.relationships_by_id = self._transaction_backup["relationships"]
        self.assertions_by_id = self._transaction_backup["assertions"]
        self.entities_by_alias = self._transaction_backup["aliases"]
        self._transaction_active = False
        self._transaction_backup = None

    # ─── Entity Operations ──────────────────────────────────────
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self.entities_by_id.get(entity_id)

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        normalized = self._normalize(name)
        if normalized in self.entities_by_alias:
            return self.entities_by_id.get(self.entities_by_alias[normalized])
        return None

    def get_or_create_entity(self, name: str, entity_type: str = "concept",
                            properties: Dict = None, confidence: float = 0.5,
                            importance: float = 0.5) -> Entity:
        existing = self.get_entity_by_name(name)
        if existing:
            existing.confidence = max(existing.confidence, confidence)
            existing.importance = max(existing.importance, importance)
            existing.properties.update(properties or {})
            existing.last_updated = datetime.now(timezone.utc).isoformat()
            return existing
        entity = Entity(
            canonical_name=name,
            entity_type=entity_type,
            properties=properties or {},
            confidence=confidence,
            importance=importance
        )
        self.entities_by_id[entity.id] = entity
        self.entities_by_alias[self._normalize(name)] = entity.id
        return entity

    # ─── Relationship Operations ───────────────────────────────
    
    def get_relationship(self, rel_id: str) -> Optional[Relationship]:
        return self.relationships_by_id.get(rel_id)

    def get_relationships_of(self, entity_id: str) -> List[Relationship]:
        return [r for r in self.relationships_by_id.values()
                if r.source_id == entity_id or r.target_id == entity_id]

    # ─── Assertion Operations ──────────────────────────────────
    
    def get_assertion(self, assertion_id: str) -> Optional[Assertion]:
        return self.assertions_by_id.get(assertion_id)

    def get_assertions_for(self, entity_id: str) -> List[Assertion]:
        results = []
        for assertion in self.assertions_by_id.values():
            if entity_id in assertion.evidence:
                results.append(assertion)
        return results

    # ─── Proposed Changes ──────────────────────────────────────
    
    def propose_change(self, change_type: str, payload: Dict,
                       evidence: List[str] = None, source: str = "conversation",
                       observation_id: str = "") -> ProposedChange:
        return ProposedChange(
            change_type=change_type,
            payload=payload,
            evidence=evidence or [],
            source=source,
            observation_id=observation_id
        )

    def validate_and_commit(self, change: ProposedChange) -> Tuple[bool, str]:
        if not self._check_invariants(change):
            return False, "Invariant violation"
        try:
            self._apply_change(change)
            self.event_log.append({
                "type": change.change_type,
                "payload": change.payload,
                "timestamp": change.timestamp,
                "observation_id": change.observation_id
            })
            return True, "Committed successfully"
        except Exception as e:
            return False, str(e)

    # ─── Invariant Checks ──────────────────────────────────────
    
    def _check_invariants(self, change: ProposedChange) -> bool:
        if change.change_type == "CREATE_ENTITY":
            name = change.payload.get("canonical_name")
            if not name:
                return False
            if self._normalize(name) in self.entities_by_alias:
                return False
        if change.change_type == "ADD_ASSERTION":
            confidence = change.payload.get("confidence", 0)
            if confidence < 0 or confidence > 1:
                return False
        if change.change_type == "ADD_RELATIONSHIP":
            source_id = change.payload.get("source_id")
            target_id = change.payload.get("target_id")
            if source_id not in self.entities_by_id:
                return False
            if target_id not in self.entities_by_id:
                return False
        return True

    def _apply_change(self, change: ProposedChange):
        if change.change_type == "CREATE_ENTITY":
            entity = Entity(**change.payload)
            self.entities_by_id[entity.id] = entity
            self.entities_by_alias[self._normalize(entity.canonical_name)] = entity.id
        elif change.change_type == "ADD_RELATIONSHIP":
            rel = Relationship(**change.payload)
            self.relationships_by_id[rel.id] = rel
        elif change.change_type == "ADD_ASSERTION":
            assertion = Assertion(**change.payload)
            self.assertions_by_id[assertion.id] = assertion
        elif change.change_type == "MERGE_ENTITY":
            survivor_id = change.payload.get("survivor_id")
            merged_ids = change.payload.get("merged_ids", [])
            for mid in merged_ids:
                if mid in self.entities_by_id:
                    for rel in self.relationships_by_id.values():
                        if rel.source_id == mid:
                            rel.source_id = survivor_id
                        if rel.target_id == mid:
                            rel.target_id = survivor_id
                    del self.entities_by_id[mid]

    def _normalize(self, name: str) -> str:
        return name.lower().strip().replace(" ", "_")
