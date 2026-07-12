# ═════════════════════════════════════════════════════════════════════════════
# [TRACE AGENT] – Copilot for aria-brain Debugging
# ═════════════════════════════════════════════════════════════════════════════
#
# This is a mini AI agent that lives inside aria-brain.
# It analyzes trace trees in real time and:
# - 🔍 Finds bugs
# - ⚡ Detects bottlenecks
# - 💡 Suggests fixes
# - 📊 Analyzes patterns
#
# You talk to it like you talk to me (@copilot).
# It understands your repo, knows the cognitive architecture, and helps debug.
#
# Usage:
#   POST /trace-chat with {"query": "why is extraction failing?", "request_id": "abc123"}
#   Returns: Analysis + Suggested fixes + Code snippets
# ═════════════════════════════════════════════════════════════════════════════

from typing import Dict, List, Any, Optional
from cognitive.core.tracer import get_tracer, TraceLevel
import json


class TraceAgent:
    """
    Intelligent trace analyzer – your Copilot for debugging aria-brain.
    """
    
    def __init__(self):
        self.tracer = get_tracer()
        self.knowledge_base = self._build_knowledge_base()
        self.conversation_history = []  # For context across multiple queries
    
    def chat(self, query: str, request_id: Optional[str] = None, 
            user_id: Optional[str] = None, mode: str = "auto") -> Dict:
        """
        Main entry point – talk to the debug agent like you talk to Copilot.
        
        Args:
            query: Your question ("why is this failing?", "optimize this", etc.)
            request_id: If you want to debug a specific request
            user_id: If you want to debug a user's traces
            mode: "auto" (detect), "error", "performance", "architecture"
        """
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": query})
        
        # Get the trace
        if request_id:
            trace = self.tracer.get_trace(request_id)
        else:
            recent = self.tracer.get_recent_traces(limit=1, user_id=user_id)
            trace = recent[0] if recent else None
        
        if not trace:
            response = {
                "status": "no_data",
                "message": "No trace found. Send a message to ARIA first to generate traces.",
                "suggestion": "Try: POST /chat with {\"message\": \"Hello\", \"email\": \"you@example.com\"}"
            }
        else:
            # Analyze the trace
            response = self._analyze(query, trace, mode)
        
        # Add response to history
        self.conversation_history.append({"role": "agent", "content": response})
        
        return {
            "status": "success",
            "query": query,
            "response": response,
            "trace_context": {
                "request_id": request_id or (trace.get("request_id") if trace else None),
                "span_count": trace.get("span_count", 0) if trace else 0,
                "errors": len(trace.get("errors", [])) if trace else 0
            }
        }
    
    def _analyze(self, query: str, trace: Dict, mode: str) -> Dict:
        """Run intelligent analysis."""
        query_lower = query.lower()
        
        # Auto-detect if not specified
        if mode == "auto":
            if any(w in query_lower for w in ["fail", "error", "broke", "not work", "bug", "wrong"]):
                mode = "error"
            elif any(w in query_lower for w in ["slow", "fast", "performance", "time", "bottleneck"]):
                mode = "performance"
            elif any(w in query_lower for w in ["why", "how does", "explain", "design", "architecture"]):
                mode = "architecture"
        
        # Route to appropriate analyzer
        if mode == "error" or trace.get("errors"):
            return self._analyze_errors(query, trace)
        elif mode == "performance":
            return self._analyze_performance(query, trace)
        elif mode == "architecture":
            return self._explain_architecture(query, trace)
        else:
            return self._general_analysis(query, trace)
    
    def _analyze_errors(self, query: str, trace: Dict) -> Dict:
        """Debug why something failed."""
        errors = trace.get("errors", [])
        
        if not errors:
            return {
                "finding": "✅ No errors detected",
                "explanation": "The trace shows all operations succeeded.",
                "next_steps": [
                    "Check if the output is actually correct",
                    "Look at output_data to verify results",
                    "If response is wrong, it's a logic issue, not a crash"
                ]
            }
        
        first_error = errors[0]
        root_cause = self._diagnose_error(first_error, trace)
        suggested_fix = self._suggest_fix(first_error, root_cause)
        
        return {
            "finding": f"❌ {first_error.get('name')} failed",
            "error_type": first_error.get('error_type'),
            "error_message": first_error.get('error'),
            "root_cause": root_cause,
            "affected_operations": [e.get("name") for e in errors],
            "suggested_fix": suggested_fix,
            "debug_trace": self._get_debug_trace(first_error),
            "code_snippet": self._generate_fix_snippet(first_error, root_cause)
        }
    
    def _analyze_performance(self, query: str, trace: Dict) -> Dict:
        """Identify performance bottlenecks."""
        analysis = trace.get("analysis", {})
        slowest = analysis.get("slowest_spans", [])
        total = trace.get("total_duration_ms", 0)
        span_count = trace.get("span_count", 0)
        
        if not slowest:
            return {
                "finding": "⚡ Performance looks good",
                "total_duration_ms": total,
                "spans_processed": span_count,
                "avg_per_span_ms": round(total / max(1, span_count - 1), 2)
            }
        
        bottleneck = slowest[0]
        pct = (bottleneck["duration_ms"] / total * 100) if total > 0 else 0
        
        return {
            "finding": f"⚡ Bottleneck: {bottleneck['name']}",
            "bottleneck": {
                "operation": bottleneck['name'],
                "duration_ms": bottleneck['duration_ms'],
                "percent_of_total": round(pct, 1)
            },
            "slowest_operations": [
                {"name": s["name"], "duration_ms": s["duration_ms"]} 
                for s in slowest[:3]
            ],
            "optimization_strategies": self._suggest_optimization(bottleneck['name']),
            "expected_improvement": f"If optimized, could save {round(bottleneck['duration_ms'] / 1000, 1)}s total"
        }
    
    def _explain_architecture(self, query: str, trace: Dict) -> Dict:
        """Explain how the system works."""
        spans = trace.get("spans", [])
        span_names = [s.get("name", "") for s in spans]
        
        # Identify which stages ran
        stages = self._identify_stages(span_names)
        
        return {
            "finding": "🏗️ Pipeline overview",
            "stages_executed": stages,
            "architecture_explanation": self._explain_stages(stages),
            "data_flow": self._trace_data_flow(spans),
            "full_pipeline": self._describe_full_pipeline()
        }
    
    def _general_analysis(self, query: str, trace: Dict) -> Dict:
        """General trace analysis."""
        spans = trace.get("spans", [])
        errors = trace.get("errors", [])
        analysis = trace.get("analysis", {})
        
        return {
            "finding": "📊 Trace summary",
            "statistics": {
                "total_spans": len(spans),
                "successful_spans": len([s for s in spans if s.get("status") == "success"]),
                "failed_spans": len(errors),
                "total_duration_ms": trace.get("total_duration_ms")
            },
            "issues": analysis.get("critical_issues", []),
            "warnings": analysis.get("warnings", []),
            "slowest_operations": analysis.get("slowest_spans", [])[:3]
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # INTELLIGENT DIAGNOSIS
    # ─────────────────────────────────────────────────────────────────────────
    
    def _diagnose_error(self, error_span: Dict, trace: Dict) -> str:
        """Diagnose the root cause of an error."""
        error_type = error_span.get("error_type", "Unknown")
        error_msg = error_span.get("error", "")
        span_name = error_span.get("name", "")
        
        # Pattern matching
        diagnostics = {
            "JSONDecodeError": f"The LLM returned invalid JSON. This usually means the model didn't format the response correctly. Check the system prompt.",
            "NoneType": f"An API returned None. This happens when all LLM calls fail. Check your API keys (GROQ_KEY_*, GEMINI_KEY_*, etc.).",
            "KeyError": f"A required key is missing from the data. The code expected a field that wasn't provided. Check input_data.",
            "ConnectionError": f"Cannot connect to Firebase or PostgreSQL. Check your database credentials and network.",
            "TimeoutError": f"LLM call took too long (>20s). The model is slow or your network is slow.",
            "AttributeError": f"An object doesn't have the expected attribute. This is usually a coding error or wrong data type."
        }
        
        for err_type, diagnosis in diagnostics.items():
            if err_type in error_type:
                return diagnosis
        
        # Fallback: use the error message
        return f"Error in {span_name}: {error_msg[:150]}. Check the stack trace for details."
    
    def _suggest_fix(self, error_span: Dict, root_cause: str) -> Dict:
        """Suggest a fix for the error."""
        error_type = error_span.get("error_type", "")
        span_name = error_span.get("name", "")
        
        fixes = {
            "JSONDecodeError": {
                "title": "Fix JSON parsing",
                "file": "cognitive/understand/extraction.py",
                "steps": [
                    "1. Improve JSON extraction by using regex to find the first { and last }",
                    "2. Add better error handling: try parse as JSON, if fails, extract from markdown",
                    "3. Add validation to ensure all required fields are present"
                ]
            },
            "NoneType": {
                "title": "Fix API calls",
                "file": "brain.py or cognitive/infrastructure/llm.py",
                "steps": [
                    "1. Check if API keys are set: echo $GROQ_KEY_1",
                    "2. Test an API key manually: curl -H \"Authorization: Bearer $GROQ_KEY_1\" https://api.groq.com/...",
                    "3. Add more detailed logging to see which API is failing",
                    "4. Fall back to a working model"
                ]
            },
            "ConnectionError": {
                "title": "Fix database connection",
                "file": "brain.py or cognitive/core/storage.py",
                "steps": [
                    "1. Verify SUPABASE_DB_URL is set",
                    "2. Test connection: psql $SUPABASE_DB_URL -c 'SELECT 1'",
                    "3. Check if connection pool is exhausted (increase pool size)",
                    "4. Check firewall/network rules"
                ]
            }
        }
        
        for err_type, fix_info in fixes.items():
            if err_type in error_type:
                return fix_info
        
        return {
            "title": "Debug this error",
            "steps": [
                "1. Read the full stack trace (error_stack in trace)",
                "2. Add tracer.span() around the failing code",
                "3. Print intermediate values to understand what went wrong",
                "4. Run again and analyze the new trace"
            ]
        }
    
    def _get_debug_trace(self, error_span: Dict) -> List[str]:
        """Get debugging information from the error span."""
        return [
            f"Error at: {error_span.get('timestamp', 'unknown')}",
            f"Operation: {error_span.get('name')}",
            f"Input: {json.dumps(error_span.get('input', {}))[:100]}",
            f"Error type: {error_span.get('error_type')}",
            f"Stack trace preview: {(error_span.get('error_stack') or '')[:200]}"
        ]
    
    def _generate_fix_snippet(self, error_span: Dict, root_cause: str) -> str:
        """Generate a code snippet to fix the error."""
        error_type = error_span.get("error_type", "")
        
        snippets = {
            "JSONDecodeError": '''import re
import json

def extract_json_from_response(response: str) -> dict:
    """Extract JSON from LLM response, even if wrapped in markdown."""
    # Try direct parse first
    try:
        return json.loads(response)
    except:
        pass
    
    # Try to find JSON object in the response
    match = re.search(r'\\{.*\\}', response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass
    
    raise ValueError(f"Could not parse JSON from: {response[:100]}")
''',
            "NoneType": '''# Check if API keys are configured
import os

def check_api_keys():
    groq_keys = [os.environ.get(f"GROQ_KEY_{i}") for i in range(1, 21)]
    valid_groq = [k for k in groq_keys if k]
    
    print(f"✅ Found {len(valid_groq)} valid Groq keys")
    
    if not valid_groq:
        raise RuntimeError("No API keys configured! Set GROQ_KEY_1 in environment")
    
    return True
''',
            "ConnectionError": '''import os
import psycopg2

def test_db_connection():
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL not set")
    
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        result = cur.fetchone()
        print(f"✅ Database connection OK: {result}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        raise
'''
        }
        
        for err_type, snippet in snippets.items():
            if err_type in error_type:
                return snippet
        
        return "# Add debugging to your code\nfrom cognitive.core.tracer import get_tracer\ntracer = get_tracer()\nwith tracer.span('operation_name') as span:\n    span.input('variable', value)\n    # do work\n    span.output('result', output)"
    
    def _suggest_optimization(self, span_name: str) -> List[str]:
        """Suggest how to optimize a slow operation."""
        optimizations = {
            "llm_call": [
                "💡 Use caching for similar prompts (LRU cache)",
                "💡 Reduce prompt size (fewer examples, shorter context)",
                "💡 Switch to faster model (Groq is fastest)",
                "💡 Batch multiple requests together"
            ],
            "extract": [
                "💡 Use regex pre-filtering before LLM",
                "💡 Cache extraction results for duplicate texts",
                "💡 Batch multiple texts in one LLM call"
            ],
            "retrieve": [
                "💡 Add in-memory cache for recent queries",
                "💡 Limit number of relationships fetched",
                "💡 Use vector search instead of text search"
            ],
            "memory": [
                "💡 Connection pooling (already implemented)",
                "💡 Batch multiple writes",
                "💡 Use async I/O"
            ]
        }
        
        for op, tips in optimizations.items():
            if op in span_name.lower():
                return tips
        
        return [
            "💡 Profile the function to find bottlenecks",
            "💡 Add caching if fetching data",
            "💡 Consider async operations",
            "💡 Check if external API is slow"
        ]
    
    def _identify_stages(self, span_names: List[str]) -> List[str]:
        """Identify which pipeline stages ran."""
        stages = []
        for name in span_names:
            if "observe" in name.lower():
                stages.append("observe")
            elif "extract" in name.lower() or "understand" in name.lower():
                stages.append("understand")
            elif "memory" in name.lower() or "save" in name.lower():
                stages.append("update_memory")
            elif "world" in name.lower():
                stages.append("build_world")
            elif "reason" in name.lower():
                stages.append("reason")
            elif "decide" in name.lower() or "plan" in name.lower():
                stages.append("plan")
            elif "act" in name.lower() or "respond" in name.lower():
                stages.append("act")
        
        return list(set(stages))  # Remove duplicates
    
    def _explain_stages(self, stages: List[str]) -> str:
        """Explain what each stage does."""
        explanations = {
            "observe": "📍 Create an observation from the user's input",
            "understand": "🧠 Extract entities and relationships using LLM",
            "update_memory": "💾 Store entities and relationships in database",
            "build_world": "🌍 Build a mental model of the situation",
            "reason": "💭 Detect patterns and generate hypotheses",
            "plan": "📋 Decide what to do next",
            "act": "💬 Generate the response to the user"
        }
        
        return " → ".join([explanations.get(s, s) for s in stages])
    
    def _trace_data_flow(self, spans: List[Dict]) -> List[str]:
        """Show how data flows through the pipeline."""
        flow = []
        for span in spans:
            input_size = len(json.dumps(span.get("input", {})))
            output_size = len(json.dumps(span.get("output", {})))
            flow.append(f"{span['name']}: {input_size}B → {output_size}B")
        return flow
    
    def _describe_full_pipeline(self) -> str:
        """Describe the full ARIA pipeline."""
        return """ARIA's cognitive pipeline (in order):
1. 📍 OBSERVE - Convert user message into structured observation
2. 🧠 UNDERSTAND - Extract entities and relationships (via LLM)
3. 💾 UPDATE_MEMORY - Save to Firestore + PostgreSQL
4. 🌍 BUILD_WORLD - Retrieve related entities and build model
5. 💭 REASON - Analyze patterns, generate hypotheses
6. 📋 PLAN - Decide on next action(s)
7. 💬 ACT - Generate response for user

Each stage adds more understanding before deciding how to respond.
        """
    
    def _build_knowledge_base(self) -> Dict:
        """Build knowledge about aria-brain architecture."""
        return {
            "files": {
                "brain.py": "Legacy HTTP server (being replaced by FastAPI)",
                "main.py": "FastAPI server + orchestrator",
                "cognitive/core/orchestrator.py": "Main pipeline orchestrator",
                "cognitive/core/tracer.py": "This tracing system",
                "cognitive/understand/extraction.py": "Entity/relationship extraction",
                "cognitive/retrieve/world_model.py": "World model builder",
                "cognitive/reason/reasoner.py": "Pattern detection & reasoning",
                "cognitive/decide/executive.py": "Decision making",
            },
            "common_issues": {
                "extraction_fails": "LLM returns invalid JSON or None (check API keys)",
                "slow_pipeline": "LLM calls are bottleneck (use caching)",
                "memory_not_saving": "Firebase/PostgreSQL not connected (check credentials)",
                "wrong_answer": "Logic error, not a crash (needs prompt tuning)"
            }
        }


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL INSTANCE
# ─────────────────────────────────────────────────────────────────────────────

_global_trace_agent = TraceAgent()

def get_trace_agent() -> TraceAgent:
    """Get the global trace agent instance."""
    return _global_trace_agent
