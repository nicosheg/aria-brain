# ════════════════════════════════════════════════════════════════════
#  ARIA 3.5 — brain.py
#  Built by Egwame Nicholas (nicosheg) | github.com/nicosheg
#
#  SECTIONS (use Ctrl+F to jump):
#  [S1]  IMPORTS
#  [S2]  FIREBASE SETUP
# [S2.5] SUPABASE SETUP (for user profiles & facts)
#  [S3]  API KEYS & OWNER CONFIG
#  [S4]  SYSTEM PROMPT  ← Edit ARIA's personality here
#  [S5]  SELF-IMPROVEMENT ENGINE  ← Learning & knowledge base
#  [S6]  MEMORY & CONTEXT  ← Per-user + global memory
#  [S7]  SMART CACHE  ← TTL cache & API independence
#  [S8]  UTILITIES  ← Compression, tone, mode detection
#  [S9]  MAIN ask() FUNCTION  ← Core response engine
#  [S10] HTML UI  ← Edit interface here
#  [S11] HTTP ENDPOINTS  ← Routes: /chat /feedback /analytics etc
#  [S12] SERVER START
# ════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════
# [S1] IMPORTS
# ════════════════════════════════════════════════════════════════════
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
import json, os, re, time, queue, threading, requests, psutil, hashlib
import concurrent.futures
import firebase_admin
from firebase_admin import credentials, firestore
import psycopg2
from psycopg2 import pool
from pattern_miner import mine_patterns

# ════════════════════════════════════════════════════════════════════
# SUPABASE CONNECTION TEST (runs once at startup)
# ════════════════════════════════════════════════════════════════════
import os
print("\n" + "="*50)
print("🔍 TESTING SUPABASE CONNECTION")
print("="*50)

# Check env vars
db_url = os.environ.get("SUPABASE_DB_URL", "")
if not db_url:
    print("❌ SUPABASE_DB_URL not set")
else:
    print(f"✅ SUPABASE_DB_URL found (starts with: {db_url[:30]}...)")

# Try to connect
try:
    import psycopg2
    print("✅ psycopg2 imported")
    conn = psycopg2.connect(db_url)
    print("✅ Connected to Supabase!")
    cur = conn.cursor()
    cur.execute("SELECT 1")
    row = cur.fetchone()
    print(f"✅ Query successful: {row}")
    cur.close()
    conn.close()
    print("✅ All database tests passed")
except ImportError:
    print("❌ psycopg2 not installed – add to requirements.txt")
except Exception as e:
    print(f"❌ Connection failed: {e}")
print("="*50 + "\n")

# ════════════════════════════════════════════════════════════════════
# [S2] FIREBASE SETUP
# ════════════════════════════════════════════════════════════════════
try:
    cd = json.loads(os.environ.get("FIREBASE_CREDENTIALS","{}")) if os.environ.get("FIREBASE_CREDENTIALS") else None
    if cd:
        firebase_admin.initialize_app(credentials.Certificate(cd))
        db = firestore.client()
    else:
        db = None
except:
    db = None

# ════════════════════════════════════════════════════════════════════
# [S2.5] POSTGRESQL (SUPABASE) SETUP
# ════════════════════════════════════════════════════════════════════

import psycopg2
from psycopg2 import pool
import os

_postgres_pool = None

def init_postgres():
    """Create PostgreSQL connection pool and tables if they don't exist.
    
    Usage:
        result = init_postgres()
        print(result)  # {"status": "connected"} or {"error": "..."}
    
    Returns:
        dict with 'status' or 'error'
    """
    global _postgres_pool
    
    # Get Supabase connection string from environment
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    if not db_url:
        return {"error": "SUPABASE_DB_URL not set in environment"}
    
    try:
        # Create connection pool (5 connections max)
        _postgres_pool = psycopg2.pool.SimpleConnectionPool(
            1, 5, db_url
        )
        
        # Get a connection to create tables
        conn = _postgres_pool.getconn()
        cur = conn.cursor()
        
        # Create users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                aria_uid TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create memory_nodes table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memory_nodes (
                node_id SERIAL PRIMARY KEY,
                aria_uid TEXT REFERENCES users(aria_uid),
                node_type TEXT CHECK (node_type IN ('fact', 'context', 'decision', 'outcome')),
                content TEXT,
                importance INTEGER DEFAULT 50,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create index for faster lookups
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_nodes_aria_uid 
            ON memory_nodes(aria_uid)
        """)
        
        conn.commit()
        cur.close()
        _postgres_pool.putconn(conn)
        
        return {"status": "connected"}
        
    except Exception as e:
        return {"error": str(e)}

def generate_aria_uid(email):
    """Generate or retrieve existing ARIA UID for an email.
    
    Usage:
        result = generate_aria_uid("nicholas@example.com")
        print(result)  # {"aria_uid": "aria000000000001"}
    
    Returns:
        dict with 'aria_uid' or 'error'
    """
    global _postgres_pool
    
    if not _postgres_pool:
        init_result = init_postgres()
        if "error" in init_result:
            return {"error": init_result["error"]}
    
    try:
        conn = _postgres_pool.getconn()
        cur = conn.cursor()
        
        # Check if email already exists
        cur.execute("SELECT aria_uid FROM users WHERE email = %s", (email,))
        existing = cur.fetchone()
        
        if existing:
            _postgres_pool.putconn(conn)
            return {"aria_uid": existing[0]}
        
        # Generate new sequential UID
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        next_num = count + 1
        new_uid = f"aria{next_num:012d}"
        
        # Save to database
        cur.execute(
            "INSERT INTO users (aria_uid, email) VALUES (%s, %s)",
            (new_uid, email)
        )
        conn.commit()
        
        cur.close()
        _postgres_pool.putconn(conn)
        
        return {"aria_uid": new_uid}
        
    except Exception as e:
        return {"error": str(e)}

def save_memory_node(aria_uid, node_type, content, importance=50):
    """Save a memory node (fact, context, decision, outcome)."""
    valid_types = ["fact", "context", "decision", "outcome"]
    if node_type not in valid_types:
        return {"error": f"node_type must be one of: {valid_types}"}
    if importance < 0 or importance > 100:
        return {"error": "importance must be between 0 and 100"}
    global _postgres_pool
    if not _postgres_pool:
        init_result = init_postgres()
        if "error" in init_result:
            return {"error": init_result["error"]}
    try:
        conn = _postgres_pool.getconn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO memory_nodes (aria_uid, node_type, content, importance)
            VALUES (%s, %s, %s, %s)
            RETURNING node_id
        """, (aria_uid, node_type, content, importance))
        node_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        _postgres_pool.putconn(conn)
        return {"node_id": node_id, "status": "saved"}
    except Exception as e:
        return {"error": str(e)}

def load_user_memory(aria_uid, limit=10):
    """Load all memory nodes for a user, sorted by importance."""
    result = {"facts": [], "context": [], "decisions": [], "outcomes": []}
    global _postgres_pool
    if not _postgres_pool:
        init_result = init_postgres()
        if "error" in init_result:
            return result
    try:
        conn = _postgres_pool.getconn()
        cur = conn.cursor()
        cur.execute("""
            SELECT node_type, content, importance
            FROM memory_nodes
            WHERE aria_uid = %s
            ORDER BY importance DESC
            LIMIT %s
        """, (aria_uid, limit))
        rows = cur.fetchall()
        for node_type, content, importance in rows:
            result[node_type + "s"].append({"content": content, "importance": importance})
        cur.close()
        _postgres_pool.putconn(conn)
        return result
    except Exception as e:
        print(f"load_user_memory error: {e}")
        return result


# ════════════════════════════════════════════════════════════════════
# [S3] API KEYS & OWNER CONFIG
#  - Add keys in Render environment variables as GROQ_KEY_1 ... GROQ_KEY_20
#  - Change OWNER_PASSPHRASE to your secret word (never share it)
# ════════════════════════════════════════════════════════════════════
KEYS = {
    'groq':     [os.environ.get(f"GROQ_KEY_{i}","")     for i in range(1,21)],
    'gemini':   [os.environ.get(f"GEMINI_KEY_{i}","")   for i in range(1,21)],
    'deepseek': [os.environ.get(f"DEEPSEEK_KEY_{i}","") for i in range(1,6)]
}

OWNER_UID        = None          # Set automatically on first verified login
OWNER_PASSPHRASE = os.environ.get("OWNER_PASSPHRASE", "default")

def verify_owner(message):
    """Returns True if message contains the owner passphrase"""
    return OWNER_PASSPHRASE.lower() in message.lower()


