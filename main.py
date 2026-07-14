from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# ── Initialize Firestore ──
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

# ── Import brain and initialize PostgreSQL ──
from brain import ask, generate_aria_uid, init_postgres

print("🔧 Initializing PostgreSQL pool...")
init_postgres()
print("✅ PostgreSQL pool initialized")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel):
    message: str
    email: str

class ChatResponse(BaseModel):
    reply: str

# ─── SPECIFIC ROUTES (in order of priority) ─────────────────

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
        reply = ask(req.message, user_id, None)
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/debug-uid")
async def debug_uid(email: str):
    from brain import generate_aria_uid
    result = generate_aria_uid(email)
    return result

@app.get("/debug-db")
async def debug_db():
    from brain import _postgres_pool
    if _postgres_pool is None:
        return {"error": "PostgreSQL pool is None"}
    try:
        conn = _postgres_pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        _postgres_pool.putconn(conn)
        return {"connected": True, "user_count": count}
    except Exception as e:
        return {"error": str(e)}

@app.get("/check-db")
async def check_db():
    """Check if users table exists and count rows."""
    from brain import _postgres_pool
    if _postgres_pool is None:
        return {"error": "PostgreSQL pool is None"}
    conn = None
    try:
        conn = _postgres_pool.getconn()
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'users'
            );
        """)
        table_exists = cur.fetchone()[0]
        if not table_exists:
            return {"table_exists": False, "message": "users table does not exist"}
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        cur.execute("SELECT aria_uid, email FROM users LIMIT 5")
        rows = cur.fetchall()
        _postgres_pool.putconn(conn)
        return {
            "table_exists": True,
            "row_count": count,
            "sample_rows": [{"aria_uid": r[0], "email": r[1]} for r in rows]
        }
    except Exception as e:
        if conn:
            _postgres_pool.putconn(conn)
        return {"error": str(e)}

@app.get("/")
async def index():
    return FileResponse("public/index.html")

# ─── CATCH‑ALL ROUTE (MUST BE LAST) ──────────────────────────

@app.get("/{path:path}")
async def static(path: str):
    full_path = f"public/{path}"
    if os.path.exists(full_path):
        return FileResponse(full_path)
    raise HTTPException(404, detail="Not found")

@app.get("/context")
async def get_context(uid: str):
    """Return conversation history for a user."""
    from brain import get_full_history
    try:
        history = get_full_history(uid)
        if history:
            return {"context": history}
        return {"context": ""}
    except Exception as e:
        return {"error": str(e), "context": ""}

@app.get("/get-uid")
async def get_uid(email: str):
    """Return the ARIA UID for a given email."""
    from brain import generate_aria_uid
    result = generate_aria_uid(email)
    return result

@app.post("/set_user_name")
async def set_user_name(request: dict):
    """Set the user's name using email (not Firebase UID)."""
    email = request.get("email", "").strip().lower()
    name = request.get("name", "").strip()
    if not email or not name:
        raise HTTPException(400, detail="Missing email or name")
    
    from brain import generate_aria_uid, db
    uid_result = generate_aria_uid(email)
    if "error" in uid_result:
        raise HTTPException(400, detail=uid_result["error"])
    aria_uid = uid_result["aria_uid"]
    
    # Store name in Firestore facts
    if db:
        try:
            fact_ref = db.collection("users").document(aria_uid).collection("facts").document("name")
            fact_ref.set({"key": "name", "value": name})
            return {"status": "ok", "aria_uid": aria_uid}
        except Exception as e:
            raise HTTPException(500, detail=str(e))
    return {"status": "ok", "aria_uid": aria_uid}

@app.get("/get-uid")
async def get_uid(email: str):
    """Return the ARIA UID for a given email."""
    from brain import generate_aria_uid
    result = generate_aria_uid(email)
    return result

@app.post("/set_user_name")
async def set_user_name(request: dict):
    """Set the user's name using email (not Firebase UID)."""
    email = request.get("email", "").strip().lower()
    name = request.get("name", "").strip()
    if not email or not name:
        raise HTTPException(400, detail="Missing email or name")
    
    from brain import generate_aria_uid, db
    uid_result = generate_aria_uid(email)
    if "error" in uid_result:
        raise HTTPException(400, detail=uid_result["error"])
    aria_uid = uid_result["aria_uid"]
    
    if db:
        try:
            fact_ref = db.collection("users").document(aria_uid).collection("facts").document("name")
            fact_ref.set({"key": "name", "value": name})
            return {"status": "ok", "aria_uid": aria_uid}
        except Exception as e:
            raise HTTPException(500, detail=str(e))
    return {"status": "ok", "aria_uid": aria_uid}
