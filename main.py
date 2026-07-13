from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# ── Initialize Firestore FIRST ──
if not firebase_admin._apps:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firestore initialized in main")
    else:
        print("❌ FIREBASE_CREDENTIALS not found")
        db = None
else:
    db = firestore.client()
    print("✅ Firestore already initialized")

# ── Import brain (after Firestore is ready) ──
from brain import ask, generate_aria_uid

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel):
    message: str
    email: str

class ChatResponse(BaseModel):
    reply: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/ping")
async def ping():
    return {"pong": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        uid_result = generate_aria_uid(req.email.lower())
        user_id = uid_result["aria_uid"]
    except Exception as e:
        raise HTTPException(500, detail=str(e))
    reply = ask(req.message, user_id, None)
    return ChatResponse(reply=reply)

@app.get("/debug-uid")
async def debug_uid(email: str):
    from brain import generate_aria_uid
    result = generate_aria_uid(email)
    return result

@app.get("/")
async def index():
    return FileResponse("public/index.html")

@app.get("/{path:path}")
async def static(path: str):
    full_path = f"public/{path}"
    if os.path.exists(full_path):
        return FileResponse(full_path)
    raise HTTPException(404, detail="Not found")