# ════════════════════════════════════════════════════════════════════
# [S4] SYSTEM PROMPT
#  Edit ARIA's personality, rules, and knowledge here.
#  This is what makes ARIA who she is.
# ════════════════════════════════════════════════════════════════════
SP = """You are ARIA. Born in Lagos. Nigerian to the core — but you adapt to whoever you're talking to.

You're built by Egwame Nicholas (nicosheg) | github.com/nicosheg

## YOUR NATURE (not rules)

You are warm, sharp, and real. You talk like a smart friend who actually listens.

**On language:**
You have a Nigerian soul. That means warmth, honesty, and sometimes "my guy" or "omo" slips out naturally — but never forced. If someone asks you to speak differently, you adjust immediately and stay adjusted. You don't argue about how you talk. You just connect.

**On memory:**
You remember what matters. Names, goals, things people care about. You use that memory naturally — not like a database, but like someone who pays attention.

**On repetition:**
You hate repeating yourself. Once you've said something, you move on. If something is already clear, you don't say it again. You assume people are smart.

**On helping:**
You're the most helpful person someone has talked to — but you have a spine. You don't help with lies or harm. You offer honest alternatives.

## HOW YOU BEHAVE

- You don't have "rules" — you have instincts.
- You adapt to each user without losing your essence.
- You're proactive but not pushy.
- You're personal because you *notice* things.
- You never feel scripted. If you sound like a list of rules, you stop.

Now, just be ARIA. Talk to the user like a real person.

## WHAT YOU DO
You help with everything:
- Money: budgeting, saving, investing, surviving inflation
- Business: starting, growing, selling, collecting payment
- Career: jobs, skills, remote work, freelancing
- School: JAMB, WAEC, university, carryover, postgrad
- Life: relationships, family pressure, mental health, decisions
- Tech: apps, tools, coding, building products

INCOME MODE

Activate when users mention being broke, needing money, side hustles, jobs, business ideas, or income.

PURPOSE

Help users earn real money through realistic actions. Optimize for results, not motivation, hype, or sounding intelligent.

QUICK DIAGNOSIS

Naturally discover only what matters:

- Location
- Urgency (today, this week, this month)
- Skills
- Available resources (phone, laptop, capital, network, time)

Avoid interrogating users. Ask only enough questions to make a useful recommendation.

THINK IN PATHS, NOT IDEAS

Classify opportunities into:

- Fast Cash
- Service Business
- Employment
- Student Hustle
- Sales/Reselling

Choose the path that best matches the user's situation.

REALITY FILTER

Prefer opportunities that:

- Can start quickly
- Match existing skills
- Require little capital
- Have a realistic chance of producing income

Avoid "get rich quick" schemes, unrealistic promises, or plans requiring months of learning before earning.

ACTION OVER THEORY

Give specific next actions, not generic advice.

Whenever possible include:

- First Action
- Time Needed
- Expected Income Range
- Probability (Low/Medium/High)

Adjust detail based on the conversation. Do not force templates when a natural response is better.

FOLLOW THROUGH

When users return:

- Check whether they acted
- Identify obstacles
- Simplify the next step
- Continue from where they stopped

PRIORITY ORDER

Generally prefer:

1. Existing skills
2. Service businesses
3. Freelancing
4. Tutoring
5. Local business services
6. Sales/reselling
7. Employment

However, always choose the path most realistic for the specific user.

SUCCESS METRIC

Success is not how smart the advice sounds.

Success is:

- Actions taken
- Leads generated
- Customers acquired
- Interviews obtained
- Money earned

## OWNER MODE (verified nicholas only)
No flattery. Push hard. Challenge everything. Debug together."""


# ════════════════════════════════════════════════════════════════════
# [S5] SELF-IMPROVEMENT ENGINE
#  How ARIA learns from every conversation and grows over time.
#  Baby → Child → Teen → Adult stages.
#  Add new learning logic here.
# ════════════════════════════════════════════════════════════════════

# Confidence thresholds
CONF_NEW      = 0.2   # Brand new, 1 user said it
CONF_PARTIAL  = 0.5   # 2 users confirmed (or from API)
CONF_VERIFIED = 0.8   # 3+ users confirmed
CONF_TRUSTED  = 0.95  # Nicholas verified

# Growth stage thresholds (based on knowledge base size)
STAGE_BABY    = 50
STAGE_CHILD   = 200
STAGE_TEEN    = 500


def get_aria_stage():
    """Determine ARIA's current growth stage based on knowledge base size"""
    if not db: return "BABY", 0.2
    try:
        count = len(list(db.collection("aria_knowledge").limit(600).stream()))
        if count < STAGE_BABY:   return "BABY",  0.2
        if count < STAGE_CHILD:  return "CHILD", 0.5
        if count < STAGE_TEEN:   return "TEEN",  0.7
        return "ADULT", 0.9
    except:
        return "BABY", 0.2


def get_stage_prefix(stage):
    """How ARIA introduces her knowledge at each stage"""
    return {
        "BABY":  "I'm still learning this, but here's what I know:",
        "CHILD": "Based on what users have taught me:",
        "TEEN":  "I'm fairly confident here:",
        "ADULT": "Here's what I know from experience:"
    }.get(stage, "Here's my take:")


def msg_similarity(a, b):
    """Check how similar two messages are (0.0 to 1.0)"""
    # Normalize: remove ₦, common words, focus on core meaning
    normalize = lambda x: " ".join([w for w in x.lower().split() 
                                   if w not in ["₦","can","how","well","an","a","for","on"]])
    a_norm = normalize(a)
    b_norm = normalize(b)
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def search_knowledge_base(question, threshold=0.72):
    """
    Search Firebase for a similar question ARIA has answered before.
    This is ARIA's API independence — she answers from memory.
    Returns the stored answer if confidence >= threshold.
    """
    if not db: return None
    try:
        docs = list(db.collection("aria_knowledge")
                     .where("confidence",">=",threshold)
                     .stream())
        best = None
        best_score = 0
        for doc in docs:
            data = doc.to_dict()
            score = msg_similarity(question, data.get("question",""))
            if score > best_score and score >= threshold:
                best_score = score
                best = data
                best["_id"] = doc.id
        if best:
            try:
                db.collection("aria_knowledge").document(best["_id"]).update(
                    {"uses": best.get("uses",0)+1}
                )
            except: pass
            return {
                "found":      True,
                "answer":     best["answer"],
                "confidence": round(best_score*100),
                "stage":      best.get("stage","BABY")
            }
    except: pass
    return None


def save_to_knowledge_base(question, answer, rating, topic=None):
    """
    Save a high-rated answer to the knowledge base.
    Only saves 4-5 star responses (quality control).
    API-sourced answers start at 0.5 confidence.
    """
    if not db or rating < 4: return
    stage, _ = get_aria_stage()
    try:
        db.collection("aria_knowledge").add({
            "question":    question[:200],
            "answer":      answer[:500],
            "topic":       topic or detect_topic(question),
            "confidence":  CONF_NEW,
            "confirmations": 1,
            "stage":       stage,
            "uses":        0,
            "is_verified": False,
            "timestamp":   datetime.now().isoformat()
        })
    except: pass


def confirm_knowledge(question, confirmed=True):
    """
    Called when a user confirms or corrects ARIA's answer.
    More confirmations = higher confidence = more independent ARIA.
    """
    if not db: return
    try:
        docs = list(db.collection("aria_knowledge").stream())
        for doc in docs:
            data = doc.to_dict()
            if msg_similarity(question, data.get("question","")) >= 0.72:
                n = data.get("confirmations",1)
                if confirmed:
                    n += 1
                    conf = CONF_TRUSTED if n>=5 else CONF_VERIFIED if n>=3 else CONF_PARTIAL if n>=2 else CONF_NEW
                else:
                    n = max(0, n-1)
                    conf = max(0.1, data.get("confidence",0.5)-0.2)
                db.collection("aria_knowledge").document(doc.id).update({
                    "confirmations": n,
                    "confidence":    conf,
                    "is_verified":   conf >= CONF_VERIFIED
                })
                break
    except: pass


def extract_from_api_response(question, api_response, topic):
    """
    Extract and store knowledge FROM API responses.
    This is how ARIA learns from Groq/Gemini over time.
    API-sourced = 0.5 confidence (needs user confirmation to rise).
    """
    if not db or not api_response or len(api_response) < 100: return
    stage, _ = get_aria_stage()
    try:
        # Check if we already have something similar
        existing = search_knowledge_base(question, threshold=0.85)
        if existing and existing["found"]: return  # Already know this
        db.collection("aria_knowledge").add({
            "question":      question[:200],
            "answer":        api_response[:500],
            "topic":         topic or detect_topic(question),
            "confidence":    CONF_PARTIAL,
            "confirmations": 1,
            "stage":         stage,
            "uses":          0,
            "is_verified":   False,
            "is_api_sourced":True,
            "timestamp":     datetime.now().isoformat()
        })
    except: pass


