# cognitive/reason/metacognition.py

from typing import Dict, List, Optional
from datetime import datetime, timezone
from cognitive.memory.graph import KnowledgeGraph
from cognitive.memory.episodic import EpisodicMemory
from cognitive.memory.semantic import SemanticMemory
from cognitive.retrieve.world_model import WorldModel


class MetaCognition:
    """
    MetaCognition: ARIA's ability to reflect on its own reasoning.
    """
    
    def __init__(self, graph: KnowledgeGraph, episodic: EpisodicMemory, semantic: SemanticMemory):
        self.graph = graph
        self.episodic = episodic
        self.semantic = semantic
        
        self.certainty_threshold = 0.7
        self.hallucination_threshold = 0.6
        self.ask_threshold = 0.5
    
    def assess_certainty(self, world: WorldModel) -> Dict:
        """Assess overall certainty."""
        result = {
            "overall_certainty": 0.0,
            "belief_certainties": [],
            "entity_certainties": [],
            "low_certainty_items": []
        }
        
        if world.beliefs:
            avg_belief = sum(b.confidence for b in world.beliefs) / len(world.beliefs)
            result["belief_certainties"] = [
                {"statement": b.statement, "confidence": b.confidence}
                for b in world.beliefs
            ]
        else:
            avg_belief = 0.0
        
        if world.entities:
            entity_confidences = [e.confidence for e in world.entities]
            avg_entity = sum(entity_confidences) / len(entity_confidences)
            result["entity_certainties"] = [
                {"entity": e.canonical_name, "confidence": e.confidence}
                for e in world.entities
            ]
        else:
            avg_entity = 0.0
        
        if world.beliefs and world.entities:
            overall = (avg_belief * 0.6) + (avg_entity * 0.4)
        elif world.beliefs:
            overall = avg_belief
        elif world.entities:
            overall = avg_entity
        else:
            overall = 0.0
        
        result["overall_certainty"] = overall
        
        for belief in world.beliefs:
            if belief.confidence < self.certainty_threshold:
                result["low_certainty_items"].append({
                    "type": "belief",
                    "statement": belief.statement,
                    "confidence": belief.confidence,
                    "gap": 1 - belief.confidence
                })
        
        for entity in world.entities:
            if entity.confidence < self.certainty_threshold:
                result["low_certainty_items"].append({
                    "type": "entity",
                    "entity": entity.canonical_name,
                    "confidence": entity.confidence,
                    "gap": 1 - entity.confidence
                })
        
        return result
    
    def detect_hallucination_risk(self, world: WorldModel) -> Dict:
        """Assess hallucination risk."""
        result = {
            "risk_score": 0.0,
            "factors": [],
            "recommendation": "proceed"
        }
        
        risk = 0.0
        factors = []
        
        if world.entities and not world.recent_episodes:
            risk += 0.3
            factors.append("Entities present but no episodes to support them")
        
        low_beliefs = [b for b in world.beliefs if b.confidence < 0.4]
        if low_beliefs:
            risk += 0.2 * (len(low_beliefs) / max(1, len(world.beliefs)))
            factors.append(f"{len(low_beliefs)} beliefs with low confidence")
        
        if not world.beliefs and world.entities:
            risk += 0.2
            factors.append("No semantic facts available")
        
        if world.uncertainty:
            risk += 0.2
            factors.append("Uncertainty present in world model")
        
        result["risk_score"] = min(1.0, risk)
        result["factors"] = factors
        
        if risk >= self.hallucination_threshold:
            result["recommendation"] = "ask_for_clarification"
        elif risk >= 0.4:
            result["recommendation"] = "proceed_with_caution"
        else:
            result["recommendation"] = "proceed"
        
        return result
    
    def should_ask_question(self, world: WorldModel, reasoning_result: Dict) -> Dict:
        """
        Decide whether to ask a question — naturally, not hardcoded.
        """
        decision = {
            "should_ask": False,
            "questions": [],
            "confidence": 0.0
        }
        
        certainty = reasoning_result.get("certainty", {})
        low_certainty_items = certainty.get("low_certainty_items", [])
        
        if low_certainty_items:
            # Generate a natural question based on what's missing
            for item in low_certainty_items[:1]:
                if item["type"] == "entity":
                    decision["should_ask"] = True
                    decision["confidence"] = 0.8
                    decision["questions"].append(
                        f"I noticed you mentioned {item['entity']}. Could you tell me more about it?"
                    )
                elif item["type"] == "belief":
                    decision["should_ask"] = True
                    decision["confidence"] = 0.7
                    decision["questions"].append(
                        f"You mentioned something about '{item['statement'][:50]}'. Could you explain that further?"
                    )
                break
        
        if not decision["should_ask"] and not world.entities and world.recent_episodes:
            decision["should_ask"] = True
            decision["confidence"] = 0.6
            decision["questions"].append(
                "I'd love to understand you better. What's on your mind?"
            )
        
        hallucination = reasoning_result.get("hallucination_risk", {})
        if hallucination.get("risk_score", 0) >= self.hallucination_threshold:
            if not decision["should_ask"]:
                decision["should_ask"] = True
                decision["confidence"] = 0.7
                decision["questions"].append(
                    "I want to make sure I understand correctly. Could you tell me more about that?"
                )
        
        return decision
    
    def evaluate_reasoning(self, world: WorldModel, reasoning_result: Dict) -> Dict:
        """Overall evaluation."""
        certainty = self.assess_certainty(world)
        hallucination = self.detect_hallucination_risk(world)
        ask_decision = self.should_ask_question(world, reasoning_result)
        
        return {
            "certainty_assessment": certainty,
            "hallucination_assessment": hallucination,
            "ask_decision": ask_decision,
            "quality_score": self._calculate_quality_score(certainty, hallucination),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _calculate_quality_score(self, certainty: Dict, hallucination: Dict) -> float:
        score = 1.0
        if certainty.get("overall_certainty", 0) < 0.5:
            score -= 0.3
        elif certainty.get("overall_certainty", 0) < 0.7:
            score -= 0.1
        if hallucination.get("risk_score", 0) > 0.7:
            score -= 0.3
        elif hallucination.get("risk_score", 0) > 0.5:
            score -= 0.1
        return max(0.0, min(1.0, score))
