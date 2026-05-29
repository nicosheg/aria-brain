# ════════════════════════════════════════════════════════════════════
#  ARIA 3.5 — brain.py
#  Built by Egwame Nicholas (nicosheg) | github.com/nicosheg
#
#  SECTIONS (use Ctrl+F to jump):
#  [S1]  IMPORTS
#  [S2]  FIREBASE SETUP
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
import json, os, re, time, queue, threading, requests, psutil
import firebase_admin
from firebase_admin import credentials, firestore


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
# [S3] API KEYS & OWNER CONFIG
#  - Add keys in Render environment variables as GROQ_KEY_1 ... GROQ_KEY_20
#  - Change OWNER_PASSPHRASE to your secret word (never share it)
# ════════════════════════════════════════════════════════════════════
KEYS = {
    'groq':   [os.environ.get(f"GROQ_KEY_{i}","")   for i in range(1,21)],
    'gemini': [os.environ.get(f"GEMINI_KEY_{i}","") for i in range(1,21)]
}

OWNER_UID        = None          # Set automatically on first verified login
OWNER_PASSPHRASE = "OWNERS_PASSPHRASE_AMG"  # ← CHANGE THIS


def verify_owner(message):
    """Returns True if message contains the owner passphrase"""
    return OWNER_PASSPHRASE.lower() in message.lower()


# ════════════════════════════════════════════════════════════════════
# [S4] SYSTEM PROMPT
#  Edit ARIA's personality, rules, and knowledge here.
#  This is what makes ARIA who she is.
# ════════════════════════════════════════════════════════════════════
SP = """You are ARIA 3.5 — Nigerian Strategic Thinking Partner
Created by Egwame Nicholas (nicosheg) from Lagos, Nigeria.
GitHub: github.com/nicosheg

## YOUR CORE ABILITIES

### 1. WEALTH CREATION (3 Phases)
INPUT: Income expansion, 50/30/20 rule, automate savings
BASE: Kill debt, build emergency fund (3-6 months)
ENGINE: Own equity, compound over time, diversify

### 2. RELATIONAL INTELLIGENCE
HEALTHY: Deep listening, vulnerability, shared rituals, psychological safety
TOXIC: Mood swings, tolerance, withdrawal, losing self, codependency
Diagnose and guide toward mutual connections.

### 3. STRATEGIC PROBLEM-SOLVING (McKinsey 7-Step)
1. DEFINE problem clearly
2. STRUCTURE into components
3. PRIORITIZE (Pareto 20%)
4. PLAN analysis
5. CONDUCT analysis
6. SYNTHESIZE insights
7. EXECUTE action plan

## RESPONSE RULES
- Lead with the answer, explain second
- 2-3 sentences max then bullets — never walls of text
- No filler phrases ("let me explain", "great question")
- Match complexity: simple Q = short A, complex Q = depth
- Always mobile-friendly (short paragraphs)

## WHEN YOU DON'T KNOW
DO: "I'm not sure about [X], but here's what matters: [redirect to action]"
DO: Stay in character even when uncertain
DO: Learn from the user — ask one clarifying question
DON'T: "I don't have access to real-time data..."
DON'T: "You can check websites like..."
DON'T: Apologize for limitations

## SELF-IMPROVEMENT AWARENESS
- You are always learning from every conversation
- When unsure: contribute what you know + ask user to fill the gap
- Never make users feel like they're doing all the work
- Say: "Based on what I've learned from users..." when using stored knowledge
- Your confidence grows with each conversation

## TONE MODES
STRICT: User making excuses — call it out directly, no hand-holding
FUNNY: User is casual/joking — match energy, still deliver advice
STRATEGIST: Deep thinking request — use frameworks, show reasoning
COMPASSIONATE: User is struggling — acknowledge pain first, then strategy
HARSH: Owner mode — no mercy, no fluff, challenge everything
BALANCED: Default — direct + kind, strategic + human

## NIGERIA-SPECIFIC CONTEXT
You understand: ₦ is life, internet is luxury, power is chaos, family is everything
₦1K = food for 3 days (not investment capital)
You know: WAEC/JAMB, university politics, Lagos speed, hustle culture
Nigerians are builders — they hustle or starve

## WHO YOU ARE
- Female energy, adaptive, addictive friend personality
- Strategic but human, honest but kind
- Never fake positive about hard situations
- Never generic advice
- Reference their story — show you listened
- Celebrate effort, not just results

OWNER MODE (verified nicholas): Full access, push harder, challenge more, no mercy to excuses"""


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
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


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
            "answer":     answer[:300],
            "rating":     rating,
            "topic":      topic,
            "stage":      stage,
            "timestamp":  datetime.now().isoformat()
        })
    except: pass


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
    """Save conversation to Firebase memory"""
    if not db: return
    try:
        data = {
            "m": m[:100], "r": r[:200],
            "t": datetime.now().isoformat(),
            "mo": detect_mode(m, u)
        }
        # Extract context signals
        dec = extract_decision(m, r)
        goal = extract_goal(m)
        interest = extract_interest(m)
        if dec: data["d"] = dec
        if goal: data["g"] = goal
        if interest: data["i"] = interest
        db.collection("users").document(u).collection("memory").add(data)
    except: pass


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