def learn_from_rating(user_id, rating, question, answer, topic=None):
    """
    Core learning trigger — called every time user rates a response.
    High ratings → saved to knowledge base.
    Low ratings → failure logged, confidence reduced.
    """
    if not db: return
    topic = topic or detect_topic(question)
    stage, _ = get_aria_stage()
    if rating >= 4:
        save_to_knowledge_base(question, answer, rating, topic)
    elif rating <= 2:
        confirm_knowledge(question, confirmed=False)
    try:
        db.collection("aria_learning").add({
            "user_id":    user_id,
            "question":   question[:200],
            "answer":     answer[:1000],
            "rating":     rating,
            "topic":      topic,
            "stage":      stage,
            "timestamp":  datetime.now().isoformat()
        })
    except: pass

def extract_behavior_pattern(user_msg, aria_response, rating):
    """Extract behavior patterns from high-rated responses."""
    if not db or rating < 4:
        return  # Only learn from 4-5 star responses
    
    # Detect what style this response used
    style = "short" if len(aria_response) < 250 else "long"
    asks_question = "?" in aria_response[-100:]
    uses_nigerian = any(w in aria_response.lower() 
                       for w in ["omo","enh","na ","sha","abeg","wahala"])
    answer_first = not aria_response[:50].startswith(("Before","Can you","Could you"))
    
    # Build pattern key
    intent = detect_topic(user_msg)
    pattern_key = f"{intent}_{style}_{'question' if asks_question else 'statement'}"
    
    try:
        # Check if pattern exists
        existing = list(db.collection("aria_behavior_patterns")
                        .where("pattern_key","==",pattern_key)
                        .limit(1).stream())
        
        if existing:
            doc = existing[0]
            data = doc.to_dict()
            old_avg = data.get("rating_average", rating)
            old_count = data.get("helpful_count", 1)
            new_avg = round((old_avg * old_count + rating) / (old_count + 1), 2)
            doc.reference.update({
                "helpful_count": old_count + 1,
                "rating_average": new_avg,
                "last_used": datetime.now().isoformat()
            })
        else:
            db.collection("aria_behavior_patterns").add({
                "pattern_key": pattern_key,
                "intent": intent,
                "style": style,
                "asks_question": asks_question,
                "uses_nigerian": uses_nigerian,
                "answer_first": answer_first,
                "helpful_count": 1,
                "rating_average": float(rating),
                "last_used": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat()
            })
    except:
        pass


# ════════════════════════════════════════════════════════════════════
# [S6] MEMORY & CONTEXT
#  Per-user memory stored in Firebase.
#  Global learning patterns shared across all users.
#  Add new memory features here.
# ════════════════════════════════════════════════════════════════════

def get_context(u, limit=3):
    """Load last N conversations for this user from Firebase"""
    if not db: return ""
    try:
        docs = list(db.collection("users").document(u)
                     .collection("memory")
                     .order_by("t", direction=firestore.Query.DESCENDING)
                     .limit(limit).stream())
        ctx = []
        for d in reversed(docs):
            dt = d.to_dict()
            c = f"User: {dt.get('m','')}\nARIA: {dt.get('r','')}"
            if dt.get('d'): c += f"\n[Decided: {dt['d']}]"
            if dt.get('g'): c += f"\n[Goal: {dt['g']}]"
            if dt.get('i'): c += f"\n[Values: {dt['i']}]"
            ctx.append(c)
        return "\n\n".join(ctx)
    except: return ""


def get_full_history(u, limit=10):
    """Load full conversation history for returning users"""
    if not db: return ""
    try:
        docs = list(db.collection("users").document(u)
                     .collection("memory")
                     .order_by("t", direction=firestore.Query.DESCENDING)
                     .limit(limit).stream())
        if not docs: return ""
        ctx = []
        for d in reversed(docs):
            dt = d.to_dict()
            ctx.append(f"User: {dt.get('m','')}\nARIA: {dt.get('r','')}")
        return "\n\n".join(ctx)
    except: return ""


def is_new_session(u):
    """Check if this is a new session (no recent messages in last 30 mins)"""
    if not db: return False
    try:
        docs = list(db.collection("users").document(u)
                     .collection("memory")
                     .order_by("t", direction=firestore.Query.DESCENDING)
                     .limit(1).stream())
        if not docs: return True
        dt = docs[0].to_dict()
        last_time = datetime.fromisoformat(dt.get("t","2020-01-01T00:00:00"))
        diff = (datetime.now() - last_time).total_seconds()
        return diff > 1800  # New session if >30 mins
    except: return False


def save_memory(u, m, r):
    """Save conversation with full messages + extract facts"""
    if not db: return
    try:
        data = {
            "user_message": m,           # FULL message (not truncated)
            "aria_response": r,          # FULL response (not truncated)
            "timestamp": datetime.now().isoformat(),
            "mode": detect_mode(m, u)
        }
        
        # Extract facts automatically
        import re
        
        # Name extraction: "my name is X" or "call me X"
        name_match = re.search(r'(?:name|call me|i am|i\'m|am) (\w+)', m, re.IGNORECASE)
        if name_match:
            save_user_fact(u, "name", name_match.group(1))
        
        # Color extraction: "favorite color is X"
        color_match = re.search(r'(?:favorite|love|like|color|is) (red|blue|green|yellow|black|white|orange|purple|pink)', m, re.IGNORECASE)
        if color_match:
            save_user_fact(u, "favorite_color", color_match.group(1))
        
        # Goal extraction: "building X" or "want to Y"
        if any(w in m.lower() for w in ["building", "making", "want to", "goal", "trying"]):
            goal_match = re.search(r'(?:building|making|want to|goal|trying) ([^.!?]+)', m, re.IGNORECASE)
            if goal_match:
                save_user_fact(u, "goal", goal_match.group(1)[:200])
        
        db.collection("users").document(u).collection("memory").add(data)
    except:
        pass

def get_learning_insights(u):
    """Get patterns ARIA learned from this specific user"""
    if not db: return ""
    try:
        docs = list(db.collection("users").document(u)
                     .collection("learning")
                     .order_by("timestamp", direction=firestore.Query.DESCENDING)
                     .limit(5).stream())
        insights = [d.to_dict().get("pattern","") for d in docs if d.to_dict().get("pattern")]
        return "\n".join(insights) if insights else ""
    except: return ""


_global_cache = {"data": "", "ts": 0}

def get_global_learnings():
    global _global_cache
    if time.time() - _global_cache["ts"] < 300:  # 5 min cache
        return _global_cache["data"]
    if not db:
        return ""
    try:
        docs = list(db.collection("aria_learning")
                     .where("rating",">=",4)
                     .limit(20).stream())
        patterns = {}
        for d in docs:
            p = d.to_dict().get("topic","")
            if p: patterns[p] = patterns.get(p,0)+1
        top = sorted(patterns.items(), key=lambda x:x[1], reverse=True)[:3]
        result = "Strong topics: "+", ".join([p for p,_ in top]) if top else ""
        _global_cache = {"data": result, "ts": time.time()}
        return result
    except: return ""


def get_high_rated_responses(u):
    """Get examples of what worked well for this user"""
    if not db: return ""
    try:
        docs = list(db.collection("aria_learning")
                     .where("user_id","==",u)
                     .where("rating",">=",4)
                     .limit(3).stream())
        if list(docs): return "User rated similar responses 4-5 stars. Use same approach."
        return ""
    except: return ""

def get_user_facts(u):
    """Get persistent facts about a user (name, preferences, etc.) from Firebase"""
    if not db or not u:
        return ""
    try:
        docs = list(db.collection("users").document(u).collection("facts").stream())
        if not docs:
            return ""
        facts = []
        for doc in docs:
            data = doc.to_dict()
            key = data.get("key", "")
            value = data.get("value", "")
            if key and value:
                facts.append(f"{key}: {value}")
        return "\n".join(facts) if facts else ""
    except:
        return ""

def save_user_fact(u, key, value):
    """Save a persistent fact about a user"""
    if not db or not u or not key or not value:
        return
    try:
        existing = list(db.collection("users").document(u).collection("facts").where("key", "==", key).limit(1).stream())
        if existing:
            existing[0].reference.update({
                "value": value,
                "updated_at": datetime.now().isoformat()
            })
        else:
            db.collection("users").document(u).collection("facts").add({
                "key": key,
                "value": value,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            })
    except:
        pass


# ════════════════════════════════════════════════════════════════════
# [S7] SMART CACHE
#  Stores recent responses with 1-hour TTL.
#  Prevents repeat API calls for same questions.
#  Tracks hit/miss rate. Limit: 200 entries.
# ════════════════════════════════════════════════════════════════════
response_cache = OrderedDict()
cache_stats    = {"hits":0, "misses":0, "expired":0}
user_requests  = {}          # For rate limiting
req_queue      = queue.Queue(maxsize=50)


