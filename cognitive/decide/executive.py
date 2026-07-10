# cognitive/decide/executive.py

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone
import uuid

from cognitive.observe.observation import Observation
from cognitive.memory.graph import KnowledgeGraph
from cognitive.memory.episodic import EpisodicMemory
from cognitive.memory.semantic import SemanticMemory
from cognitive.memory.procedural import ProceduralMemory
from cognitive.retrieve.retriever import Retriever
from cognitive.retrieve.world_model import WorldModel, WorldModelBuilder
from cognitive.reason.reasoner import Reasoner
from cognitive.reason.metacognition import MetaCognition
from cognitive.decide.planner import Planner, Action
from cognitive.core.event_bus import EventBus, Event
from cognitive.understand.extraction import Extractor


class Executive:
    """
    The Executive Controller orchestrates the entire cognitive pipeline.
    """
    
    def __init__(self, graph: KnowledgeGraph, episodic: EpisodicMemory,
                 semantic: SemanticMemory, procedural: ProceduralMemory,
                 retriever: Retriever, reasoner: Reasoner,
                 metacognition: MetaCognition, planner: Planner,
                 event_bus: EventBus = None):
        
        self.graph = graph
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural
        self.retriever = retriever
        self.reasoner = reasoner
        self.metacognition = metacognition
        self.planner = planner
        self.event_bus = event_bus
        
        # State
        self.last_observation: Optional[Observation] = None
        self.last_world: Optional[WorldModel] = None
        self.last_decision: Optional[Dict] = None
        
        # Subscriptions
        if self.event_bus:
            self.event_bus.subscribe("OBSERVATION_CREATED", self._on_observation_created)
            self.event_bus.subscribe("UNDERSTANDING_COMPLETE", self._on_understanding_complete)
            self.event_bus.subscribe("MEMORY_UPDATED", self._on_memory_updated)
            self.event_bus.subscribe("REASONING_COMPLETE", self._on_reasoning_complete)
    
    # ─── Main Entry Point ─────────────────────────────────────────
    
    def process(self, source: str, raw: str, metadata: Dict = None) -> Dict:
        """
        Main entry point: process any input through the cognitive pipeline.
        """
        # 1. Observe
        observation = self._observe(source, raw, metadata)
        
        # 2. Understand (LLM extraction)
        understanding = self._understand(observation)
        
        # 3. Update Memory
        self._update_memory(observation, understanding)
        
        # 4. Retrieve & Build World Model
        world = self._build_world(observation.raw)
        
        # 5. Reason
        reasoning_result = self._reason(world)
        
        # 6. Metacognition
        meta_result = self._metacognition(world, reasoning_result)
        
        # 7. Plan
        action = self._plan(world, reasoning_result, meta_result)
        
        # 8. Act
        response = self._act(action, world, observation)
        
        return {
            "observation": observation,
            "understanding": understanding,
            "world": world,
            "reasoning": reasoning_result,
            "metacognition": meta_result,
            "action": action,
            "response": response
        }
    
    # ─── Pipeline Steps ──────────────────────────────────────────
    
    def _observe(self, source: str, raw: str, metadata: Dict = None) -> Observation:
        obs = Observation(
            source=source,
            raw=raw,
            metadata=metadata or {},
            importance=self._calculate_importance(raw)
        )
        self.last_observation = obs
        if self.event_bus:
            self.event_bus.publish("OBSERVATION_CREATED", {"observation": obs})
        return obs
    
    def _understand(self, observation: Observation) -> Dict:
        """Step 2: LLM extraction."""
        # Get context from graph
        context = self._get_context(observation.raw)
        return Extractor.extract(observation.raw, context)
    
    def _get_context(self, text: str) -> str:
        """Get graph context for extraction."""
        parts = []
        for entity in self.graph.entities_by_id.values():
            if entity.canonical_name.lower() in text.lower():
                parts.append(f"{entity.canonical_name} is a {entity.entity_type}")
        return "\n".join(parts[:5])
    
    def _update_memory(self, observation: Observation, understanding: Dict):
        """Step 3: Update all memory stores."""
        # Store entities
        for entity in understanding.get("entities", []):
            self.graph.get_or_create_entity(
                name=entity["name"],
                entity_type=entity.get("type", "concept"),
                confidence=0.8
            )
        
        # Store relationships
        for rel in understanding.get("relationships", []):
            source = self.graph.get_entity_by_name(rel["source"])
            target = self.graph.get_entity_by_name(rel["target"])
            if source and target:
                change = self.graph.propose_change(
                    "ADD_RELATIONSHIP",
                    {
                        "source_id": source.id,
                        "target_id": target.id,
                        "relation_type": rel["relation_type"],
                        "source": observation.source,
                        "created_by": observation.id
                    }
                )
                self.graph.validate_and_commit(change)
        
        # Store claims as semantic facts
        for claim in understanding.get("claims", []):
            self.semantic.add(
                statement=claim["statement"],
                confidence=claim.get("confidence", 0.6)
            )
        
        # Store episode
        entities = [e["name"] for e in understanding.get("entities", [])]
        self.episodic.add(
            summary=observation.raw[:100],
            full_text=observation.raw,
            importance=observation.importance,
            source=observation.source,
            entities=entities
        )
        
        if self.event_bus:
            self.event_bus.publish("MEMORY_UPDATED", {
                "observation_id": observation.id,
                "entity_count": len(understanding.get("entities", []))
            })
    
    def _build_world(self, query: str) -> WorldModel:
        world_builder = WorldModelBuilder(
            self.graph, self.retriever, self.episodic,
            self.semantic, self.procedural
        )
        world = world_builder.build(query)
        self.last_world = world
        return world
    
    def _reason(self, world: WorldModel) -> Dict:
        result = self.reasoner.reason(world)
        if self.event_bus:
            self.event_bus.publish("REASONING_COMPLETE", {"world": world, "result": result})
        return result
    
    def _metacognition(self, world: WorldModel, reasoning_result: Dict) -> Dict:
        return self.metacognition.evaluate_reasoning(world, reasoning_result)
    
    def _plan(self, world: WorldModel, reasoning_result: Dict, meta_result: Dict) -> Action:
        ask_decision = meta_result.get("ask_decision", {})
        if ask_decision.get("should_ask", False):
            questions = ask_decision.get("questions", [])
            if questions:
                return Action(
                    type="ask",
                    description=questions[0],
                    utility=0.9,
                    priority="high",
                    details={"question": questions[0]}
                )
        return self.planner.plan(world)
    
    def _act(self, action: Action, world: WorldModel, observation: Observation) -> str:
        self.last_decision = {
            "action": action.type,
            "description": action.description,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if action.type == "ask":
            return action.description
        elif action.type == "continue":
            return "I understand. What would you like to know?"
        else:
            return f"Action: {action.type} - {action.description}"
    
    # ─── Event Handlers ──────────────────────────────────────────
    
    def _on_observation_created(self, event): pass
    def _on_understanding_complete(self, event): pass
    def _on_memory_updated(self, event): pass
    def _on_reasoning_complete(self, event): pass
    
    # ─── Helpers ──────────────────────────────────────────────────
    
    def _calculate_importance(self, text: str) -> float:
        score = 0.3
        important_words = ["goal", "dream", "life", "career", "identity", "value", "mission", "purpose"]
        if any(w in text.lower() for w in important_words):
            score += 0.2
        if len(text) > 100:
            score += 0.2
        if "?" in text:
            score += 0.1
        return min(1.0, score)
    
    def get_state(self) -> Dict:
        return {
            "last_observation": self.last_observation.to_dict() if self.last_observation else None,
            "last_decision": self.last_decision,
            "has_world": self.last_world is not None
        }