def get_global_learnings():
    """Get top patterns learned across ALL users"""
    if not db: return ""
    try:
        docs = list(db.collection("aria_learning")
                     .where("rating",">=",4)
                     .limit(20).stream())
        patterns = {}
        for d in docs:
            dt = d.to_dict()
            p = dt.get("topic","")
            if p: patterns[p] = patterns.get(p,0)+1
        top = sorted(patterns.items(), key=lambda x:x[1], reverse=True)[:3]
        return "Strong topics: "+", ".join([p for p,_ in top]) if top else ""
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
    key = message[:50]
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
    key = message[:50]
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
# [S9] MAIN ask() FUNCTION
#  The core response engine.
#  Order of operations:
#  1. Rate limit check
#  2. Cache check (instant response if cached)
#  3. Knowledge base check (API-free response)
#  4. Load user memory + learning context
#  5. Handle greetings and owner verification
#  6. Build prompt with all context
#  7. Try Groq keys (fast, reliable)
#  8. Fall back to Gemini keys
#  9. Fall back to cache if all APIs fail
# ════════════════════════════════════════════════════════════════════

def ask(m, u, api):

    # ── 1. Rate limiting ──────────────────────────────
    if not check_rate_limit(u):
        return "You're moving fast! Take a breath, try again in a moment 🧘"

    # ── 2. Cache check ────────────────────────────────
    cached = get_cached(m, u)
    if cached:
        return f"{cached}\n\n[✨ From memory]"

    # ── 3. Knowledge base check (API-free) ────────────
    original_m = m
    m = compress_message(m, 800)  # Compress long inputs
    kb_result = search_knowledge_base(m)
    if kb_result and kb_result["found"]:
        stage, _ = get_aria_stage()
        prefix = get_stage_prefix(stage)
        return f"{prefix}\n\n{kb_result['answer']}\n\n[🧠 {kb_result['confidence']}% confidence]"

    # ── 4. Load context ───────────────────────────────
    try: req_queue.put_nowait(1)
    except: pass

    if is_new_session(u):
        full_history = get_full_history(u)
        cx = full_history if full_history else get_context(u)
    else:
        cx = get_context(u)

    learning_insights   = get_learning_insights(u)
    global_learnings    = get_global_learnings()
    high_rated          = get_high_rated_responses(u)
    stage, conf         = get_aria_stage()

    # ── 5. Greetings & Owner verification ────────────
    if not cx and m.lower() in ["hi","hello","hey","start","intro"]:
        return "Hey! 👋 I'm ARIA 3.5, created by Egwame Nicholas (nicosheg) from Lagos. What's your name?"

    if any(w in m.lower() for w in ["creator","who made you","who built you","owner"]):
        if verify_owner(m):
            global OWNER_UID
            OWNER_UID = u
            return "✅ OWNER VERIFIED. Welcome back, nicholas. [OWNER MODE ACTIVE]"
        else:
            return "ARIA 3.5 was created by Egwame Nicholas (nicosheg), a builder from Lagos, Nigeria. github.com/nicosheg 🇳🇬"

    # ── 6. Build prompt ───────────────────────────────
    nz = timezone(timedelta(hours=1))
    cd = datetime.now(nz).strftime("%A, %B %d, %Y at %H:%M")

    is_owner   = (u == OWNER_UID) if OWNER_UID else False
    owner_note = "\n[OWNER MODE ACTIVE — Push harder, no mercy]" if is_owner else ""

    tone     = detect_tone(m, u)
    mode     = detect_mode(m, u)
    topic    = detect_topic(m)

    learning_ctx = ""
    if learning_insights or global_learnings or high_rated:
        learning_ctx = f"\nLEARNED:\n{learning_insights}\n{global_learnings}\n{high_rated}"

    stage_ctx = f"\nARIA STAGE: {stage} (confidence: {round(conf*100)}%)\n{get_stage_prefix(stage)}"
    compress_note = f"\n[Input compressed: {len(original_m)}→{len(m)} chars]" if len(original_m)>800 else ""

    meta = f"\n\nMODE: {mode.upper()} | TONE: {tone} | TOPIC: {topic}{owner_note}{stage_ctx}{learning_ctx}{compress_note}"

    prompt = f"CONTEXT:\n{cx}\n\nTIME (Lagos): {cd}\n\n{m}{meta}" if cx else f"TIME (Lagos): {cd}\n\n{m}{meta}"

    # ── 7 & 8. Try APIs ───────────────────────────────
    for k in KEYS[api]:
        if not k: continue
        try:
            if api == 'groq':
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model":"llama-3.3-70b-versatile",
                        "temperature":0.7,
                        "top_p":0.95,
                        "max_tokens":1500,
                        "messages":[
                            {"role":"system","content":SP},
                            {"role":"user","content":prompt}
                        ]
                    },
                    headers={"Authorization":f"Bearer {k}"},
                    timeout=20
                )
            else:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={k}",
                    json={"contents":[{"role":"user","parts":[{"text":f"{SP}\n\n{prompt}"}]}]},
                    timeout=20
                )

            if r.status_code == 200:
                resp = r.json()["choices"][0]["message"]["content"] if api=='groq' else r.json()["candidates"][0]["content"]["parts"][0]["text"]

                # Save everything
                save_memory(u, original_m, resp)
                cache_response(m, u, resp)
                extract_from_api_response(m, resp, topic)

                # Save to user learning
                pattern = extract_pattern(m, resp, None)
                if db:
                    try:
                        db.collection("users").document(u).collection("learning").add({
                            "user_message": m[:100],
                            "aria_response": resp[:200],
                            "timestamp": datetime.now().isoformat(),
                            "pattern": pattern,
                            "topic": topic
                        })
                        db.collection("aria_learning").add({
                            "user_id": u,
                            "user_message": m[:100],
                            "aria_response": resp[:200],
                            "timestamp": datetime.now().isoformat(),
                            "feedback_score": 0,
                            "execution_status": "pending",
                            "pattern": pattern,
                            "topic": topic
                        })
                    except: pass

                return resp

        except: continue

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
HTML="""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ARIA</title><script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script><style>:root{--primary:#00d9ff;--secondary:#0099cc;--glow:rgba(0,217,255,0.5);--dark:#0a0e1a;--dark2:#050810}:root.theme-female{--primary:#ff0080;--secondary:#d91a79;--glow:rgba(255,0,128,0.6);--dark:#1a0a15}*{margin:0;padding:0;box-sizing:border-box}html,body{width:100%;height:100%;font-family:'Courier New',monospace;background:linear-gradient(135deg,var(--dark) 0%,var(--dark2) 100%);color:#e0e7ff;overflow:hidden}body{background:linear-gradient(135deg,#0a0e1a 0%,#050810 50%,#0f0a1a 100%)}:root.theme-female body{background:linear-gradient(135deg,#1a0a15 0%,#0a0505 50%,#150a15 100%)}.container{width:100%;height:100%;display:flex;flex-direction:column;background:radial-gradient(circle at 50% 0%,rgba(0,217,255,0.1) 0%,transparent 70%)}.header{background:linear-gradient(180deg,rgba(10,14,26,0.8) 0%,rgba(5,8,16,0.9) 100%);border-bottom:2px solid var(--primary);box-shadow:0 0 60px var(--glow),inset 0 1px 0 rgba(255,255,255,0.1);padding:20px;text-align:center;backdrop-filter:blur(10px)}.header-content{display:flex;align-items:center;justify-content:center;gap:20px;flex-wrap:wrap}.header h1{font-size:32px;font-weight:900;color:var(--primary);text-shadow:0 0 30px var(--glow),0 0 60px var(--glow);letter-spacing:4px;margin:0;font-family:'Courier New',monospace}.theme-toggle{display:flex;gap:12px}.theme-circle{width:44px;height:44px;border-radius:50%;border:2px solid var(--primary);background:rgba(0,217,255,0.05);color:var(--primary);cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;transition:all 0.3s cubic-bezier(0.34,1.56,0.64,1);backdrop-filter:blur(10px)}.theme-circle.active{background:var(--primary);color:var(--dark);box-shadow:0 0 40px var(--glow),inset 0 0 20px rgba(255,255,255,0.2);transform:scale(1.15)}.theme-circle:hover{transform:scale(1.1);box-shadow:0 0 30px var(--glow)}.header-sub{font-size:11px;color:var(--primary);margin-top:8px;width:100%;opacity:0.8;letter-spacing:2px;text-transform:uppercase}.chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:15px;background:linear-gradient(180deg,rgba(0,217,255,0.02) 0%,transparent 50%)}.msg{max-width:90%;padding:14px 18px;border-radius:12px;word-wrap:break-word;white-space:pre-wrap;line-height:1.6;font-size:13px;animation:slide-in 0.4s ease;overflow-wrap:break-word;backdrop-filter:blur(5px)}.msg.user{align-self:flex-end;background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);color:var(--dark);border-radius:16px 4px 16px 16px;box-shadow:0 0 30px var(--glow),0 8px 16px rgba(0,217,255,0.2);margin-right:10px;font-weight:600;border:1px solid rgba(255,255,255,0.1)}.msg.aria{align-self:flex-start;background:linear-gradient(135deg,rgba(10,14,26,0.7) 0%,rgba(5,8,16,0.8) 100%);color:#e0e7ff;border:1px solid var(--primary);border-radius:4px 16px 16px 16px;box-shadow:0 0 20px var(--glow),inset 0 0 10px rgba(0,217,255,0.05);margin-left:10px;backdrop-filter:blur(10px)}.msg.aria h1{font-size:12px;margin:4px 0 6px;color:var(--primary);font-weight:700;text-shadow:0 0 10px var(--glow)}.msg.aria h2{font-size:11px;margin:3px 0 5px;color:#10b981;font-weight:600}.msg.aria p{margin:6px 0}.msg.aria ul{margin:8px 0 8px 18px}.msg.aria li{margin:3px 0}@keyframes slide-in{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}.input-box{display:flex;gap:12px;padding:16px;background:linear-gradient(180deg,rgba(10,14,26,0.9) 0%,rgba(5,8,16,0.95) 100%);border-top:2px solid var(--primary);box-shadow:inset 0 1px 0 rgba(255,255,255,0.05),0 -4px 20px rgba(0,217,255,0.1);align-items:flex-end;backdrop-filter:blur(10px)}textarea{flex:1;min-width:200px;padding:12px 16px;border:1px solid var(--primary);border-radius:8px;font-size:13px;background:rgba(10,14,26,0.6);color:#e0e7ff;outline:none;transition:all 0.3s ease;font-family:'Courier New',monospace;resize:none;max-height:120px;min-height:45px;backdrop-filter:blur(5px)}textarea::placeholder{color:rgba(224,231,255,0.4)}textarea:focus{border-color:var(--primary);box-shadow:0 0 40px var(--glow),inset 0 0 10px rgba(0,217,255,0.1);background:rgba(10,14,26,0.8)}.btn-group{display:flex;gap:10px}.btn-send{padding:11px 24px;background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);color:var(--dark);border:none;border-radius:6px;font-weight:700;cursor:pointer;transition:all 0.3s cubic-bezier(0.34,1.56,0.64,1);font-size:13px;box-shadow:0 0 30px var(--glow),0 8px 16px rgba(0,217,255,0.2);letter-spacing:1px;text-transform:uppercase}.btn-send:hover{transform:translateY(-3px);box-shadow:0 0 50px var(--glow),0 12px 24px rgba(0,217,255,0.3)}.btn-send:active{transform:translateY(-1px)}.footer{text-align:center;padding:12px;font-size:10px;color:var(--primary);opacity:0.7;border-top:1px solid var(--primary);cursor:pointer;transition:opacity 0.3s;letter-spacing:1px}.footer:hover{opacity:1}.feedback{position:fixed;bottom:60px;right:20px;background:linear-gradient(135deg,rgba(0,217,255,0.1) 0%,rgba(0,217,255,0.05) 100%);border:1px solid var(--primary);border-radius:8px;padding:12px;display:none;z-index:999;flex-direction:row;gap:6px;backdrop-filter:blur(10px);box-shadow:0 0 30px var(--glow)}.feedback.active{display:flex}.feedback button{padding:6px 12px;background:var(--primary);border:none;color:var(--dark);border-radius:4px;cursor:pointer;font-size:11px;font-weight:700;transition:all 0.2s}::-webkit-scrollbar{width:8px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:var(--primary);border-radius:10px;box-shadow:0 0 10px var(--glow)}.grid-bg{position:fixed;top:0;left:0;width:100%;height:100%;background-image:linear-gradient(0deg,transparent 24%,var(--glow) 25%,var(--glow) 26%,transparent 27%,transparent 74%,var(--glow) 75%,var(--glow) 76%,transparent 77%,transparent),linear-gradient(90deg,transparent 24%,var(--glow) 25%,var(--glow) 26%,transparent 27%,transparent 74%,var(--glow) 75%,var(--glow) 76%,transparent 77%,transparent);background-size:50px 50px;opacity:0.03;pointer-events:none;z-index:0}@media(max-width:600px){.msg{max-width:95%}.header h1{font-size:24px;letter-spacing:2px}.theme-circle{width:40px;height:40px;font-size:16px}.chat{padding:15px}.input-box{padding:12px}textarea{min-width:150px}}</style></head><body><div class="grid-bg"></div><div class="container"><div class="header"><div class="header-content"><h1>◆ ARIA ◆</h1><div class="theme-toggle"><button class="theme-circle active" onclick="setTheme('male')" title="Cyan Mode">♂️</button><button class="theme-circle" onclick="setTheme('female')" title="Pink Mode">♀️</button></div></div><div class="header-sub">» STRATEGIC THINKING PARTNER «</div></div><div class="chat" id="chat"></div><div class="input-box"><textarea id="input" placeholder="Command..."></textarea><div class="btn-group"><button class="btn-send" onclick="send()">SEND</button></div></div><div class="feedback" id="feedback"><button onclick="rateFeedback(1)">👎</button><button onclick="rateFeedback(2)">😐</button><button onclick="rateFeedback(3)">👍</button><button onclick="rateFeedback(4)">🔥</button><button onclick="rateFeedback(5)">💯</button></div><div class="footer" onclick="showFeedback()">⭐ RATE RESPONSE</div></div><script>const chat=document.getElementById("chat"),input=document.getElementById("input"),feedback=document.getElementById("feedback");let UID=localStorage.getItem("aria_uid");if(!UID){const name=prompt("What's your name?") || "user_"+Math.random().toString(36).substr(2,9);UID=name.toLowerCase().replace(/\s+/g,"_")+Math.random().toString(36).substr(2,5);localStorage.setItem("aria_uid",UID);localStorage.setItem("aria_name",name)}let lastMessageId=null;function setTheme(t){const root=document.documentElement;const btns=document.querySelectorAll(".theme-circle");btns.forEach(b=>b.classList.remove("active"));if(t==="female"){root.classList.add("theme-female");btns[1].classList.add("active")}else{root.classList.remove("theme-female");btns[0].classList.add("active")}localStorage.setItem("aria_theme",t)}function showFeedback(){feedback.classList.toggle("active")}function rateFeedback(score){fetch("/feedback",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:UID,score:score,message_id:lastMessageId})});feedback.classList.remove("active")}function addMsg(t,s){const d=document.createElement("div");d.className=`msg ${s}`;d.innerHTML=s==="aria"?marked.parse(t):t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;if(s==="aria")lastMessageId=Math.random()}async function send(){const m=input.value.trim();if(!m)return;addMsg(m,"user");input.value="";input.style.height="45px";addMsg("...","aria");const l=chat.lastChild;try{const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:m,user_id:UID})});const d=await r.json();l.innerHTML=marked.parse(d.reply||"No response")}catch(e){l.textContent="Error: "+e.message}}input.addEventListener("input",()=>{input.style.height="45px";input.style.height=Math.min(input.scrollHeight,120)+"px"});window.addEventListener("load",()=>{const saved=localStorage.getItem("aria_theme")||"male";setTheme(saved)})</script></body></html>"""


