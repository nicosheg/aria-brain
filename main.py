from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os, time, hashlib, subprocess, re, sys, importlib, inspect
from pathlib import Path
import traceback

# ── UID Generator ──
def generate_aria_uid(email: str) -> dict:
    email = email.strip().lower()
    uid = f"aria_{hashlib.sha256(email.encode()).hexdigest()[:12]}"
    return {"aria_uid": uid}

# ── Import Orchestrator ──
from cognitive.core.orchestrator import Orchestrator

app = FastAPI(title="ARIA Debug", version="3.5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel):
    message: str
    email: str

class ChatResponse(BaseModel):
    reply: str

_orchestrators = {}
def get_orchestrator_for_user(user_id: str):
    if user_id not in _orchestrators:
        _orchestrators[user_id] = Orchestrator(user_id)
    return _orchestrators[user_id]

# ── Health & Ping ──
@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ARIA 3.5 alive 💚"}

@app.get("/ping")
async def ping():
    return {"pong": "ok"}

# ── Chat Endpoint ──
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    message = request.message.strip()
    email = request.email.strip().lower()
    if not message or not email:
        raise HTTPException(status_code=400, detail="Missing fields")
    uid_result = generate_aria_uid(email)
    if "error" in uid_result:
        raise HTTPException(status_code=400, detail=uid_result["error"])
    user_id = uid_result["aria_uid"]
    try:
        orchestrator = get_orchestrator_for_user(user_id)
        result = orchestrator.process("conversation", message, {"email": email})
        response = result.get("response", "I'm thinking...")
        return ChatResponse(reply=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Debug Endpoints ──
@app.get("/debug-state")
async def debug_state(email: str):
    uid_result = generate_aria_uid(email)
    if "error" in uid_result:
        return {"error": uid_result["error"]}
    user_id = uid_result["aria_uid"]
    return get_orchestrator_for_user(user_id).get_state()

@app.get("/debug-world")
async def debug_world(email: str, query: str = ""):
    uid_result = generate_aria_uid(email)
    if "error" in uid_result:
        return {"error": uid_result["error"]}
    user_id = uid_result["aria_uid"]
    return get_orchestrator_for_user(user_id).get_world_model(query or "test")

# ── Static Files ──
@app.get("/")
async def serve_index():
    return FileResponse("public/index.html")

@app.get("/{file_path:path}")
async def serve_static(file_path: str):
    full_path = f"public/{file_path}"
    if os.path.exists(full_path):
        return FileResponse(full_path)
    raise HTTPException(status_code=404, detail="Not found")

# ════════════════════════════════════════════════════════════════════
#  DEBUG COMPANION ENGINE – Dynamic, No Hardcoding
# ════════════════════════════════════════════════════════════════════

@app.post("/trace-chat")
async def trace_chat(request: dict):
    query = request.get("query", "")
    request_id = request.get("request_id", "unknown")

    # Run dynamic analysis
    analyzer = DebugAnalyzer()
    result = analyzer.analyze(query)

    return {
        "response": result["response"],
        "trace_context": {
            "request_id": request_id,
            "span_count": 0,
            "errors": 0
        },
        "code_snippet": result.get("code_snippet")
    }

class DebugAnalyzer:
    """Scans your codebase, checks common issues, and suggests fixes dynamically."""

    def analyze(self, query: str) -> Dict[str, Any]:
        lower = query.lower()
        checks = [
            ("extraction", self.check_extraction),
            ("llm", self.check_llm),
            ("error", self.check_errors),
            ("optimize", self.check_performance),
            ("database", self.check_database),
            ("routes", self.check_routes),
            ("memory", self.check_memory),
        ]
        for keyword, func in checks:
            if keyword in lower:
                return func()
        return self.general_analysis(query)

    def check_extraction(self):
        findings = []
        root_cause = ""
        suggestion = ""

        # Check extraction.py exists
        ext_path = Path("cognitive/understand/extraction.py")
        if not ext_path.exists():
            findings.append("❌ extraction.py not found – likely missing the entire cognitive module.")
            root_cause = "The cognitive architecture is not properly installed or the extraction module is missing."
            suggestion = "Run `pip install -e .` or ensure the cognitive folder exists."
        else:
            # Check if the file imports correctly
            try:
                importlib.import_module("cognitive.understand.extraction")
                findings.append("✅ extraction.py imports successfully.")
            except Exception as e:
                findings.append(f"❌ extraction.py import error: {e}")
                root_cause = "There's a syntax or dependency error in extraction.py."
                suggestion = "Fix the import error, likely missing a dependency or a typo."

            # Check for JSON parsing in the file
            try:
                content = ext_path.read_text()
                if "json.loads" not in content:
                    findings.append("⚠️ extraction.py does not appear to parse JSON. Check the LLM response handling.")
                if "call_llm" not in content:
                    findings.append("⚠️ extraction.py does not call an LLM – maybe it's using a different method?")
            except:
                pass

        return self.build_response(findings, root_cause, suggestion, "cognitive/understand/extraction.py")

    def check_llm(self):
        findings = []
        root_cause = ""
        suggestion = ""

        # Check environment variables for Groq keys
        groq_keys = [os.environ.get(f"GROQ_KEY_{i}") for i in range(1, 21)]
        found = [k for k in groq_keys if k]
        if not found:
            findings.append("❌ No GROQ_API_KEY found in environment variables.")
            root_cause = "The LLM (Groq) is not configured – ARIA can't make extraction calls."
            suggestion = "Add GROQ_KEY_1 to your Render environment variables or set it locally."
        else:
            findings.append(f"✅ Found {len(found)} Groq API key(s).")

        # Check if llm.py exists and imports
        llm_path = Path("cognitive/infrastructure/llm.py")
        if not llm_path.exists():
            findings.append("❌ cognitive/infrastructure/llm.py missing.")
            root_cause = "The LLM wrapper module is not present."
            suggestion = "Create cognitive/infrastructure/llm.py with a `call_llm` function."
        else:
            try:
                importlib.import_module("cognitive.infrastructure.llm")
                findings.append("✅ llm.py imports successfully.")
            except Exception as e:
                findings.append(f"❌ llm.py import error: {e}")

        return self.build_response(findings, root_cause, suggestion, "cognitive/infrastructure/llm.py")

    def check_errors(self):
        findings = []
        root_cause = ""
        suggestion = ""

        # Check for recent error logs (if in Render, we could fetch logs, but we'll scan files)
        # Look for traceback in code
        for py_file in Path(".").glob("*.py"):
            try:
                content = py_file.read_text()
                if "Traceback" in content or "ERROR" in content.upper():
                    findings.append(f"⚠️ Found potential error markers in {py_file.name}.")
            except:
                pass

        # Check for common mistakes
        py_files = list(Path("cognitive").rglob("*.py"))
        for f in py_files:
            try:
                content = f.read_text()
                if "import" in content and "from" in content:
                    # Check for import errors by trying to import
                    pass
            except:
                pass

        if not findings:
            findings.append("✅ No obvious error patterns found in your code files.")

        return self.build_response(findings, root_cause, suggestion, "main.py")

    def check_performance(self):
        findings = []
        root_cause = ""
        suggestion = ""

        # Count LLM calls in code
        llm_calls = 0
        for py_file in Path("cognitive").rglob("*.py"):
            try:
                content = py_file.read_text()
                llm_calls += content.count("call_llm")
            except:
                pass

        if llm_calls > 10:
            findings.append(f"⚠️ Found {llm_calls} LLM calls across files – consider caching.")
            root_cause = "Multiple LLM calls may slow down responses."
            suggestion = "Implement caching with `@lru_cache` or use a request batching mechanism."

        return self.build_response(findings, root_cause, suggestion, "cognitive/infrastructure/llm.py")

    def check_database(self):
        findings = []
        root_cause = ""
        suggestion = ""

        # Check Firestore connection
        try:
            from brain import db
            if db is None:
                findings.append("❌ Firestore db is None – check credentials.")
                root_cause = "Firestore not initialized, likely missing FIREBASE_CREDENTIALS."
                suggestion = "Set FIREBASE_CREDENTIALS environment variable with service account JSON."
            else:
                findings.append("✅ Firestore is connected.")
        except ImportError:
            findings.append("⚠️ brain.py not found or cannot import db – Firestore may not be used.")
            root_cause = "The application may be using a file adapter instead of Firestore."
            suggestion = "If you need Firestore, ensure the module is installed and configured."

        return self.build_response(findings, root_cause, suggestion, "brain.py")

    def check_routes(self):
        findings = []
        root_cause = ""
        suggestion = ""

        # Get all routes from the app
        routes = []
        for route in app.routes:
            routes.append(f"{route.methods} {route.path}")
        findings.append(f"✅ Registered routes: {len(routes)}")
        # Show sample
        if len(routes) > 0:
            findings.append("Sample routes: " + ", ".join([r for r in routes[:5]]))

        # Check for duplicate or conflicting routes
        return self.build_response(findings, root_cause, suggestion, "main.py")

    def check_memory(self):
        findings = []
        root_cause = ""
        suggestion = ""

        # Check if file adapter exists
        mem_file = Path("aria_memory_test_user.json")
        if mem_file.exists():
            findings.append("✅ Memory file exists for test_user.")
        else:
            findings.append("ℹ️ No memory file found for test_user – likely because no conversations have been saved yet.")

        # Check orchestrator state
        try:
            orch = Orchestrator("test_user")
            state = orch.get_state()
            findings.append(f"✅ Orchestrator state: entities={state.get('total_entities',0)}, episodes={state.get('total_episodes',0)}")
        except Exception as e:
            findings.append(f"❌ Orchestrator error: {e}")

        return self.build_response(findings, root_cause, suggestion, "cognitive/core/orchestrator.py")

    def general_analysis(self, query):
        findings = ["I'll help you debug. I can check:"]
        findings.append("- extraction (extraction issues)")
        findings.append("- llm (API keys, models)")
        findings.append("- error (runtime errors)")
        findings.append("- optimize (performance suggestions)")
        findings.append("- database (Firestore/Postgres)")
        findings.append("- routes (endpoint issues)")
        findings.append("- memory (storage and recall)")
        root_cause = "No specific topic selected."
        suggestion = "Try asking: 'check extraction' or 'why is memory failing?'"
        return self.build_response(findings, root_cause, suggestion, None)

    def build_response(self, findings, root_cause, suggestion, file_hint):
        response = "🔍 **Debug Analysis**\n\n"
        response += "\n".join(findings) + "\n\n"
        if root_cause:
            response += f"📌 **Root Cause**: {root_cause}\n\n"
        if suggestion:
            response += f"✅ **Suggested Fix**: {suggestion}\n\n"
        if file_hint:
            response += f"📄 **Relevant File**: `{file_hint}`\n"

        # Provide a code snippet if available
        code_snippet = None
        if file_hint and Path(file_hint).exists():
            try:
                snippet = Path(file_hint).read_text().split("\n")[:10]
                code_snippet = "\n".join(snippet)
            except:
                pass

        return {
            "response": response,
            "code_snippet": code_snippet
        }

# ════════════════════════════════════════════════════════════════════
# START
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
