from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os, time, hashlib

def generate_aria_uid(email: str) -> dict:
    email = email.strip().lower()
    uid = f"aria_{hashlib.sha256(email.encode()).hexdigest()[:12]}"
    return {"aria_uid": uid}

from cognitive.core.orchestrator import Orchestrator

app = FastAPI(title="ARIA", version="3.5.0")
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

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ARIA 3.5 alive 💚"}

@app.get("/ping")
async def ping():
    return {"pong": "ok"}

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

@app.get("/")
async def serve_index():
    return FileResponse("public/index.html")

@app.get("/{file_path:path}")
async def serve_static(file_path: str):
    full_path = f"public/{file_path}"
    if os.path.exists(full_path):
        return FileResponse(full_path)
    raise HTTPException(status_code=404, detail="Not found")

@app.post("/trace-chat")
async def trace_chat(request: dict):
    query = request.get("query", "unknown")
    return {
        "response": f"🔍 Debugging: {query}\n\nI see you're debugging. This endpoint is now working.",
        "trace_context": {"request_id": "debug", "span_count": 0, "errors": 0}
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
