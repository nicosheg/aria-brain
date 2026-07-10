# cognitive/core/orchestrator.py

from typing import Dict, Optional
from cognitive.memory.graph import KnowledgeGraph
from cognitive.memory.episodic import EpisodicMemory
from cognitive.memory.semantic import SemanticMemory
from cognitive.memory.procedural import ProceduralMemory
from cognitive.memory.storage_adapter import InMemoryAdapter
from cognitive.memory.file_adapter import FileAdapter
from cognitive.memory.firestore_adapter import FirestoreAdapter
from cognitive.retrieve.retriever import Retriever
from cognitive.retrieve.world_model import WorldModelBuilder
from cognitive.reason.reasoner import Reasoner
from cognitive.reason.metacognition import MetaCognition
from cognitive.decide.planner import Planner
from cognitive.decide.executive import Executive
from cognitive.core.event_bus import EventBus


class Orchestrator:
    def __init__(self, user_id: str, storage_adapter=None):
        self.user_id = user_id
        
        # Try Firestore first, fallback to file, then in-memory
        try:
            from brain import db
            if db is not None:
                self.storage = FirestoreAdapter(user_id)
                print(f"[Orchestrator] Using Firestore for user {user_id}")
            else:
                self.storage = FileAdapter(user_id)
                print(f"[Orchestrator] Firestore unavailable, using file storage for user {user_id}")
        except Exception as e:
            self.storage = FileAdapter(user_id)
            print(f"[Orchestrator] Firestore error: {e}, using file storage")
        
        # Components
        self.graph = KnowledgeGraph()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()
        self.event_bus = EventBus()
        
        self.retriever = Retriever(self.graph, self.episodic, self.semantic, self.procedural)
        self.world_builder = WorldModelBuilder(self.graph, self.retriever, self.episodic, self.semantic, self.procedural)
        self.reasoner = Reasoner(self.graph, self.episodic, self.semantic)
        self.metacognition = MetaCognition(self.graph, self.episodic, self.semantic)
        self.planner = Planner()
        self.executive = Executive(
            self.graph, self.episodic, self.semantic, self.procedural,
            self.retriever, self.reasoner, self.metacognition,
            self.planner, self.event_bus
        )
        
        self._loaded = False
        self._load()
    
    def process(self, source: str, raw: str, metadata: Dict = None) -> Dict:
        result = self.executive.process(source, raw, metadata or {})
        self._save()
        return result
    
    def ask(self, message: str, user_id: Optional[str] = None) -> str:
        if user_id:
            self.user_id = user_id
        result = self.process("conversation", message)
        return result.get("response", "I'm thinking...")
    
    def get_world_model(self, query: str) -> Dict:
        world = self.world_builder.build(query)
        return world.to_dict()
    
    def get_state(self) -> Dict:
        return {
            "user_id": self.user_id,
            "total_episodes": self.episodic.count(),
            "total_facts": self.semantic.count(),
            "total_procedures": self.procedural.count(),
            "total_entities": len(self.graph.entities_by_id),
            "total_relationships": len(self.graph.relationships_by_id)
        }
    
    def _load(self):
        try:
            entities = self.storage.get_all_entities()
            for e in entities:
                self.graph.entities_by_id[e.id] = e
                self.graph.entities_by_alias[e.canonical_name.lower()] = e.id
            print(f"[Orchestrator] Loaded {len(entities)} entities")
            
            rels = self.storage.get_all_relationships()
            for r in rels:
                self.graph.relationships_by_id[r.id] = r
            print(f"[Orchestrator] Loaded {len(rels)} relationships")
            
            eps = self.storage.get_episodes(limit=100)
            for ep in eps:
                self.episodic.episodes.append(ep)
            print(f"[Orchestrator] Loaded {len(eps)} episodes")
            
            facts = self.storage.get_semantic_facts(limit=100)
            for f in facts:
                self.semantic.facts.append(f)
            print(f"[Orchestrator] Loaded {len(facts)} facts")
            
            self._loaded = True
        except Exception as e:
            print(f"[Orchestrator] Load error: {e}")
    
    def _save(self):
        try:
            for e in self.graph.entities_by_id.values():
                self.storage.save_entity(e)
            for r in self.graph.relationships_by_id.values():
                self.storage.save_relationship(r)
            for ep in self.episodic.episodes[-50:]:
                self.storage.save_episode(ep)
            for f in self.semantic.facts[-50:]:
                self.storage.save_semantic_fact(f)
        except Exception as e:
            print(f"[Orchestrator] Save error: {e}")


_orchestrator = None
def get_orchestrator(user_id: str = "default") -> Orchestrator:
    global _orchestrator
    if _orchestrator is None or _orchestrator.user_id != user_id:
        _orchestrator = Orchestrator(user_id)
    return _orchestrator
