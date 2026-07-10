# cognitive/reason/metacognition.py

from typing import Dict, List, Optional
from datetime import datetime, timezone
from cognitive.memory.graph import KnowledgeGraph
from cognitive.memory.episodic import EpisodicMemory
from cognitive.memory.semantic import SemanticMemory
from cognitive.retrieve.world_model import WorldModel
from cognitive.core.config import ARIAConfig


class MetaCognition:
    """
    MetaCognition: ARIA's ability to reflect on its own reasoning.
    
    - Assess certainty of beliefs and decisions
    - Detect hallucination risk
    - Decide when to ask for clarification
    - Evaluate reasoning quality
    """
    
    def __init__(self, graph: KnowledgeGraph, episodic: EpisodicMemory, semantic: SemanticMemory):
        self.graph = graph
        self.episodic = episodic
        self.semantic = semantic
        
        # Thresholds (configurable)
        self.certainty_threshold = 0.7
        self.hallucination_threshold = 0.6
        self.ask_threshold = 0.5
    
    def assess_certainty(self, world: WorldModel) -> Dict:
        """
        Assess overall certainty and per-belief confidence.
        """
        result = {
            "overall_certainty": 0.0,
            "belief_certainties": [],
            "entity_certainties": [],
            "low_certainty_items": []
        }
        
        # 1. Average certainty of beliefs
        if world.beliefs:
            avg_belief = sum(b.confidence for b in world.beliefs) / len(world.beliefs)
            result["belief_certainties"] = [
                {"statement": b.statement, "confidence": b.confidence}
                for b in world.beliefs
            ]
        else:
            avg_belief = 0.0
        
        # 2. Entity importance & confidence
        if world.entities:
            entity_confidences = [e.confidence for e in world.entities]
            avg_entity = sum(entity_confidences) / len(entity_confidences)
            result["entity_certainties"] = [
                {"entity": e.canonical_name, "confidence": e.confidence}
                for e in world.entities
            ]
        else:
            avg_entity = 0.0
        
        # 3. Combine
        if world.beliefs and world.entities:
            overall = (avg_belief * 0.6) + (avg_entity * 0.4)
        elif world.beliefs:
            overall = avg_belief
        elif world.entities:
            overall = avg_entity
        else:
            overall = 0.0
        
        result["overall_certainty"] = overall
        
        # 4. Identify low-certainty items
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
        """
        Assess the risk of hallucination based on evidence strength.
        """
        result = {
            "risk_score": 0.0,
            "factors": [],
            "recommendation": "proceed"
        }
        
        risk = 0.0
        factors = []
        
        # 1. No evidence for key entities
        if world.entities and not world.recent_episodes:
            risk += 0.3
            factors.append("Entities present but no recent episodes to support them")
        
        # 2. Beliefs with low confidence
        low_beliefs = [b for b in world.beliefs if b.confidence < 0.4]
        if low_beliefs:
            risk += 0.2 * (len(low_beliefs) / max(1, len(world.beliefs)))
            factors.append(f"{len(low_beliefs)} beliefs with low confidence")
        
        # 3. No semantic facts
        if not world.recent_facts and world.entities:
            risk += 0.2
            factors.append("No semantic facts available")
        
        # 4. Contradictions detected (will be passed from reasoning)
        if world.patterns:
            # We assume patterns with "contradiction" in type
            contradiction_patterns = [p for p in world.patterns if "contradiction" in p.get("type", "")]
            if contradiction_patterns:
                risk += 0.3
                factors.append(f"{len(contradiction_patterns)} contradictions found")
        
        # 5. High uncertainty
        if world.uncertainty:
            risk += 0.2
            factors.append("Uncertainty present in world model")
        
        result["risk_score"] = min(1.0, risk)
        result["factors"] = factors
        
        # Recommendation
        if risk >= self.hallucination_threshold:
            result["recommendation"] = "ask_for_clarification"
        elif risk >= 0.4:
            result["recommendation"] = "proceed_with_caution"
        else:
            result["recommendation"] = "proceed"
        
        return result
    
    def should_ask_question(self, world: WorldModel, reasoning_result: Dict) -> Dict:
        """
        Decide whether ARIA should ask a question to clarify or gather more information.
        """
        decision = {
            "should_ask": False,
            "questions": [],
            "confidence": 0.0
        }
        
        # 1. Low certainty overall
        certainty = reasoning_result.get("certainty", {})
        if certainty.get("overall_certainty", 0) < self.certainty_threshold:
            decision["should_ask"] = True
            decision["confidence"] = 0.8
            decision["questions"].append("I'm not fully certain. Could you clarify?")
        
        # 2. Hallucination risk high
        hallucination = reasoning_result.get("hallucination_risk", {})
        if hallucination.get("risk_score", 0) >= self.hallucination_threshold:
            decision["should_ask"] = True
            decision["confidence"] = 0.7
            decision["questions"].append("I need more information to be confident.")
        
        # 3. Specific low-certainty beliefs
        for item in certainty.get("low_certainty_items", []):
            if item["type"] == "belief" and item["confidence"] < 0.4:
                decision["should_ask"] = True
                decision["confidence"] = max(decision["confidence"], 0.6)
                decision["questions"].append(f"About '{item['statement']}': could you tell me more?")
                break
        
        # 4. Uncertainty in reasoning
        for item in reasoning_result.get("uncertainty", {}).values():
            if item.get("confidence_gap", 0) > 0.7:
                decision["should_ask"] = True
                decision["confidence"] = 0.7
                decision["questions"].append(item.get("description", "I'm not sure about this."))
                break
        
        return decision
    
    def evaluate_reasoning(self, world: WorldModel, reasoning_result: Dict) -> Dict:
        """
        Overall evaluation of reasoning quality.
        """
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
        """Calculate a composite quality score."""
        score = 1.0
        
        # Penalize for low certainty
        if certainty.get("overall_certainty", 0) < 0.5:
            score -= 0.3
        elif certainty.get("overall_certainty", 0) < 0.7:
            score -= 0.1
        
        # Penalize for high hallucination risk
        if hallucination.get("risk_score", 0) > 0.7:
            score -= 0.3
        elif hallucination.get("risk_score", 0) > 0.5:
            score -= 0.1
        
        return max(0.0, min(1.0, score))