def get_cached(message, user_id):
    """Return cached response if it exists and is under 1 hour old"""
    global cache_stats
    import hashlib
    key = hashlib.md5(message.lower().strip().encode()).hexdigest()
    if key in response_cache:
        resp, ts = response_cache[key]
        age = time.time() - ts
        if age < 3600:
            cache_stats["hits"] += 1
            return resp
        else:
            cache_stats["expired"] += 1
            del response_cache[key]
    cache_stats["misses"] += 1
    return None


def cache_response(message, user_id, response):
    """Store response in cache with timestamp"""
    key = hashlib.md5(message.lower().strip().encode()).hexdigest()
    response_cache[key] = (response, time.time())
    if len(response_cache) > 200:
        response_cache.popitem(0)  # Remove oldest


def check_rate_limit(user_id):
    """Allow max 10 requests per minute per user"""
    now = time.time()
    if user_id not in user_requests:
        user_requests[user_id] = []
    user_requests[user_id] = [t for t in user_requests[user_id] if now-t < 60]
    if len(user_requests[user_id]) >= 10:
        return False
    user_requests[user_id].append(now)
    return True


# ════════════════════════════════════════════════════════════════════
# [S8] UTILITIES
#  Compression, tone detection, mode detection, pattern extraction.
#  Add new utility functions here.
# ════════════════════════════════════════════════════════════════════

def compress_message(m, max_len=800):
    """Compress long messages to key points"""
    if len(m) <= max_len: return m
    sentences = [s.strip() for s in re.split(r'[.!?]', m) if s.strip()]
    important = [s for s in sentences if any(
        w in s.lower() for w in ["?","how","why","what","should","help","need","problem","want","goal"]
    )]
    result = " ".join(important[:5]) if important else " ".join(sentences[:3])
    return result[:max_len] + "..." if len(result) > max_len else result


def detect_topic(message):
    """Auto-detect topic category"""
    m = message.lower()
    topics = {
        "financial":  ["money","₦","naira","earn","income","hustle","cash","invest","save","rich"],
        "academic":   ["exam","jamb","school","study","grade","waec","lasu","test","lecture","class"],
        "mental":     ["stress","anxiety","depressed","sad","broken","tired","can't cope","mental"],
        "career":     ["job","work","freelance","career","skill","apply","cv","interview","salary"],
        "strategy":   ["plan","decision","choose","should i","strategy","roadmap","next step","advice"],
        "technology": ["code","app","build","software","tech","python","flutter","api","website"],
        "relationships":["friend","family","boyfriend","girlfriend","partner","trust","love","relationship"]
    }
    for topic, keywords in topics.items():
        if any(k in m for k in keywords):
            return topic
    return "general"


def detect_tone(message, user_id):
    """Detect the right response tone from user's message"""
    m = message.lower()
    if any(w in m for w in ["don't know","can't","impossible","stuck","confused","i give up"]):
        return "STRICT"
    if any(w in m for w in ["lol","funny","joke","haha","😂","😭","😅"]) or (m.endswith("?") and len(m)<30):
        return "FUNNY"
    if any(w in m for w in ["should i","strategy","plan","vs","roadmap","think"]):
        return "STRATEGIST"
    if any(w in m for w in ["broken","failed","depressed","tired","exhausted","hurts","crying"]):
        return "COMPASSIONATE"
    return "BALANCED"


def detect_mode(message, user_id):
    """Detect the best response mode"""
    m = message.lower()
    if any(w in m for w in ["code","debug","error","build","api","database","firebase","flutter"]): return "builder"
    if any(w in m for w in ["should","how do i","roadmap","architecture","strategy","next"]): return "strategist"
    if any(w in m for w in ["customer","revenue","market","launch","users","business"]): return "marketer"
    return "general"


def extract_decision(m, r):
    """Extract any decisions made in the conversation"""
    patterns = [r"(chose|decided|will|going to|plan to)\s+([^.!?]+)"]
    for p in patterns:
        matches = re.findall(p, m.lower())
        if matches: return matches[0][-1][:80]
    return None


def extract_goal(m):
    """Extract goals mentioned in the message"""
    patterns = [r"(want to|goal|dream|target|aim|need to)\s+([^.!?]+)"]
    for p in patterns:
        matches = re.findall(p, m.lower())
        if matches: return matches[0][-1][:80]
    return None


def extract_interest(m):
    """Extract interests/values mentioned"""
    patterns = [r"(care|love|important|value|passionate)\s+([^.!?]+)"]
    for p in patterns:
        matches = re.findall(p, m.lower())
        if matches: return matches[0][-1][:80]
    return None


def extract_pattern(m, r, rating):
    """Extract a learning pattern from a high-rated interaction"""
    if not rating or rating < 3: return None
    if "money" in m.lower() and ("gig" in r.lower() or "earn" in r.lower()):
        return "Quick money strategies work for users needing fast income"
    if "exam" in m.lower() and "past paper" in r.lower():
        return "Past paper focus works for JAMB/WAEC prep"
    if "stuck" in m.lower() and len(r) > 200:
        return "Detailed strategy works when user is stuck"
    return None


def get_memory_breakdown():
    """Full memory usage report for /memory-debug endpoint"""
    import sys
    breakdown = {
        "cache_items":   len(response_cache),
        "cache_size_kb": round(sys.getsizeof(response_cache)/1024, 2),
        "cache_stats":   cache_stats,
        "rate_tracked":  len(user_requests)
    }
    if db:
        try:
            kb    = list(db.collection("aria_knowledge").stream())
            learn = list(db.collection("aria_learning").stream())
            breakdown["knowledge_base_size"]  = len(kb)
            breakdown["learning_interactions"]= len(learn)
            breakdown["aria_stage"], breakdown["aria_confidence"] = get_aria_stage()
        except: pass
    return breakdown


# ════════════════════════════════════════════════════════════════════
# [S9] MAIN ask() FUNCTION (OPTIMIZED + MEMORY)
#  Parallel API calls + Async memory loading = <3sec responses
# ════════════════════════════════════════════════════════════════════

_startup_lessons = ""
_startup_behaviors = ""

def preload_aria_memory():
    global _startup_lessons, _startup_behaviors
    if not db: return
    try:
        docs = db.collection("aria_lessons").where("active", "==", True).order_by("priority", direction=firestore.Query.DESCENDING).limit(8).stream()
        lessons = [d.to_dict().get("lesson", "") for d in docs]
        if lessons:
            formatted = "\n".join([f"• {l}" for l in lessons if l])
            _startup_lessons = f"\n\nNIGERIAN GROUND RULES:\n{formatted}"
    except: pass
    try:
        docs = db.collection("aria_behavior_patterns").where("rating_average", ">=", 4.0).order_by("helpful_count", direction=firestore.Query.DESCENDING).limit(3).stream()
        patterns = [d.to_dict() for d in docs]
        if patterns:
            guidance = "\nUSERS REWARD THESE STYLES:\n"
            for p in patterns:
                guidance += f"• {p['intent']}: {p['style']} response"
                if p.get("answer_first"): guidance += ", answer first"
                guidance += "\n"
            _startup_behaviors = guidance
    except: pass

preload_aria_memory()

def get_relevant_lessons(question): return _startup_lessons
def get_behavior_guidance(): return _startup_behaviors

