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

@app.get("/")
async def index():
    return FileResponse("public/index.html")

@app.get("/{path:path}")
async def static(path: str):
    full_path = f"public/{path}"
    if os.path.exists(full_path):
        return FileResponse(full_path)
    raise HTTPException(404, detail="Not found")

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
        
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'users'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            return {"table_exists": False, "message": "users table does not exist"}
        
        # Count rows
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        
        # Get first 5 rows
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
        
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'users'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            return {"table_exists": False, "message": "users table does not exist"}
        
        # Count rows
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        
        # Get first 5 rows
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
