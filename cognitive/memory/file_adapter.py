# cognitive/memory/file_adapter.py

import json
import os
from typing import Dict, List, Optional
from cognitive.memory.graph import Entity, Relationship
from cognitive.memory.episodic import Episode
from cognitive.memory.semantic import SemanticFact
from cognitive.memory.procedural import Procedure
from cognitive.memory.assertions import Assertion, AssertionType


class FileAdapter:
    """
    Local file storage adapter for ARIA.
    Saves all memory to a JSON file for persistence across restarts.
    """
    
    def __init__(self, user_id: str, file_path: str = None):
        self.user_id = user_id
        if file_path is None:
            file_path = f"aria_memory_{user_id}.json"
        self.file_path = file_path
        self._data = self._load()
    
    def _load(self) -> Dict:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "entities": [],
            "relationships": [],
            "assertions": [],
            "episodes": [],
            "semantic_facts": [],
            "procedures": []
        }
    
    def _save(self):
        with open(self.file_path, 'w') as f:
            json.dump(self._data, f, indent=2, default=str)
    
    # ─── Entity ──────────────────────────────────────────────────
    def save_entity(self, entity: Entity) -> str:
        # Remove existing entity with same id
        self._data["entities"] = [e for e in self._data["entities"] if e.get("id") != entity.id]
        self._data["entities"].append({
            "id": entity.id,
            "canonical_name": entity.canonical_name,
            "aliases": entity.aliases,
            "entity_type": entity.entity_type,
            "properties": entity.properties,
            "confidence": entity.confidence,
            "importance": entity.importance,
            "created": entity.created,
            "last_updated": entity.last_updated,
            "version": entity.version
        })
        self._save()
        return entity.id
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        for e in self._data["entities"]:
            if e["id"] == entity_id:
                return Entity(**e)
        return None
    
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        for e in self._data["entities"]:
            if e["canonical_name"].lower() == name.lower():
                return Entity(**e)
        return None
    
    def get_all_entities(self) -> List[Entity]:
        return [Entity(**e) for e in self._data["entities"]]
    
    def delete_entity(self, entity_id: str) -> bool:
        self._data["entities"] = [e for e in self._data["entities"] if e["id"] != entity_id]
        self._save()
        return True
    
    # ─── Relationship ────────────────────────────────────────────
    def save_relationship(self, rel: Relationship) -> str:
        self._data["relationships"] = [r for r in self._data["relationships"] if r.get("id") != rel.id]
        self._data["relationships"].append({
            "id": rel.id,
            "source_id": rel.source_id,
            "target_id": rel.target_id,
            "relation_type": rel.relation_type,
            "confidence": rel.confidence,
            "evidence": rel.evidence,
            "source": rel.source,
            "created_by": rel.created_by,
            "created": rel.created,
            "last_updated": rel.last_updated,
            "version": rel.version
        })
        self._save()
        return rel.id
    
    def get_relationship(self, rel_id: str) -> Optional[Relationship]:
        for r in self._data["relationships"]:
            if r["id"] == rel_id:
                return Relationship(**r)
        return None
    
    def get_relationships_of(self, entity_id: str) -> List[Relationship]:
        rels = []
        for r in self._data["relationships"]:
            if r["source_id"] == entity_id or r["target_id"] == entity_id:
                rels.append(Relationship(**r))
        return rels
    
    def get_all_relationships(self) -> List[Relationship]:
        return [Relationship(**r) for r in self._data["relationships"]]
    
    def delete_relationship(self, rel_id: str) -> bool:
        self._data["relationships"] = [r for r in self._data["relationships"] if r["id"] != rel_id]
        self._save()
        return True
    
    # ─── Episode ─────────────────────────────────────────────────
    def save_episode(self, episode: Episode) -> str:
        self._data["episodes"] = [e for e in self._data["episodes"] if e.get("id") != episode.id]
        self._data["episodes"].append({
            "id": episode.id,
            "summary": episode.summary,
            "full_text": episode.full_text,
            "timestamp": episode.timestamp,
            "importance": episode.importance,
            "source": episode.source,
            "entities_involved": episode.entities_involved,
            "relationships_changed": episode.relationships_changed,
            "beliefs_affected": episode.beliefs_affected,
            "metadata": episode.metadata
        })
        self._save()
        return episode.id
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        for e in self._data["episodes"]:
            if e["id"] == episode_id:
                return Episode(**e)
        return None
    
    def get_episodes(self, limit: int = 100) -> List[Episode]:
        sorted_eps = sorted(self._data["episodes"], key=lambda x: x.get("timestamp", ""), reverse=True)
        return [Episode(**e) for e in sorted_eps[:limit]]
    
    def get_episodes_by_entity(self, entity_name: str, limit: int = 10) -> List[Episode]:
        results = []
        for e in self._data["episodes"]:
            if entity_name.lower() in [x.lower() for x in e.get("entities_involved", [])]:
                results.append(Episode(**e))
        return results[:limit]
    
    def delete_episode(self, episode_id: str) -> bool:
        self._data["episodes"] = [e for e in self._data["episodes"] if e["id"] != episode_id]
        self._save()
        return True
    
    # ─── Semantic Fact ───────────────────────────────────────────
    def save_semantic_fact(self, fact: SemanticFact) -> str:
        self._data["semantic_facts"] = [f for f in self._data["semantic_facts"] if f.get("id") != fact.id]
        self._data["semantic_facts"].append({
            "id": fact.id,
            "statement": fact.statement,
            "confidence": fact.confidence,
            "source_episode_ids": fact.source_episode_ids,
            "created": fact.created,
            "last_updated": fact.last_updated,
            "version": fact.version
        })
        self._save()
        return fact.id
    
    def get_semantic_fact(self, fact_id: str) -> Optional[SemanticFact]:
        for f in self._data["semantic_facts"]:
            if f["id"] == fact_id:
                return SemanticFact(**f)
        return None
    
    def get_semantic_facts(self, limit: int = 100) -> List[SemanticFact]:
        sorted_facts = sorted(self._data["semantic_facts"], key=lambda x: x.get("created", ""), reverse=True)
        return [SemanticFact(**f) for f in sorted_facts[:limit]]
    
    def delete_semantic_fact(self, fact_id: str) -> bool:
        self._data["semantic_facts"] = [f for f in self._data["semantic_facts"] if f["id"] != fact_id]
        self._save()
        return True
    
    # ─── Procedure ───────────────────────────────────────────────
    def save_procedure(self, procedure: Procedure) -> str:
        self._data["procedures"] = [p for p in self._data["procedures"] if p.get("id") != procedure.id]
        self._data["procedures"].append({
            "id": procedure.id,
            "name": procedure.name,
            "description": procedure.description,
            "steps": procedure.steps,
            "when_to_use": procedure.when_to_use,
            "success_rate": procedure.success_rate,
            "times_used": procedure.times_used,
            "times_succeeded": procedure.times_succeeded,
            "created": procedure.created,
            "last_updated": procedure.last_updated,
            "version": procedure.version
        })
        self._save()
        return procedure.id
    
    def get_procedure(self, procedure_id: str) -> Optional[Procedure]:
        for p in self._data["procedures"]:
            if p["id"] == procedure_id:
                return Procedure(**p)
        return None
    
    def get_procedures(self, limit: int = 100) -> List[Procedure]:
        sorted_procs = sorted(self._data["procedures"], key=lambda x: x.get("created", ""), reverse=True)
        return [Procedure(**p) for p in sorted_procs[:limit]]
    
    def delete_procedure(self, procedure_id: str) -> bool:
        self._data["procedures"] = [p for p in self._data["procedures"] if p["id"] != procedure_id]
        self._save()
        return True
    
    # ─── Lifecycle ───────────────────────────────────────────────
    def begin_transaction(self): pass
    def commit_transaction(self): pass
    def rollback_transaction(self): pass
    def close(self): pass
