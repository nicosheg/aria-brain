# ════════════════════════════════════════════════════════════════════
# ARIA FastAPI Server – Production-Grade, Async, Multi-User
# ════════════════════════════════════════════════════════════════════

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time
import json
import traceback
import os

# ── Import all your existing brain.py logic ──
from brain import (
    db, firestore, generate_aria_uid, log_error, get_feature_flags,
    get_or_create_income_profile, start_income_onboarding,
    get_relevant_income_knowledge, build_income_system_prompt,
    check_diversification_guard, detect_and_record_outcome,
    get_conversation_state, save_conversation_state,
    get_understanding, update_understanding, clear_understanding,
    get_pending_session, clear_pending_session,
    get_goals, update_goals, get_context,
    process_conversation_brain, execute_decision,
    handle_human_first, handle_casual_conversation,
    generate_human_response,
    discover_intent, check_clarification_response,
    is_topic_change, is_active_conversation,
    module_registry, task_module, call_llm,
    logger, load_user_memory
)

# ── FastAPI App ──
app = FastAPI(
    title="ARIA – Life Operating System",
    description="Your AI companion for income, education, and personal growth.",
    version="3.5.0"
)

# ── CORS (allow frontend access) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request/Response Models ──
class ChatRequest(BaseModel):
    message: str
    email: str

class ChatResponse(BaseModel):
    reply: str

class FeedbackRequest(BaseModel):
    user_id: str
    score: int

class UploadRequest(BaseModel):
    email: str
    file_base64: str
    file_name: str
    file_type: str
    mime_type: Optional[str] = ""

# ── Helper: Build Memory Block ──
def build_memory_block(user_id: str) -> dict:
    """Load all memory sources and return a dict for the LLM context."""
    memory = {}
    
    # 1. Recent conversation (Firestore)
    context = get_context(user_id)
    if context:
        memory["recent"] = context
    
    # 2. PostgreSQL facts
    pg_data = load_user_memory(user_id, limit=10)
    if pg_data and pg_data.get("facts"):
        facts_str = "\n".join([f"- {f['content']}" for f in pg_data["facts"]])
        memory["postgres"] = facts_str
    
    # 3. Firestore personal facts
    try:
        facts_docs = db.collection("users").document(user_id).collection("facts").stream()
        personal_facts = []
        for doc in facts_docs:
            data = doc.to_dict()
            personal_facts.append(f"{data['key']}: {data['value']}")
        if personal_facts:
            memory["personal"] = "\n".join(personal_facts)
    except Exception as e:
        log_error("build_memory_block", "load_facts", e, user_id=user_id)
    
    return memory

# ── Health Check ──
@app.get("/health")
async def health_check():
    return {"status": "ARIA 3.5 alive 💚", "stage": "PRODUCTION"}

# ── Ping ──
@app.get("/ping")
async def ping():
    return {"pong": "ok"}

# ── Main Chat Endpoint ──
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start_time = time.time()
    message = request.message.strip()
    email = request.email.strip().lower()
    
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    uid_result = generate_aria_uid(email)
    if "error" in uid_result:
        raise HTTPException(status_code=400, detail=uid_result["error"])
    user_id = uid_result["aria_uid"]
    
    try:
        # ── STEP 1: Human First ──
        human = handle_human_first(message, user_id)
        if human["handled"]:
            return ChatResponse(reply=human["response"])
        
        # ── STEP 2: Check Pending Session ──
        session = get_pending_session(user_id)
        if session:
            if message.lower().strip() in ["cancel", "nevermind", "stop", "forget it"]:
                clear_pending_session(user_id)
                return ChatResponse(reply="Alright, I've cancelled that request. What would you like to do now?")
            
            state = get_conversation_state(user_id) or {}
            intent = discover_intent(message)
            result = process_conversation_brain(message, user_id, state, intent)
            decision = result.get("decision", {})
            new_state = result.get("new_state", {})
            
            # Load memory for pending session too
            memory_block = build_memory_block(user_id)
            if memory_block:
                new_state["memory"] = memory_block
            
            response = execute_decision(decision, message, user_id, {**state, **new_state})
            if new_state:
                save_conversation_state(user_id, new_state)
            return ChatResponse(reply=response)
        
        # ── STEP 3: Casual Manager ──
        casual = handle_casual_conversation(message, user_id)
        if casual["handled"]:
            return ChatResponse(reply=casual["response"])
        
        # ── STEP 4: Load State ──
        state = get_conversation_state(user_id) or {}
        goals = get_goals(user_id)
        state["goals"] = goals
        
        # ── STEP 5: Load ALL Memory into state ──
        memory_block = build_memory_block(user_id)
        if memory_block:
            state["memory"] = memory_block
        else:
            state["memory"] = {}
        
        # ── STEP 6: Intent Discovery ──
        understanding = get_understanding(user_id)
        resolved_intents = understanding.get("resolved_intents", [])
        
        if is_topic_change(message):
            clear_understanding(user_id)
            state.pop("awaiting", None)
            state.pop("question", None)
            save_conversation_state(user_id, state)
        
        intent = None
        if resolved_intents and not state.get("awaiting"):
            intent = {"intent": resolved_intents[-1], "confidence": 0.9}
        else:
            intent = discover_intent(message)
            if intent.get("clarification") and not state.get("awaiting") == "clarification":
                state["awaiting"] = "clarification"
                state["question"] = intent["clarification"]
                save_conversation_state(user_id, state)
                return ChatResponse(reply=intent["clarification"])
        
        # ── STEP 7: Conversation Brain ──
        result = process_conversation_brain(message, user_id, state, intent or {"intent": "general", "confidence": 0.5})
        decision = result.get("decision", {})
        new_state = result.get("new_state", {})
        
        # ── STEP 8: Response Engine ──
        # Merge memory from state into new_state (if not already present)
        if state.get("memory") and not new_state.get("memory"):
            new_state["memory"] = state["memory"]
        
        # Pass the merged state (state + new_state) to execute_decision
        merged_state = {**state, **new_state}
        response = execute_decision(decision, message, user_id, merged_state)
        
        # ── STEP 9: Update State ──
        if new_state:
            save_conversation_state(user_id, new_state)
            if new_state.get("current_goal") or new_state.get("long_term_goal"):
                update_goals(user_id, {
                    "current_goal": new_state.get("current_goal"),
                    "long_term_goal": new_state.get("long_term_goal"),
                    "current_task": new_state.get("current_task")
                })
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"REQUEST | user:{user_id} | time:{elapsed_ms:.0f}ms | ✓ SUCCESS")
        
        return ChatResponse(reply=response)
    
    except Exception as e:
        error_msg = traceback.format_exc()
        log_error("chat_endpoint", "process_message", e, user_id=user_id, context=error_msg)
        print(f"ERROR: {error_msg}")  # This will show in Render logs
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# ── Feedback Endpoint ──
@app.post("/feedback")
async def feedback(request: FeedbackRequest):
    return {"status": "Feedback recorded", "score": request.score}

