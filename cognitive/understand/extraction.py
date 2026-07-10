# cognitive/understand/extraction.py

import json
import re
from typing import Dict, List
from cognitive.infrastructure.llm import call_llm


class Extractor:
    """
    Uses LLM to extract entities, relationships, and claims from text.
    """
    
    @staticmethod
    def extract(text: str, context: str = "") -> Dict:
        """
        Extract structured information from text.
        Returns: {"entities": [], "relationships": [], "claims": []}
        """
        print(f"[Extractor] Processing: {text[:50]}...")
        
        system_prompt = """You are an information extraction engine. Extract structured data from the user's message.

        Output ONLY valid JSON. Do not add any extra text, explanations, or markdown.

        The JSON must have this exact format:
        {
            "entities": [
                {"name": "...", "type": "person|concept|place|organization|skill|goal"}
            ],
            "relationships": [
                {"source": "...", "target": "...", "relation_type": "..."}
            ],
            "claims": [
                {"statement": "...", "confidence": 0.8}
            ]
        }

        If you can't extract anything, return: {"entities": [], "relationships": [], "claims": []}
        """
        
        user_prompt = f"""Text: "{text}"

        Context (if any): {context}

        Extract entities, relationships, and claims. Output ONLY the JSON."""
        
        try:
            response = call_llm(system_prompt, user_prompt)
            print(f"[Extractor] LLM response: {response[:100] if response else 'empty'}")
            
            if not response:
                print("[Extractor] LLM returned empty")
                return {"entities": [], "relationships": [], "claims": []}
            
            # Clean up response
            response = response.strip()
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group(0)
            
            # Remove markdown code blocks
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            result = json.loads(response.strip())
            
            # Ensure required keys exist
            if "entities" not in result:
                result["entities"] = []
            if "relationships" not in result:
                result["relationships"] = []
            if "claims" not in result:
                result["claims"] = []
            
            print(f"[Extractor] Extracted {len(result['entities'])} entities")
            return result
            
        except json.JSONDecodeError as e:
            print(f"[Extractor] JSON error: {e}")
            print(f"[Extractor] Response: {response[:200] if response else 'empty'}")
            return {"entities": [], "relationships": [], "claims": []}
        except Exception as e:
            print(f"[Extractor] Error: {e}")
            return {"entities": [], "relationships": [], "claims": []}
