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
