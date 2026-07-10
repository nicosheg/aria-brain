# cognitive/decide/planner.py

from typing import Dict, List, Optional
from dataclasses import dataclass
from cognitive.retrieve.world_model import WorldModel


@dataclass
class Action:
    type: str  # ask, remind, encourage, challenge, continue, execute_tool, respond
    description: str
    utility: float
    priority: str  # high, medium, low
    details: Dict


class Planner:
    """
    Planner decides the next action based on the world model.
    """
    
    def __init__(self):
        self.min_utility = 0.3
    
    def plan(self, world: WorldModel) -> Action:
        """Plan the next action."""
        actions = self._generate_actions(world)
        if not actions:
            return Action(
                type="continue",
                description="Continue natural conversation",
                utility=0.5,
                priority="low",
                details={}
            )
        
        # Select action with highest utility
        return max(actions, key=lambda a: a.utility)
    
    def _generate_actions(self, world: WorldModel) -> List[Action]:
        """Generate possible actions with utilities."""
        actions = []
        
        # 1. If uncertainty is high, ask a question
        if world.uncertainty:
            for key, item in world.uncertainty.items():
                if item.get("confidence_gap", 0) > 0.6:
                    actions.append(Action(
                        type="ask",
                        description=f"Ask about: {item.get('description', 'this topic')}",
                        utility=0.9,
                        priority="high",
                        details={"topic": key}
                    ))
                    break
        
        # 2. If patterns detected, reflect
        if world.patterns:
            for pattern in world.patterns[:2]:
                if pattern.get("significance", 0) > 0.6:
                    actions.append(Action(
                        type="reflect",
                        description=f"Reflect on pattern: {pattern.get('description', '')}",
                        utility=0.7,
                        priority="medium",
                        details={"pattern": pattern}
                    ))
                    break
        
        # 3. If entities exist but no relationships, ask for clarification
        if world.entities and not world.relationships:
            actions.append(Action(
                type="ask",
                description="How do these entities relate to each other?",
                utility=0.8,
                priority="high",
                details={"question": "How do these entities relate to each other?"}
            ))
        
        # 4. Default: continue
        actions.append(Action(
            type="continue",
            description="Continue natural conversation",
            utility=0.4,
            priority="low",
            details={}
        ))
        
        return actions
