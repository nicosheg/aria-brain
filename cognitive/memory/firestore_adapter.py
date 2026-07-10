# cognitive/memory/firestore_adapter.py

from typing import Dict, List, Optional
import json
from datetime import datetime, timezone

# Import Firestore from brain — catches error if not available
try:
    from brain import db, firestore
except ImportError:
    db = None
    firestore = None

from cognitive.memory.graph import Entity, Relationship
from cognitive.memory.episodic import Episode
from cognitive.memory.semantic import SemanticFact
from cognitive.memory.procedural import Procedure
from cognitive.memory.assertions import Assertion


class FirestoreAdapter:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.db = db
        self.collection = f"users/{user_id}/cognition"
        
        if db is None:
            print(f"[FirestoreAdapter] Firestore not available for user {user_id}")
    
    # ─── Entity ──────────────────────────────────────────────────
    def save_entity(self, entity: Entity) -> str:
        if not self.db:
            return entity.id
        try:
            doc_ref = self.db.collection(self.collection).document("entities") \
                .collection("all").document(entity.id)
            doc_ref.set({
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
        except Exception as e:
            print(f"[FirestoreAdapter] Save entity error: {e}")
        return entity.id
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        if not self.db:
            return None
        try:
            doc = self.db.collection(self.collection).document("entities") \
                .collection("all").document(entity_id).get()
            if doc.exists:
                data = doc.to_dict()
                return Entity(**data)
        except Exception as e:
            print(f"[FirestoreAdapter] Get entity error: {e}")
        return None
    
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        if not self.db:
            return None
        try:
            docs = self.db.collection(self.collection).document("entities") \
                .collection("all").where("canonical_name", "==", name).limit(1).stream()
            for doc in docs:
                data = doc.to_dict()
                return Entity(**data)
        except Exception as e:
            print(f"[FirestoreAdapter] Get entity by name error: {e}")
        return None
    
    def get_all_entities(self) -> List[Entity]:
        if not self.db:
            return []
        try:
            docs = self.db.collection(self.collection).document("entities") \
                .collection("all").stream()
            entities = []
            for doc in docs:
                data = doc.to_dict()
                entities.append(Entity(**data))
            return entities
        except Exception as e:
            print(f"[FirestoreAdapter] Get all entities error: {e}")
            return []
    
    def delete_entity(self, entity_id: str) -> bool:
        if not self.db:
            return False
        try:
            self.db.collection(self.collection).document("entities") \
                .collection("all").document(entity_id).delete()
            return True
        except Exception as e:
            print(f"[FirestoreAdapter] Delete entity error: {e}")
            return False
    
    # ─── Relationship ────────────────────────────────────────────
    def save_relationship(self, rel: Relationship) -> str:
        if not self.db:
            return rel.id
        try:
            doc_ref = self.db.collection(self.collection).document("relationships") \
                .collection("all").document(rel.id)
            doc_ref.set({
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
        except Exception as e:
            print(f"[FirestoreAdapter] Save relationship error: {e}")
        return rel.id
    
    def get_relationship(self, rel_id: str) -> Optional[Relationship]:
        if not self.db:
            return None
        try:
            doc = self.db.collection(self.collection).document("relationships") \
                .collection("all").document(rel_id).get()
            if doc.exists:
                data = doc.to_dict()
                return Relationship(**data)
        except Exception as e:
            print(f"[FirestoreAdapter] Get relationship error: {e}")
        return None
    
    def get_relationships_of(self, entity_id: str) -> List[Relationship]:
        if not self.db:
            return []
        try:
            docs = self.db.collection(self.collection).document("relationships") \
                .collection("all").where("source_id", "==", entity_id).stream()
            rels = []
            for doc in docs:
                data = doc.to_dict()
                rels.append(Relationship(**data))
            docs2 = self.db.collection(self.collection).document("relationships") \
                .collection("all").where("target_id", "==", entity_id).stream()
            for doc in docs2:
                data = doc.to_dict()
                rels.append(Relationship(**data))
            return rels
        except Exception as e:
            print(f"[FirestoreAdapter] Get relationships error: {e}")
            return []
    
    def get_all_relationships(self) -> List[Relationship]:
        if not self.db:
            return []
        try:
            docs = self.db.collection(self.collection).document("relationships") \
                .collection("all").stream()
            rels = []
            for doc in docs:
                data = doc.to_dict()
                rels.append(Relationship(**data))
            return rels
        except Exception as e:
            print(f"[FirestoreAdapter] Get all relationships error: {e}")
            return []
    
    def delete_relationship(self, rel_id: str) -> bool:
        if not self.db:
            return False
        try:
            self.db.collection(self.collection).document("relationships") \
                .collection("all").document(rel_id).delete()
            return True
        except Exception as e:
            print(f"[FirestoreAdapter] Delete relationship error: {e}")
            return False
    
    # ─── Episode ─────────────────────────────────────────────────
    def save_episode(self, episode: Episode) -> str:
        if not self.db:
            return episode.id
        try:
            doc_ref = self.db.collection(self.collection).document("episodes") \
                .collection("all").document(episode.id)
            doc_ref.set({
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
        except Exception as e:
            print(f"[FirestoreAdapter] Save episode error: {e}")
        return episode.id
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        if not self.db:
            return None
        try:
            doc = self.db.collection(self.collection).document("episodes") \
                .collection("all").document(episode_id).get()
            if doc.exists:
                data = doc.to_dict()
                return Episode(**data)
        except Exception as e:
            print(f"[FirestoreAdapter] Get episode error: {e}")
        return None
    
    def get_episodes(self, limit: int = 100) -> List[Episode]:
        if not self.db:
            return []
        try:
            docs = self.db.collection(self.collection).document("episodes") \
                .collection("all").order_by("timestamp", direction=firestore.Query.DESCENDING) \
                .limit(limit).stream()
            episodes = []
            for doc in docs:
                data = doc.to_dict()
                episodes.append(Episode(**data))
            return episodes
        except Exception as e:
            print(f"[FirestoreAdapter] Get episodes error: {e}")
            return []
    
    def get_episodes_by_entity(self, entity_name: str, limit: int = 10) -> List[Episode]:
        if not self.db:
            return []
        try:
            docs = self.db.collection(self.collection).document("episodes") \
                .collection("all").where("entities_involved", "array_contains", entity_name) \
                .order_by("timestamp", direction=firestore.Query.DESCENDING) \
                .limit(limit).stream()
            episodes = []
            for doc in docs:
                data = doc.to_dict()
                episodes.append(Episode(**data))
            return episodes
        except Exception as e:
            print(f"[FirestoreAdapter] Get episodes by entity error: {e}")
            return []
    
    def delete_episode(self, episode_id: str) -> bool:
        if not self.db:
            return False
        try:
            self.db.collection(self.collection).document("episodes") \
                .collection("all").document(episode_id).delete()
            return True
        except Exception as e:
            print(f"[FirestoreAdapter] Delete episode error: {e}")
            return False
    
    # ─── Semantic Fact ────────────────────────────────────────────
    def save_semantic_fact(self, fact: SemanticFact) -> str:
        if not self.db:
            return fact.id
        try:
            doc_ref = self.db.collection(self.collection).document("semantic_facts") \
                .collection("all").document(fact.id)
            doc_ref.set({
                "id": fact.id,
                "statement": fact.statement,
                "confidence": fact.confidence,
                "source_episode_ids": fact.source_episode_ids,
                "created": fact.created,
                "last_updated": fact.last_updated,
                "version": fact.version
            })
        except Exception as e:
            print(f"[FirestoreAdapter] Save semantic fact error: {e}")
        return fact.id
    
    def get_semantic_fact(self, fact_id: str) -> Optional[SemanticFact]:
        if not self.db:
            return None
        try:
            doc = self.db.collection(self.collection).document("semantic_facts") \
                .collection("all").document(fact_id).get()
            if doc.exists:
                data = doc.to_dict()
                return SemanticFact(**data)
        except Exception as e:
            print(f"[FirestoreAdapter] Get semantic fact error: {e}")
        return None
    
    def get_semantic_facts(self, limit: int = 100) -> List[SemanticFact]:
        if not self.db:
            return []
        try:
            docs = self.db.collection(self.collection).document("semantic_facts") \
                .collection("all").order_by("created", direction=firestore.Query.DESCENDING) \
                .limit(limit).stream()
            facts = []
            for doc in docs:
                data = doc.to_dict()
                facts.append(SemanticFact(**data))
            return facts
        except Exception as e:
            print(f"[FirestoreAdapter] Get semantic facts error: {e}")
            return []
    
    def delete_semantic_fact(self, fact_id: str) -> bool:
        if not self.db:
            return False
        try:
            self.db.collection(self.collection).document("semantic_facts") \
                .collection("all").document(fact_id).delete()
            return True
        except Exception as e:
            print(f"[FirestoreAdapter] Delete semantic fact error: {e}")
            return False
    
    # ─── Procedure ───────────────────────────────────────────────
    def save_procedure(self, procedure: Procedure) -> str:
        if not self.db:
            return procedure.id
        try:
            doc_ref = self.db.collection(self.collection).document("procedures") \
                .collection("all").document(procedure.id)
            doc_ref.set({
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
        except Exception as e:
            print(f"[FirestoreAdapter] Save procedure error: {e}")
        return procedure.id
    
    def get_procedure(self, procedure_id: str) -> Optional[Procedure]:
        if not self.db:
            return None
        try:
            doc = self.db.collection(self.collection).document("procedures") \
                .collection("all").document(procedure_id).get()
            if doc.exists:
                data = doc.to_dict()
                return Procedure(**data)
        except Exception as e:
            print(f"[FirestoreAdapter] Get procedure error: {e}")
        return None
    
    def get_procedures(self, limit: int = 100) -> List[Procedure]:
        if not self.db:
            return []
        try:
            docs = self.db.collection(self.collection).document("procedures") \
                .collection("all").order_by("created", direction=firestore.Query.DESCENDING) \
                .limit(limit).stream()
            procedures = []
            for doc in docs:
                data = doc.to_dict()
                procedures.append(Procedure(**data))
            return procedures
        except Exception as e:
            print(f"[FirestoreAdapter] Get procedures error: {e}")
            return []
    
    def delete_procedure(self, procedure_id: str) -> bool:
        if not self.db:
            return False
        try:
            self.db.collection(self.collection).document("procedures") \
                .collection("all").document(procedure_id).delete()
            return True
        except Exception as e:
            print(f"[FirestoreAdapter] Delete procedure error: {e}")
            return False
    
    # ─── Lifecycle ───────────────────────────────────────────────
    def begin_transaction(self): pass
    def commit_transaction(self): pass
    def rollback_transaction(self): pass
    def close(self): pass
