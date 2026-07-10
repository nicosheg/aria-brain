# ════════════════════════════════════════════════════════════════════
# ARIA FastAPI Server – Cognitive Architecture Integration
# ════════════════════════════════════════════════════════════════════

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import time
import hashlib

# ── Simple UID generator (no brain.py dependency) ──
def generate_aria_uid(email: str) -> dict:
    email = email.strip().lower()
    uid = f"aria_{hashlib.sha256(email.encode()).hexdigest()[:12]}"
    return {"aria_uid": uid}

# ── Import cognitive architecture ──
from cognitive.core.orchestrator import Orchestrator

# ── FastAPI App ──
app = FastAPI(
    title="ARIA – Life Operating System",
    description="Your AI companion for income, education, and personal growth.",
    version="3.5.0"
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request Models ──
class ChatRequest(BaseModel):
    message: str
    email: str

class ChatResponse(BaseModel):
    reply: str

# ── Global orchestrator cache ──
_orchestrators = {}

def get_orchestrator_for_user(user_id: str) -> Orchestrator:
    if user_id not in _orchestrators:
        _orchestrators[user_id] = Orchestrator(user_id)
    return _orchestrators[user_id]

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
        orchestrator = get_orchestrator_for_user(user_id)
        result = orchestrator.process("conversation", message, {"email": email})
        response = result.get("response", "I'm thinking...")
        
        elapsed_ms = (time.time() - start_time) * 1000
        print(f"REQUEST | user:{user_id} | time:{elapsed_ms:.0f}ms | ✓ SUCCESS")
        
        return ChatResponse(reply=response)
    
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"ERROR: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# ── Debug Endpoints ──
@app.get("/debug-state")
async def debug_state(email: str):
    uid_result = generate_aria_uid(email)
    if "error" in uid_result:
        return {"error": uid_result["error"]}
    user_id = uid_result["aria_uid"]
    orchestrator = get_orchestrator_for_user(user_id)
    return orchestrator.get_state()

@app.get("/debug-world")
async def debug_world(email: str, query: str = ""):
    uid_result = generate_aria_uid(email)
    if "error" in uid_result:
        return {"error": uid_result["error"]}
    user_id = uid_result["aria_uid"]
    orchestrator = get_orchestrator_for_user(user_id)
    return orchestrator.get_world_model(query or "test")

# ── Serve Frontend ──
@app.get("/")
async def serve_index():
    return FileResponse("public/index.html")

@app.get("/{file_path:path}")
async def serve_static(file_path: str):
    full_path = f"public/{file_path}"
    if os.path.exists(full_path):
        return FileResponse(full_path)
    raise HTTPException(status_code=404, detail="File not found")

# ── Run ──
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
