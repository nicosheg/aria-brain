# cognitive/core/orchestrator.py

from typing import Dict, Optional
from cognitive.memory.graph import KnowledgeGraph
from cognitive.memory.episodic import EpisodicMemory
from cognitive.memory.semantic import SemanticMemory
from cognitive.memory.procedural import ProceduralMemory
from cognitive.memory.storage_adapter import InMemoryAdapter
from cognitive.retrieve.retriever import Retriever
from cognitive.retrieve.world_model import WorldModelBuilder
from cognitive.reason.reasoner import Reasoner
from cognitive.reason.metacognition import MetaCognition
from cognitive.decide.planner import Planner
from cognitive.decide.executive import Executive
from cognitive.core.event_bus import EventBus


class Orchestrator:
    """
    The Orchestrator is the main entry point for ARIA's cognitive system.
    It initializes all components and provides a simple API.
    """
    
    def __init__(self, user_id: str, storage_adapter=None):
        self.user_id = user_id
        self.storage = storage_adapter or InMemoryAdapter()
        
        # Initialize all components
        self.graph = KnowledgeGraph()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()
        self.event_bus = EventBus()
        
        # Retrieve components
        self.retriever = Retriever(self.graph, self.episodic, self.semantic, self.procedural)
        self.world_builder = WorldModelBuilder(self.graph, self.retriever, self.episodic, self.semantic, self.procedural)
        
        # Reasoning components
        self.reasoner = Reasoner(self.graph, self.episodic, self.semantic)
        self.metacognition = MetaCognition(self.graph, self.episodic, self.semantic)
        
        # Decision components
        self.planner = Planner()
        self.executive = Executive(
            self.graph, self.episodic, self.semantic, self.procedural,
            self.retriever, self.reasoner, self.metacognition,
            self.planner, self.event_bus
        )
        
        # State
        self._loaded = False
        self._load()
    
    def process(self, source: str, raw: str, metadata: Dict = None) -> Dict:
        """
        Main entry point: process any input through the cognitive pipeline.
        """
        result = self.executive.process(source, raw, metadata or {})
        
        # Save to storage after processing
        self._save()
        
        return result
    
    def ask(self, message: str, user_id: Optional[str] = None) -> str:
        """
        Legacy API: simple ask function for compatibility with brain.py.
        """
        if user_id:
            self.user_id = user_id
        
        result = self.process("conversation", message)
        return result.get("response", "I'm thinking...")
    
    def get_world_model(self, query: str) -> Dict:
        """Get the current world model for a query."""
        world = self.world_builder.build(query)
        return world.to_dict()
    
    def get_state(self) -> Dict:
        """Get current system state."""
        return {
            "user_id": self.user_id,
            "total_episodes": self.episodic.count(),
            "total_facts": self.semantic.count(),
            "total_procedures": self.procedural.count(),
            "total_entities": len(self.graph.entities_by_id),
            "total_relationships": len(self.graph.relationships_by_id),
            "executive": self.executive.get_state()
        }
    
    def _load(self):
        """Load from storage."""
        # TODO: Implement loading from storage adapter
        pass
    
    def _save(self):
        """Save to storage."""
        # TODO: Implement saving to storage adapter
        pass


# ─── Singleton for easy access ───
_orchestrator = None

def get_orchestrator(user_id: str = "default") -> Orchestrator:
    """Get or create a global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(user_id)
    return _orchestrator

    def _extract_and_store(self, text: str, observation_id: str):
        """Extract entities/relationships and store them in the graph."""
        from cognitive.understand.extraction import Extractor
        
        # Get context from the graph
        context = self._get_graph_context(text)
        
        # Extract
        result = Extractor.extract(text, context)
        
        # Store entities
        for entity in result.get("entities", []):
            self.graph.get_or_create_entity(
                name=entity["name"],
                entity_type=entity.get("type", "concept"),
                confidence=0.8
            )
        
        # Store relationships
        for rel in result.get("relationships", []):
            source = self.graph.get_entity_by_name(rel["source"])
            target = self.graph.get_entity_by_name(rel["target"])
            if source and target:
                change = self.graph.propose_change(
                    "ADD_RELATIONSHIP",
                    {
                        "source_id": source.id,
                        "target_id": target.id,
                        "relation_type": rel["relation_type"],
                        "source": "conversation",
                        "created_by": observation_id
                    }
                )
                self.graph.validate_and_commit(change)
        
        # Store claims as semantic facts
        for claim in result.get("claims", []):
            self.semantic.add(
                statement=claim["statement"],
                confidence=claim.get("confidence", 0.6)
            )
        
        return result
    
    def _get_graph_context(self, text: str) -> str:
        """Get relevant context from the graph for extraction."""
        context_parts = []
        for entity in self.graph.entities_by_id.values():
            if entity.canonical_name.lower() in text.lower():
                context_parts.append(f"{entity.canonical_name} is a {entity.entity_type}")
        return "\n".join(context_parts[:10])

    def _load(self):
        """Load from storage."""
        # TODO: Implement loading from Firestore/PostgreSQL
        # For now, try to load from in-memory backup if it exists
        
        # If storage adapter is available, load entities, relationships, etc.
        if self.storage:
            try:
                # Load entities
                entities = self.storage.get_all_entities()
                for entity_data in entities:
                    self.graph.get_or_create_entity(
                        name=entity_data["canonical_name"],
                        entity_type=entity_data.get("entity_type", "concept"),
                        confidence=entity_data.get("confidence", 0.5)
                    )
                
                # Load episodes
                episodes = self.storage.get_episodes(limit=100)
                for ep in episodes:
                    self.episodic.add(
                        summary=ep.get("summary", ""),
                        full_text=ep.get("full_text", ""),
                        importance=ep.get("importance", 0.5),
                        source=ep.get("source", "conversation"),
                        entities=ep.get("entities_involved", [])
                    )
            except Exception as e:
                print(f"[Orchestrator] Load error: {e}")
        
        self._loaded = True