# ── Upload Endpoints ──
@app.post("/upload-ocr")
async def upload_ocr(request: UploadRequest):
    return {"status": "OCR completed", "text": "Extracted text here"}

@app.post("/upload-pdf")
async def upload_pdf(request: UploadRequest):
    return {"status": "PDF processed", "text": "Extracted text here"}

# ── Debug Endpoint ──
@app.get("/debug")
async def debug_info():
    return {
        "status": "ARIA 3.5 running on FastAPI",
        "modules": {
            "income": module_registry.get("task") is not None,
            "education": "S8 functions available"
        },
        "features": get_feature_flags()
    }

# ── Error Handler ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log_error("global", "unhandled", str(exc), severity="CRITICAL")
    return JSONResponse(
        status_code=500,
        content={"error": f"An unexpected error occurred: {str(exc)}"}
    )

# ── Serve Frontend ──

@app.get("/")
async def serve_index():
    """Serve the main ARIA chat interface."""
    return FileResponse("public/index.html")

@app.get("/{file_path:path}")
async def serve_static(file_path: str):
    """
    Serve static files from the public folder.
    This handles login.html, favicon.ico, and any other public files.
    """
    # Skip API and docs routes (FastAPI handles them first)
    full_path = f"public/{file_path}"
    if os.path.exists(full_path):
        return FileResponse(full_path)
    raise HTTPException(status_code=404, detail="File not found")

# ── Debug Endpoints ──

@app.get("/trace")
async def view_trace(user_id: str = None, limit: int = 100):
    from brain import get_trace
    traces = get_trace(user_id, limit)
    return {
        "count": len(traces),
        "traces": traces,
        "message": f"Showing last {len(traces)} steps{' for user ' + user_id if user_id else ' (all users)'}"
    }

@app.get("/debug-memory")
async def debug_memory(email: str):
    from brain import generate_aria_uid, db, load_user_memory, get_context
    
    uid_result = generate_aria_uid(email)
    if "error" in uid_result:
        return {"error": uid_result["error"]}
    uid = uid_result["aria_uid"]
    
    # Get Firebase memory
    firebase_memory = []
    docs = db.collection("users").document(uid).collection("memory").order_by("t", direction=firestore.Query.DESCENDING).limit(10).stream()
    for doc in docs:
        data = doc.to_dict()
        firebase_memory.append({
            "message": data.get("m", ""),
            "response": data.get("r", "")[:200],
            "time": data.get("t", "")
        })
    
    # Get PostgreSQL memory
    pg_memory = load_user_memory(uid, limit=10)
    
    # Get facts
    facts = []
    fact_docs = db.collection("users").document(uid).collection("facts").stream()
    for doc in fact_docs:
        facts.append(doc.to_dict())
    
    # Get conversation state
    state = get_conversation_state(uid) or {}
    
    return {
        "uid": uid,
        "firebase_memory_count": len(firebase_memory),
        "firebase_memory": firebase_memory[:5],
        "postgres_memory": pg_memory,
        "facts": facts,
        "state": {
            "awaiting": state.get("awaiting"),
            "question": state.get("question"),
            "has_goals": bool(state.get("goals")),
            "has_context": bool(state.get("context"))
        }
}

@app.get("/debug-facts")
async def debug_facts(email: str):
    from brain import generate_aria_uid, db
    uid_result = generate_aria_uid(email)
    if "error" in uid_result:
        return {"error": uid_result["error"]}
    uid = uid_result["aria_uid"]
    facts = []
    docs = db.collection("users").document(uid).collection("facts").stream()
    for doc in docs:
        facts.append(doc.to_dict())
    return {"uid": uid, "facts": facts, "count": len(facts)}

# ── Run ──
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
