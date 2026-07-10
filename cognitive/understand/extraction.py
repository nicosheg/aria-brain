# cognitive/understand/extraction.py

import json
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
        system_prompt = """You are an information extraction engine. Extract structured data from the user's message.

        Output ONLY valid JSON with this format:
        {
            "entities": [{"name": "...", "type": "person|concept|place|organization|skill|goal"}],
            "relationships": [{"source": "...", "target": "...", "relation_type": "..."}],
            "claims": [{"statement": "...", "confidence": 0.8}]
        }
        """
        
        user_prompt = f"""Text: "{text}"

        Context (if any): {context}

        Extract entities, relationships, and claims. Output ONLY JSON."""
        
        try:
            response = call_llm(system_prompt, user_prompt)
            if response:
                # Clean up markdown
                response = response.strip()
                if response.startswith("```json"):
                    response = response[7:]
                if response.endswith("```"):
                    response = response[:-3]
                result = json.loads(response.strip())
                return result
        except Exception as e:
            print(f"[Extractor] Error: {e}")
        
        return {"entities": [], "relationships": [], "claims": []}
