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
from cognitive.decide.planner import Planner, Action  # We'll build Planner next
from cognitive.core.event_bus import EventBus, Event  # We'll build EventBus next


class Executive:
    """
    The Executive Controller orchestrates the entire cognitive pipeline.
    
    Flow:
    1. Observe → Create Observation
    2. Understand → LLM extracts entities/relationships/claims
    3. Update Memory → Graph + Episodic + Semantic + Procedural
    4. Retrieve → Build World Model
    5. Reason → Detect contradictions, patterns, hypotheses
    6. Metacognition → Assess certainty, hallucination risk
    7. Plan → Decide next action
    8. Act → Execute action (tool, response, ask, etc.)
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
        """Step 1: Create Observation."""
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
        """Step 2: LLM extraction (to be implemented with your call_llm)."""
        # Placeholder: In production, call your LLM here
        # For now, return empty extraction
        return {
            "entities": [],
            "relationships": [],
            "claims": [],
            "events": []
        }
    
    def _update_memory(self, observation: Observation, understanding: Dict):
        """Step 3: Update all memory stores."""
        # This will be implemented with the actual extraction
        pass
    
    def _build_world(self, query: str) -> WorldModel:
        """Step 4: Build World Model."""
        world_builder = WorldModelBuilder(
            self.graph, self.retriever, self.episodic,
            self.semantic, self.procedural
        )
        world = world_builder.build(query)
        self.last_world = world
        return world
    
    def _reason(self, world: WorldModel) -> Dict:
        """Step 5: Run Reasoning."""
        result = self.reasoner.reason(world)
        
        if self.event_bus:
            self.event_bus.publish("REASONING_COMPLETE", {"world": world, "result": result})
        
        return result
    
    def _metacognition(self, world: WorldModel, reasoning_result: Dict) -> Dict:
        """Step 6: Run Metacognition."""
        return self.metacognition.evaluate_reasoning(world, reasoning_result)
    
    def _plan(self, world: WorldModel, reasoning_result: Dict, meta_result: Dict) -> Action:
        """Step 7: Plan the next action."""
        # Check metacognition: should we ask a question?
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
        
        # Otherwise use planner
        return self.planner.plan(world)
    
    def _act(self, action: Action, world: WorldModel, observation: Observation) -> str:
        """Step 8: Execute the action and generate response."""
        self.last_decision = {
            "action": action.type,
            "description": action.description,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # In production, this would call the response generator
        # For now, return a placeholder
        if action.type == "ask":
            return action.description
        elif action.type == "continue":
            return "I understand. What would you like to know?"
        else:
            return f"Action: {action.type} - {action.description}"
    
    # ─── Event Handlers ──────────────────────────────────────────
    
    def _on_observation_created(self, event):
        """Handle OBSERVATION_CREATED event."""
        # Could trigger understanding asynchronously
        pass
    
    def _on_understanding_complete(self, event):
        """Handle UNDERSTANDING_COMPLETE event."""
        # Could trigger memory update asynchronously
        pass
    
    def _on_memory_updated(self, event):
        """Handle MEMORY_UPDATED event."""
        # Could trigger reasoning asynchronously
        pass
    
    def _on_reasoning_complete(self, event):
        """Handle REASONING_COMPLETE event."""
        # Could trigger planning asynchronously
        pass
    
    # ─── Helpers ──────────────────────────────────────────────────
    
    def _calculate_importance(self, text: str) -> float:
        """Calculate importance of an observation."""
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
        """Get current executive state."""
        return {
            "last_observation": self.last_observation.to_dict() if self.last_observation else None,
            "last_decision": self.last_decision,
            "has_world": self.last_world is not None
        }