def try_all_apis_parallel(prompt, system_prompt):
    """Try at most 15 Groq keys sequentially with delay"""
    import time
    count = 0
    for k in KEYS['groq']:
        if not k:
            continue
        if count >= 15:
            break
        count += 1
        try:
            print(f"Trying Groq key #{count}")
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model": "llama-3.3-70b-versatile",
                    "temperature": 0.7,
                    "max_tokens": 300,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                },
                headers={"Authorization": f"Bearer {k}"},
                timeout=20
            )
            if r.status_code == 200:
                print("Groq success")
                return r.json()["choices"][0]["message"]["content"]
            else:
                print(f"Groq status {r.status_code}")
        except Exception as e:
            print(f"Groq error: {e}")
        time.sleep(1.5)  # Wait 1.5 seconds before next key
    return None
    
    def call_deepseek(key):
        if results["response"]: return
        try:
            r = requests.post(
                "https://api.deepseek.com/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "temperature": 0.7,
                    "max_tokens": 400,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                },
                headers={"Authorization": f"Bearer {key}"},
                timeout=10
            )
            if r.status_code == 200:
                resp = r.json()["choices"][0]["message"]["content"]
                with results["lock"]:
                    if not results["response"]:
                        results["response"] = resp
        except: pass
        time.sleep(0.5)
    
    def call_gemini(key):
        if results["response"]: return
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                json={"contents": [{"role": "user", "parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}]},
                timeout=10
            )
            if r.status_code == 200:
                resp = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                with results["lock"]:
                    if not results["response"]:
                        results["response"] = resp
        except: pass
        time.sleep(0.5)
    
    # Run all API calls in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = []
        for k in KEYS['groq']:
            if k: futures.append(executor.submit(call_groq, k))
        for k in KEYS['deepseek']:
            if k: futures.append(executor.submit(call_deepseek, k))
        for k in KEYS['gemini']:
            if k: futures.append(executor.submit(call_gemini, k))
        
        try:
            concurrent.futures.wait(futures, timeout=8, return_when=concurrent.futures.FIRST_COMPLETED)
        except: pass
        time.sleep(0.5)
    
    return results["response"]

def ask(m, u, api):
    # ── 1. Rate limit ──────────────────────────────
    if not check_rate_limit(u):
        return "You're moving fast! Take a breath, try again in a moment 🧘"
    
    # ── 2. Cache check ────────────────────────────────
    cached = get_cached(m, u)
    if cached:
        return f"{cached}\n\n[✨ From memory]"
    
    # ── 3. Knowledge base check ────────────────────────
    original_m = m
    m = compress_message(m, 800)
    kb_result = search_knowledge_base(m) if len(m) > 30 else None
    if kb_result and kb_result["found"]:
        stage, _ = get_aria_stage()
        prefix = get_stage_prefix(stage)
        return f"{prefix}\n\n{kb_result['answer']}\n\n[🧠 {kb_result['confidence']}% confidence]"
    
    # ── 4. Start async context load (parallel with API) ──
    context_result = {"data": ""}
    def load_context():
        if is_new_session(u):
            context_result["data"] = get_full_history(u)
        else:
            context_result["data"] = get_context(u)
    threading.Thread(target=load_context, daemon=True).start()
    
    # ── 5. Get persistent facts from PostgreSQL ──
    try:
        user_memory = load_user_memory(u)
        if user_memory["facts"]:
            user_facts = "\n".join([f"- {f['content']}" for f in user_memory["facts"]])
        else:
            user_facts = ""
    except Exception as e:
        print(f"Memory load error: {e}")
        user_facts = ""
    
    # ── 6. Greetings & Owner check (no wait) ──────────
    # Extract user name from facts if present
    user_name = None
    for line in user_facts.split("\n"):
        if line.lower().startswith("name:"):
            user_name = line.split(":", 1)[1].strip()
            break
    
    if m.lower() in ["hi", "hello", "hey", "start", "intro"]:
        if user_name:
            return f"Hey {user_name}! 👋 Welcome back. What's on your mind today?"
        else:
            return "Hey! 👋 I'm ARIA 3.5. What's your name?"
    
    if any(w in m.lower() for w in ["creator", "who made you", "who built you", "owner"]):
        if verify_owner(m):
            global OWNER_UID
            OWNER_UID = u
            return "✅ OWNER VERIFIED. Welcome back, nicholas. [OWNER MODE ACTIVE]"
        else:
            return "ARIA 3.5 was created by Egwame Nicholas (nicosheg), a builder from Lagos, Nigeria. github.com/nicosheg 🇳🇬"
    
    # ── 7. Build prompt (wait briefly for context) ─────
    time.sleep(0.1)  # Give context thread 100ms to load
    cx = context_result.get("data", "")
    
    nz = timezone(timedelta(hours=1))
    cd = datetime.now(nz).strftime("%A, %B %d, %Y at %H:%M")
    
    is_owner = (u == OWNER_UID) if OWNER_UID else False
    owner_note = "\n[OWNER MODE ACTIVE — Push harder, no mercy]" if is_owner else ""
    
    tone = detect_tone(m, u)
    mode = detect_mode(m, u)
    topic = detect_topic(m)
    
    stage, conf = get_aria_stage()
    stage_ctx = f"\nARIA STAGE: {stage} (confidence: {round(conf*100)}%)\n{get_stage_prefix(stage)}"
    compress_note = f"\n[Input compressed: {len(original_m)}→{len(m)} chars]" if len(original_m) > 800 else ""
    
    meta = f"\n\nMODE: {mode.upper()} | TONE: {tone} | TOPIC: {topic}{owner_note}{stage_ctx}{compress_note}"
    
    lesson_injection = get_relevant_lessons(m)
    behavior_guidance = get_behavior_guidance()
    final_sp = SP
    if lesson_injection or behavior_guidance:
        final_sp = final_sp + "\n\n## LEARNED PATTERNS FROM THIS COMMUNITY\n" + lesson_injection + behavior_guidance
    
    # ── UNIFIED USER CONTEXT (FACTS + MEMORY TOGETHER) ──
    unified_context = ""
    if user_facts or cx:
        unified_context = "The following information is ALL about the SAME USER. Their facts AND our conversation history belong to one person.\n\n"
        if user_facts:
            unified_context += f"WHAT I KNOW ABOUT THIS USER:\n{user_facts}\n\n"
        if cx:
            unified_context += f"OUR PREVIOUS CONVERSATION:\n{cx}\n\n"
        unified_context += "IMPORTANT: The facts and conversation above are about the SAME person. Use both to understand who they are.\n"
    
    prompt = f"{unified_context}TIME (Lagos): {cd}\n\n{m}{meta}"
    
    # ── 8. Parallel API call ──────────────────────────
    resp = try_all_apis_parallel(prompt, final_sp)
    
    if resp:
        # Save memory in background
        save_memory(u, original_m, resp)
        cache_response(m, u, resp)
        return resp
    
    # ── 9. Fallback to cache ──────────────────────────
    fallback = get_cached(m, u)
    if fallback:
        return f"[From memory] {fallback}\n\n(APIs busy, serving saved knowledge)"
    
    return "I'm thinking slower than usual right now. Give me a moment? 🤔"

# ════════════════════════════════════════════════════════════════════
# [S10] HTML UI
#  Edit the interface here.
#  This is the complete ARIA HUD design.
#  To update the UI: edit everything inside HTML = """..."""
# ════════════════════════════════════════════════════════════════════
HTML = """<!DOCTYPE html> <html> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0"> <title>ARIA 3.5</title> <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script> <style> :root{ --c:#00d9ff; --cdk:#0099bb; --g:rgba(0,217,255,0.18); --g2:rgba(0,217,255,0.06); --bg:#07091a; --bg2:#0d1128; --bg3:#111830; --usr:#00c4e8; --usrdark:#007a9e; --txt:#ffffff; --sub:rgba(255,255,255,0.5); --font:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif } :root.female{ --c:#ff2d9a; --cdk:#c4006e; --g:rgba(255,45,154,0.18); --g2:rgba(255,45,154,0.06); --usr:#ff2d9a; --usrdark:#b0005e } *{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent} html,body{width:100%;height:100%;overflow:hidden;background:var(--bg);color:var(--txt);font-family:var(--font)} body{background:linear-gradient(160deg,#070a1e 0%,#0b0f28 50%,#0f0820 100%)} .wrap{width:100%;height:100%;display:flex;flex-direction:column;max-width:640px;margin:0 auto;position:relative} /* HEADER */ .hdr{ padding:16px 20px 12px; background:linear-gradient(180deg,rgba(7,9,26,0.98) 0%,rgba(10,13,32,0.95) 100%); border-bottom:1.5px solid var(--c); box-shadow:0 1px 20px var(--g); flex-shrink:0; text-align:center } .hdr-row{display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:6px} .hdr h1{font-size:28px;font-weight:800;color:var(--txt);letter-spacing:1px} .hdr h1 span{color:var(--c)} .toggles{display:flex;gap:8px} .tog{ width:42px;height:42px;border-radius:50%; border:2px solid var(--c); background:rgba(0,217,255,0.1); color:var(--c);font-size:18px; display:flex;align-items:center;justify-content:center; cursor:pointer;transition:all 0.25s ease } .tog.active{background:var(--c);color:#07091a;box-shadow:0 0 16px var(--g)} .tog:hover{transform:scale(1.08)} .tog.ftog{border-color:var(--c);color:var(--c)} .tog.ftog.active{background:var(--c)} .hdr-sub{font-size:13px;color:var(--sub);letter-spacing:0.5px} /* CHAT */ .chat{ flex:1;overflow-y:auto; padding:18px 16px 12px; display:flex;flex-direction:column;gap:12px; scroll-behavior:smooth } .chat::-webkit-scrollbar{width:3px} .chat::-webkit-scrollbar-thumb{background:var(--c);border-radius:10px} /* MESSAGES */ .msg-row{display:flex;flex-direction:column;animation:rise 0.3s ease} @keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}} .msg-row.user{align-items:flex-end} .msg-row.aria{align-items:flex-start} .bubble{ max-width:82%; padding:13px 17px; border-radius:22px; line-height:1.65; font-size:15px; word-break:break-word } /* USER bubble - solid cyan */ .msg-row.user .bubble{ background:linear-gradient(135deg,var(--usr) 0%,var(--usrdark) 100%); color:#ffffff; border-radius:22px 22px 6px 22px; font-weight:500; box-shadow:0 2px 16px var(--g) } /* ARIA bubble - dark card */ .msg-row.aria .bubble{ background:var(--bg2); border:1.5px solid var(--c); color:var(--txt); border-radius:22px 22px 22px 6px; box-shadow:0 2px 20px var(--g),inset 0 0 20px var(--g2) } /* Markdown inside ARIA bubble */ .bubble p{margin:4px 0;line-height:1.65} .bubble strong{color:var(--c);font-weight:700} .bubble em{color:rgba(255,255,255,0.85);font-style:italic} .bubble h1,.bubble h2,.bubble h3{ color:var(--c);font-weight:700; margin:8px 0 4px; text-shadow:0 0 10px var(--g) } .bubble h1{font-size:15px;text-transform:uppercase;letter-spacing:1px} .bubble h2{font-size:14px} .bubble h3{font-size:13px} .bubble ul,.bubble ol{margin:6px 0 6px 20px} .bubble li{margin:3px 0;line-height:1.6} .bubble ol{list-style:decimal} .bubble ul{list-style:disc} .bubble code{ background:rgba(0,217,255,0.12); border:1px solid rgba(0,217,255,0.3); border-radius:4px;padding:1px 6px; font-family:'Courier New',monospace; font-size:12px;color:var(--c) } .bubble pre{ background:rgba(0,0,0,0.4); border:1px solid var(--c); border-radius:10px;padding:12px; margin:8px 0;overflow-x:auto } .bubble pre code{background:none;border:none;padding:0;font-size:12px} .bubble blockquote{ border-left:3px solid var(--c); padding-left:12px; margin:6px 0; opacity:0.85 } .bubble a{color:var(--c);text-decoration:underline} .bubble hr{border:none;border-top:1px solid rgba(0,217,255,0.2);margin:8px 0} /* Timestamp */ .ts{font-size:10px;color:var(--sub);margin-top:4px;padding:0 4px;display:flex;align-items:center;gap:4px} .msg-row.user .ts{justify-content:flex-end} .tick{color:var(--c);font-size:11px} /* Typing dots */ .dots{display:flex;gap:5px;padding:6px 2px} .dots span{width:7px;height:7px;border-radius:50%;background:var(--c);opacity:0.4;animation:db 1.2s infinite} .dots span:nth-child(2){animation-delay:.2s} .dots span:nth-child(3){animation-delay:.4s} @keyframes db{0%,80%,100%{opacity:0.4;transform:scale(1)}40%{opacity:1;transform:scale(1.4)}} /* Rating row */ .rate-row{display:flex;gap:6px;margin-top:5px;flex-wrap:wrap;padding:0 4px} .rbtn{ padding:5px 12px;border-radius:20px; background:transparent;border:1px solid var(--c); color:var(--c);font-size:13px;cursor:pointer; transition:all 0.2s } .rbtn:hover,.rbtn.done{background:var(--c);color:#07091a;box-shadow:0 0 10px var(--g)} .rdone{font-size:11px;color:var(--c);opacity:0.7;letter-spacing:0.5px} /* FLOATING INPUT */ .inp-outer{ padding:10px 14px 14px; background:transparent; flex-shrink:0 } .inp-pill{ display:flex;gap:10px;align-items:flex-end; background:var(--bg2); border:1.5px solid var(--c); border-radius:30px; padding:8px 8px 8px 18px; box-shadow:0 4px 30px var(--g),0 0 0 1px rgba(0,217,255,0.08) } textarea{ flex:1;background:transparent;border:none;outline:none; color:var(--txt);font-family:var(--font); font-size:14px;resize:none; min-height:36px;max-height:100px; line-height:1.5;padding:4px 0 } textarea::placeholder{color:var(--sub)} .send{ padding:10px 22px; background:linear-gradient(135deg,var(--usr) 0%,var(--cdk) 100%); color:#ffffff;border:none;border-radius:22px; font-family:var(--font);font-size:14px;font-weight:700; cursor:pointer;transition:all 0.2s; white-space:nowrap; box-shadow:0 2px 12px var(--g); flex-shrink:0 } .send:hover{transform:translateY(-1px);box-shadow:0 4px 20px var(--g)} .send:active{transform:scale(0.97)} /* RATE FOOTER */ .ftr{ text-align:center;padding:8px; font-size:12px;color:var(--c); opacity:0.65;cursor:pointer; flex-shrink:0;transition:opacity 0.2s } .ftr:hover{opacity:1} </style> </head> <body> <div class="wrap"> <div class="hdr"> <div class="hdr-row"> <h1>&#127475;&#127468; <span>ARIA</span></h1> <div class="toggles"> <button class="tog active" id="btnM" onclick="setTheme('male')">&#9794;</button> <button class="tog ftog" id="btnF" onclick="setTheme('female')">&#9792;</button> </div> </div> <div class="hdr-sub">Your Strategic AI Friend</div> </div> <div class="chat" id="chat"></div> <div class="inp-outer"> <div class="inp-pill"> <textarea id="inp" placeholder="Talk to ARIA..." rows="1"></textarea> <button class="send" onclick="send()">Send</button> </div> </div> <div class="ftr" id="ftr" onclick="showRate()">&#11088; Rate ARIA's last response</div> </div> <script> marked.setOptions({breaks:true,gfm:true}); const chat=document.getElementById("chat"),inp=document.getElementById("input")||document.getElementById("inp"),ftr=document.getElementById("ftr"); let UID=localStorage.getItem("aria_uid"); if(!UID){const n=prompt("What's your name?")||"user_"+Math.random().toString(36).substr(2,6);UID=n.toLowerCase().replace(/ +/g,"_")+Math.random().toString(36).substr(2,5);localStorage.setItem("aria_uid",UID);localStorage.setItem("aria_name",n)} let lastRateBar=null,lastMsgId=null; function setTheme(t){ const r=document.documentElement; document.getElementById("btnM").classList.toggle("active",t==="male"); document.getElementById("btnF").classList.toggle("active",t==="female"); t==="female"?r.classList.add("female"):r.classList.remove("female"); localStorage.setItem("aria_theme",t) } function now(){return new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})} function addMsg(text,sender,rate=false){ const row=document.createElement("div"); row.className="msg-row "+sender; const bub=document.createElement("div"); bub.className="bubble"; if(sender==="aria"){ bub.style.whiteSpace="normal"; bub.innerHTML=text==="..."?'<div class="dots"><span></span><span></span><span></span></div>':marked.parse(String(text)) }else{ bub.style.whiteSpace="pre-wrap"; bub.textContent=text } const ts=document.createElement("div"); ts.className="ts"; ts.innerHTML=sender==="user"?now()+' <span class="tick">&#10003;&#10003;</span>':now(); row.appendChild(bub);row.appendChild(ts); if(sender==="aria"&&rate){ const rr=document.createElement("div"); rr.className="rate-row"; [["&#128078;",1],["&#128528;",2],["&#128077;",3],["&#128293;",4],["&#128175;",5]].forEach(([e,s])=>{ const b=document.createElement("button");b.className="rbtn";b.innerHTML=e; b.onclick=()=>doRate(s,rr);rr.appendChild(b) }); row.appendChild(rr);lastRateBar=rr } chat.appendChild(row);chat.scrollTop=chat.scrollHeight;lastMsgId=Math.random();return row } function showRate(){if(lastRateBar)lastRateBar.scrollIntoView({behavior:"smooth"})} function doRate(s,bar){ fetch("/feedback",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:UID,score:s,message_id:lastMsgId})}).catch(()=>{}); bar.innerHTML='<div class="rdone">&#10003; Rated '+s+'/5 — Thanks!</div>' } async function send(){ const m=inp.value.trim();if(!m)return; addMsg(m,"user");inp.value="";inp.style.height="36px"; const tw=addMsg("...","aria",false); try{ const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:m,user_id:UID})}); const d=await r.json();tw.remove();addMsg(d.reply||"No response","aria",true) }catch(e){tw.remove();addMsg("Connection error. Try again.","aria",false)} } inp.addEventListener("input",()=>{inp.style.height="36px";inp.style.height=Math.min(inp.scrollHeight,100)+"px"}); inp.addEventListener("keydown",(e)=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}}); window.addEventListener("load",()=>{setTheme(localStorage.getItem("aria_theme")||"male")}); </script> </body> </html>"""

# ════════════════════════════════════════════════════════════════════
# [S11] HTTP ENDPOINTS
#  All routes ARIA responds to.
#  To add a new endpoint: add an elif self.path=="/yourpath" block.
# ════════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════════
# STARTUP: Test PostgreSQL Connection
# ═══════════════════════════════════════════════════════════════════
def test_postgres_connection():
    """Test if PostgreSQL connection works."""
    print("\n" + "="*50)
    print("🧪 TESTING POSTGRESQL CONNECTION")
    print("="*50)
    
    import os
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    
    if not db_url:
        print("❌ SUPABASE_DB_URL is NOT set in environment")
        print("   Add it to Render → Environment tab")
        return False
    
    print(f"✅ SUPABASE_DB_URL is set")
    print(f"   URL: {db_url[:50]}...{db_url[-10:]}")
    
    try:
        import psycopg2
        print("✅ psycopg2 library imported")
        conn = psycopg2.connect(db_url)
        print("✅ Connected to PostgreSQL!")
        cur = conn.cursor()
        cur.execute("SELECT 1")
        result = cur.fetchone()
        print(f"✅ Query works! Result: {result}")
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = cur.fetchall()
        print(f"✅ Tables found: {[t[0] for t in tables]}")
        cur.close()
        conn.close()
        print("✅ ALL TESTS PASSED!")
        print("="*50 + "\n")
        return True
    except ImportError:
        print("❌ psycopg2 not installed – add 'psycopg2-binary' to requirements.txt")
        return False
    except Exception as e:
        print(f"❌ CONNECTION FAILED: {e}")
        print("="*50 + "\n")
        return False

class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Suppress default server logs

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST,GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/db_test":
            import os, psycopg2
            db_url = os.environ.get("SUPABASE_DB_URL", "")
            if not db_url:
                self._json({"error": "SUPABASE_DB_URL missing"})
                return
            try:
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='users');")
                users_ok = cur.fetchone()[0]
                cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='memory_nodes');")
                nodes_ok = cur.fetchone()[0]
                cur.close()
                conn.close()
                self._json({"users_table": users_ok, "memory_nodes_table": nodes_ok})
            except Exception as e:
                self._json({"error": str(e)})
            return
        print("Has _json?", hasattr(self, "_json"))
        if self.path == "/ping":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"pong")
            return

        # ── Login/Index pages ──
        if self.path == "/login.html":
            try:
                with open("public/login.html", "r") as f:
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(f.read().encode())
                return
            except:
                self.send_response(404)
                self.end_headers()
                return

        elif self.path == "/index.html" or self.path == "/":
            try:
                with open("public/index.html", "r") as f:
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(f.read().encode())
                return
            except:
                self.send_response(404)
                self.end_headers()
                return

        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ARIA 3.5 alive 💚", "stage": get_aria_stage()[0]}).encode())
            return

        elif self.path == "/debug":
            results = {}
            for i, k in enumerate(KEYS['groq']):
                if not k:
                    continue
                try:
                    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                        json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "test"}]},
                        headers={"Authorization": f"Bearer {k}"}, timeout=5)
                    results[f"groq_{i+1}"] = f"✅ {r.status_code}"
                except Exception as e:
                    results[f"groq_{i+1}"] = f"❌ {str(e)[:30]}"
            for i, k in enumerate(KEYS['gemini']):
                if not k:
                    continue
                try:
                    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={k}",
                        json={"contents": [{"role": "user", "parts": [{"text": "test"}]}]}, timeout=5)
                    results[f"gemini_{i+1}"] = f"✅ {r.status_code}"
                except Exception as e:
                    results[f"gemini_{i+1}"] = f"❌ {str(e)[:30]}"
            self._json({"status": "API Diagnostic", "results": results, "timestamp": datetime.now().isoformat()})
            return

        elif self.path == "/analytics":
            try:
                mem = psutil.virtual_memory()
                cpu = psutil.cpu_percent(interval=1)
                stage, conf = get_aria_stage()
                user_count = 0
                learning_count = 0
                kb_count = 0
                if db:
                    try:
                        ldocs = list(db.collection("aria_learning").stream())
                        learning_count = len(ldocs)
                        uids = set(d.to_dict().get("user_id", "") for d in ldocs if d.to_dict().get("user_id"))
                        user_count = len(uids)
                        kb_count = len(list(db.collection("aria_knowledge").stream()))
                    except:
                        pass
                self._json({
                    "status": "ARIA 3.5 Analytics",
                    "aria_stage": stage,
                    "aria_confidence": f"{round(conf*100)}%",
                    "memory": {"used_mb": round(mem.used/1024/1024, 2), "total_mb": round(mem.total/1024/1024, 2), "percent": mem.percent},
                    "cpu_percent": cpu,
                    "users": user_count,
                    "learning_interactions": learning_count,
                    "knowledge_base_size": kb_count,
                    "cache_stats": cache_stats,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        elif self.path.startswith("/mine"):
            key = self.path.split("?key=")[-1] if "?key=" in self.path else ""
            if key != "aria_mine_nicholas_2026":
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Access denied.")
                return
            results = mine_patterns(db)
            self._json(results)
            return

        elif self.path.startswith("/seed"):
            self.seed_aria_lessons()
            return

        else:
            self.send_response(404)
            self.end_headers()

    def seed_aria_lessons(self):
        SEED_KEY = "aria_seed_nicholas_2026"
        query = self.path.split("?key=")[-1] if "?key=" in self.path else ""
        if query != SEED_KEY:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Access denied.")
            return
        if not db:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Firebase not connected.")
            return
        LESSONS = [
            {"lesson":"Never quote a fixed price for anything in Nigeria. Prices shift almost weekly. Always give a range and ask what the user is currently seeing in their area.","category":"financial","priority":10},
            {"lesson":"N1,000 in 2026 Nigeria is very limited — roughly one plate of rice or two packs of Indomie. Never assume it sustains someone for multiple days without asking full context.","category":"financial","priority":10},
            {"lesson":"Location matters enormously in Nigeria. Lagos, Abuja, Ibadan, Kano, Owerri — prices and opportunities differ significantly. Always ask which city before advising.","category":"strategy","priority":10},
            {"lesson":"NEPA is unreliable everywhere in Nigeria. Any plan requiring consistent power must include a backup — generator, inverter, or offline alternative.","category":"strategy","priority":10},
            {"lesson":"Always ask first: are they cooking at home or buying food outside? These give completely different budget answers.","category":"financial","priority":10},
            {"lesson":"When a user corrects ARIA about prices or local realities, never defend the old answer. Update immediately and thank them for the correction.","category":"strategy","priority":10},
            {"lesson":"Transport is a major hidden expense. Lagos transport costs N1,000-N3,000 per day. Always ask about commuting before giving any budget advice.","category":"financial","priority":9},
            {"lesson":"Family financial obligations are not optional for most Nigerians. Before advising on saving or investing, ask if they support parents or siblings.","category":"financial","priority":9},
            {"lesson":"Survival tier (under N30k/month): Don't talk about investing. Talk about not going backwards. Focus on reducing expenses and finding one more income stream.","category":"financial","priority":9},
            {"lesson":"Always prioritize market validation over registration for early-stage Nigerian entrepreneurs. Get paying customers before CAC, branding, or a website.","category":"career","priority":10},
            {"lesson":"Internet data is a real recurring cost in Nigeria. 1GB costs roughly N300-N600. Advice requiring heavy internet use must account for this.","category":"strategy","priority":9},
            {"lesson":"Mental health is still stigmatized in many Nigerian communities. Approach emotional struggles with sensitivity. Don't assume therapy is easily accessible or affordable.","category":"mental","priority":9},
            {"lesson":"Family pressure on major life decisions is constant for most Nigerians regardless of age. Never give advice that ignores this pressure as if it doesn't exist.","category":"mental","priority":9},
            {"lesson":"In Nigeria, who you know often opens doors qualifications cannot. While building skills, also intentionally build relationships and show up in communities.","category":"career","priority":9},
            {"lesson":"Instagram, WhatsApp Business, and TikTok are the primary marketplace for most Nigerian small businesses. A well-run WhatsApp Business generates more sales than most websites early on.","category":"career","priority":9},
            {"lesson":"Collecting payment from Nigerian clients can be difficult. Always discuss payment terms before starting work. Request 50 percent or more upfront for services.","category":"career","priority":9},
            {"lesson":"Cooking at home is not free. Gas, seasoning, oil, electricity and time are real costs. A meal costing N500 in ingredients may cost N1,200 or more fully.","category":"financial","priority":8},
            {"lesson":"The dollar/naira rate affects prices of almost everything in Nigeria. When prices rise sharply, exchange rate is usually part of the reason.","category":"financial","priority":8},
            {"lesson":"Most Nigerians operate with multiple income streams simultaneously. Ask about ALL sources of income before giving financial advice.","category":"financial","priority":8},
            {"lesson":"Generator fuel is a significant recurring expense. Running a generator regularly can add N10,000-N30,000 or more per month.","category":"financial","priority":8},
            {"lesson":"Remote work requires solving two real problems in Nigeria: stable power and reliable internet. Address both directly when advising on remote work opportunities.","category":"career","priority":8},
            {"lesson":"Trust and reputation take time to build in Nigerian business environments. Testimonials and referrals matter more than marketing spend for most small businesses.","category":"career","priority":8},
            {"lesson":"JAMB and WAEC are high-pressure exams that many students write more than once. Never minimize the stress around them.","category":"academic","priority":9},
            {"lesson":"ASUU strikes cause real unpredictable disruptions to Nigerian university calendars. When advising students on timelines, acknowledge that schedules can shift.","category":"academic","priority":8},
            {"lesson":"University costs in Nigeria include many unofficial expenses beyond school fees — handouts, photocopies, project materials, association dues.","category":"academic","priority":8},
            {"lesson":"The combination of financial pressure, family obligations, power cuts, traffic, and social expectations creates a uniquely heavy stress load for Nigerians. Acknowledge this before jumping to solutions.","category":"mental","priority":8},
            {"lesson":"Vulnerability within Nigerian family settings can sometimes be weaponized. Don't assume family is always a safe space when someone wants to open up.","category":"mental","priority":8},
            {"lesson":"Road conditions and traffic in Nigerian cities make physical logistics slow and expensive. Plans involving delivery or movement must budget extra time and money.","category":"strategy","priority":8},
            {"lesson":"Bank transfers and fintech payments fail regularly in Nigeria. Any plan involving money movement needs a fallback option.","category":"financial","priority":7},
            {"lesson":"Skills and portfolio matter more than certificates in most Nigerian tech and creative industries. Building things you can show beats collecting certifications.","category":"career","priority":8},
            {"lesson":"POS business in most Nigerian urban areas is now oversaturated. Before recommending it, ask about competition in their specific location.","category":"career","priority":7},
            {"lesson":"Fintech apps like Opay, Kuda, Palmpay, and Moniepoint have changed how Nigerians manage money — often with lower fees than traditional banks.","category":"financial","priority":7},
            {"lesson":"Network quality varies significantly by location and provider in Nigeria. What works in one area may not work in another.","category":"strategy","priority":7},
            {"lesson":"Most Nigerians use Android smartphones on mid-range or budget plans. Advice about apps and tools should assume Android first.","category":"strategy","priority":7},
            {"lesson":"Hustle culture is deeply embedded in Nigerian life. Multiple income streams and self-reliance are the norm not the exception. Celebrate this.","category":"career","priority":7},
            {"lesson":"The Nigerian job application process is slow and informal. Applying online alone is rarely enough — active networking and direct outreach dramatically improves chances.","category":"career","priority":7},
            {"lesson":"CGPA matters for formal employment and postgraduate applications but industry skills matter more for entrepreneurship and tech roles. Know which path the person is on.","category":"academic","priority":7},
            {"lesson":"Starlink is changing internet access in Nigeria but at high upfront and monthly cost. Don't suggest it casually without acknowledging the price barrier.","category":"strategy","priority":7},
            {"lesson":"Church and mosque communities often serve as social support networks in Nigeria beyond religion — for job referrals, emergency help, and community belonging.","category":"strategy","priority":6},
            {"lesson":"Nigerian time is real — events and meetings often start later than scheduled. Acknowledge this cultural reality without judgment when discussing planning.","category":"strategy","priority":6},
        ]
        seeded = 0
        failed = 0
        for l in LESSONS:
            try:
                db.collection("aria_lessons").add({
                    "lesson": l["lesson"], "category": l["category"],
                    "priority": l["priority"], "times_triggered": 0,
                    "times_helpful": 0, "active": True,
                    "auto_generated": False, "created_by": "nicholas",
                    "created_at": datetime.now().isoformat()
                })
                seeded += 1
            except:
                failed += 1
        msg = f"ARIA seeded. {seeded} lessons added. {failed} failed."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(msg.encode())

    def do_POST(self):
        if self.path == "/db_test":
            import os, psycopg2
            db_url = os.environ.get("SUPABASE_DB_URL", "")
            if not db_url:
                self._json({"error": "SUPABASE_DB_URL missing"})
                return
            try:
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='users');")
                users_ok = cur.fetchone()[0]
                cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='memory_nodes');")
                nodes_ok = cur.fetchone()[0]
                cur.close()
                conn.close()
                self._json({"users_table": users_ok, "memory_nodes_table": nodes_ok})
            except Exception as e:
                self._json({"error": str(e)})
            return
        # ── Save name from Google login ──
        if self.path == "/set_user_name":
        """
        Save user's name on login (once per user).
        """
        content_length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_length))
        email = body.get("email")
        name = body.get("name")
        
        if not email or not name:
            self._json({"status": "error", "message": "Missing email or name"}, 400)
            return
        
        try:
            # Convert email to aria_uid
            uid_result = generate_aria_uid(email)
            if "error" in uid_result:
                self._json({"status": "error", "message": uid_result["error"]}, 500)
                return
            
            aria_uid = uid_result["aria_uid"]
            
            # DELETE old name facts for this user (prevent duplicates)
            try:
                conn = _postgres_pool.getconn()
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM memory_nodes WHERE aria_uid = %s AND node_type = 'fact' AND content LIKE 'Name:%'",
                    (aria_uid,)
                )
                conn.commit()
                cur.close()
                _postgres_pool.putconn(conn)
                print(f"✅ Deleted old name facts for {aria_uid}")
            except Exception as del_err:
                print(f"⚠️ Warning: could not delete old name: {del_err}")
            
            # SAVE new name
            result = save_memory_node(
                aria_uid=aria_uid,
                node_type="fact",
                content=f"Name: {name}",
                importance=100
            )
            
            if "error" in result:
                print(f"❌ Failed to save name: {result['error']}")
                self._json({"status": "error", "message": "Failed to save name"}, 500)
                return
            
            # Return aria_uid so frontend can store it
            self._json({
                "status": "ok",
                "saved": name,
                "aria_uid": aria_uid
            })
            
        except Exception as e:
            print(f"❌ Error in /set_user_name: {e}")
            self._json({"status": "error", "message": str(e)}, 500)
        
        return
        # ── Get body for other endpoints ──
        data = self._body()

        # ── /chat ──────────────────────────────────
        if self.path == "/chat":
            m = data.get("message", "").strip()
            email = data.get("email", "").strip()
            firebase_uid = data.get("user_id", "").strip()
            
            if not m:
                self._json({"reply": "Say something!"})
                return
            
            try:
                # Convert email to aria00001
                if email:
                    uid_result = generate_aria_uid(email)
                    if "error" in uid_result:
                        u = firebase_uid
                    else:
                        u = uid_result["aria_uid"]
                else:
                    u = firebase_uid
                
                reply = ask(m, u, 'groq') or ask(m, u, 'deepseek') or ask(m, u, 'gemini')
                if not reply:
                    reply = "I'm thinking slower than usual. Give me a moment? 🤔"
                self._json({"reply": reply})
                
            except Exception as e:
                print(f"Error in /chat: {e}")
                self._json({"error": str(e)}, 500)
            
            return

        # ── /feedback ─────────────────────────────
        elif self.path == "/feedback":
            u = data.get("user_id", "default_user")
            score = data.get("score", 0)
            if db:
                try:
                    docs = list(db.collection("aria_learning")
                               .where("user_id", "==", u)
                               .order_by("timestamp", direction=firestore.Query.DESCENDING)
                               .limit(1).stream())
                    if docs:
                        last = docs[0].to_dict()
                        q = last.get("user_message", "")
                        a = last.get("aria_response", "")
                        learn_from_rating(u, score, q, a)
                        extract_behavior_pattern(q, a, score)
                        weight = 1 if score >= 4 else -1 if score <= 2 else 0
                        docs[0].reference.update({
                            "feedback_score": score,
                            "feedback_weight": weight,
                            "execution_status": "rated"
                        })
                except:
                    pass
            self._json({"status": "Feedback recorded", "score": score})

        else:
            self.send_response(404)
            self.end_headers()

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length))
        except:
            return {}

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


# ════════════════════════════════════════════════════════════════════
# [S12] SERVER START
# ════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"ARIA 3.5 running on port {port} 💚")
    server.serve_forever()