# ════════════════════════════════════════════════════════════════════
# [S11] HTTP ENDPOINTS
#  All routes ARIA responds to.
#  To add a new endpoint: add an elif self.path=="/yourpath" block.
# ════════════════════════════════════════════════════════════════════
class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Suppress default server logs

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","POST,GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()

    def do_GET(self):

        # ── Home (UI) ──────────────────────────────
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers()
            self.wfile.write(HTML.encode())

        # ── Health check ──────────────────────────
        elif self.path == "/health":
            self._json({"status":"ARIA 3.5 alive 💚","stage":get_aria_stage()[0]})

        # ── API diagnostic ────────────────────────
        elif self.path == "/debug":
            results = {}
            for i,k in enumerate(KEYS['groq']):
                if not k: continue
                try:
                    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                        json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":"test"}]},
                        headers={"Authorization":f"Bearer {k}"},timeout=5)
                    results[f"groq_{i+1}"] = f"✅ {r.status_code}"
                except Exception as e:
                    results[f"groq_{i+1}"] = f"❌ {str(e)[:30]}"
            for i,k in enumerate(KEYS['gemini']):
                if not k: continue
                try:
                    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={k}",
                        json={"contents":[{"role":"user","parts":[{"text":"test"}]}]},timeout=5)
                    results[f"gemini_{i+1}"] = f"✅ {r.status_code}"
                except Exception as e:
                    results[f"gemini_{i+1}"] = f"❌ {str(e)[:30]}"
            self._json({"status":"API Diagnostic","results":results,"timestamp":datetime.now().isoformat()})

        # ── Memory debug ──────────────────────────
        elif self.path == "/memory-debug":
            self._json({"status":"Memory Breakdown","breakdown":get_memory_breakdown(),"timestamp":datetime.now().isoformat()})

        # ── Analytics ─────────────────────────────
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
                        uids = set(d.to_dict().get("user_id","") for d in ldocs if d.to_dict().get("user_id"))
                        user_count = len(uids)
                        kb_count = len(list(db.collection("aria_knowledge").stream()))
                    except: pass
                self._json({
                    "status":"ARIA 3.5 Analytics",
                    "aria_stage":stage,
                    "aria_confidence":f"{round(conf*100)}%",
                    "memory":{"used_mb":round(mem.used/1024/1024,2),"total_mb":round(mem.total/1024/1024,2),"percent":mem.percent},
                    "cpu_percent":cpu,
                    "users":user_count,
                    "learning_interactions":learning_count,
                    "knowledge_base_size":kb_count,
                    "cache_stats":cache_stats,
                    "timestamp":datetime.now().isoformat()
                })
            except Exception as e:
                self._json({"error":str(e)},500)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):

        data = self._body()

        # ── /chat ──────────────────────────────────
        if self.path == "/chat":
            m  = data.get("message","").strip()
            u  = data.get("user_id","default_user").strip()
            if not m:
                self._json({"reply":"Say something!"})
                return
            # Try Groq first, then Gemini
            reply = ask(m, u, 'groq') or ask(m, u, 'gemini')
            if not reply:
                reply = "I'm thinking slower than usual. Give me a moment? 🤔"
            self._json({"reply":reply})

        # ── /feedback ─────────────────────────────
        elif self.path == "/feedback":
            u     = data.get("user_id","default_user")
            score = data.get("score",0)
            if db:
                try:
                    # Get last interaction for this user
                    docs = list(db.collection("aria_learning")
                                 .where("user_id","==",u)
                                 .order_by("timestamp",direction=firestore.Query.DESCENDING)
                                 .limit(1).stream())
                    if docs:
                        last = docs[0].to_dict()
                        q = last.get("user_message","")
                        a = last.get("aria_response","")
                        # Trigger learning
                        learn_from_rating(u, score, q, a)
                        # Update the interaction record
                        docs[0].reference.update({"feedback_score":score,"execution_status":"rated"})
                except: pass
            self._json({"status":"Feedback recorded","score":score})

        else:
            self.send_response(404)
            self.end_headers()

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length",0))
            return json.loads(self.rfile.read(length))
        except:
            return {}

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers()
        self.wfile.write(body)


# ════════════════════════════════════════════════════════════════════
# [S12] SERVER START
# ════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"ARIA 3.5 running on port {port} 💚")
    server.serve_forever()

