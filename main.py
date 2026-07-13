from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from brain import ask, generate_aria_uid

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel):
    message: str
    email: str

class ChatResponse(BaseModel):
    reply: str

# ── Health check (explicit) ──
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/ping")
async def ping():
    return {"pong": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    uid_result = generate_aria_uid(req.email.lower())
    if "error" in uid_result:
        raise HTTPException(400, detail=uid_result["error"])
    user_id = uid_result["aria_uid"]
    reply = ask(req.message, user_id, None)
    return ChatResponse(reply=reply)

@app.get("/")
async def index():
    return FileResponse("public/index.html")

# ── Catch-all must be LAST ──
@app.get("/{path:path}")
async def static(path: str):
    full_path = f"public/{path}"
    if os.path.exists(full_path):
        return FileResponse(full_path)
    raise HTTPException(404, detail="Not found")
