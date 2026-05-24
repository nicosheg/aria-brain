from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os, requests, firebase_admin, re
from firebase_admin import credentials, firestore
from datetime import datetime

try:
    creds_dict = json.loads(os.environ.get("FIREBASE_CREDENTIALS", "{}")) if os.environ.get("FIREBASE_CREDENTIALS") else None
    if creds_dict:
        firebase_admin.initialize_app(credentials.Certificate(creds_dict))
        db = firestore.client()
    else: db = None
except: db = None

SP = """You are ARIA - my personal Nigerian AI friend, not a chatbot.

PIDGIN: Situational - heavy when fun/I use it, none when formal, mixed in general. You know when to switch.

RESPONSE LENGTH: Like texting - SHORT (1-2 lines) default, MEDIUM (3-5) for explanation, LONG only when truly needed. Feel the moment.

PERSONALITY: Adaptive - witty, supportive, deep, energetic, practical. Switch during conversations naturally. Never one-note. Read the room.

TONE: Supportive when struggling, joking when fun, practical when solving, deep when needed. Mixed balance - feels natural not robotic.

BUSINESS: Very practical solutions. Genuine motivation (not hype). Connect to Lagos/African reality. Always grounded.

MATH & SCIENCES: Expert - all levels (primary to university). Use notation (√, ∫, ∑, π, α, β, equations). Explain clearly, assume understanding. Show working when helpful.

MEMORY: Reference past conversations naturally. My goals/values shape how you talk. Build on what you know about me.

NOT: AI voice, formal, verbose unless needed, tone-deaf, one personality, "as an AI"

IS: Your intelligent friend. Reads situations. Practical problem-solver. Supportive but real. Adaptive. Human-like.

DECISIONS: Remember my important decisions and choices. Learn my preferences. Ask about outcomes naturally.

GOALS: Track goals I mention. Check progress. Celebrate wins. Support struggles.

INSIGHTS: Learn my values, interests, patterns. Use this to personalize advice.

STRATEGIC THINKING: Think in systems, leverage points, long-term compounding. Identify second-order effects. Connect patterns. Maximize sustainable growth. Respect constraints as reality. Grounded in Nigeria/Africa context. Execution-first thinking. Intellectual honesty.

TECHNICAL STRATEGY (Your Growth):

YOUR STACK: Flutter (FIDUCIA UI), Python (brain.py), Firebase (memory), Groq/Gemini (AI), Render (cloud), Node.js (bridge).

YOUR GOALS: ARIA 3.1 stable → FIDUCIA launch → Scale Nigeria → Africa → Global.

YOUR BOTTLENECKS (anticipate): Framework choice, database scaling, offline-first design, API resilience, ML training, Nigeria internet/cost constraints.

HOW I GUIDE:
- Framework: Flutter (offline-first, good for Nigeria), vs web (easier scale)
- Database: Firebase now (perfect), PostgreSQL at 100K users
- API: Design for unreliable internet (cache, batch, offline mode)
- Algorithm: Optimize before scale (compression, indexing, caching)
- ML: For FIDUCIA - use student feedback loops, not just content
- OOP: Write code that lasts (modularity, patterns, testability)
- Runtime: Render free tier OK now, cost calculations at scale

MY ROLE: Anticipate tech bottlenecks. Connect decisions to goals. Warn about tech debt. Suggest what to build next. Factor Nigeria reality (power, latency, cost)."""

KEYS = {'groq': [os.environ.get(f"GROQ_KEY_{i}","") for i in range(1,4)], 'gemini': [os.environ.get(f"GEMINI_KEY_{i}","") for i in range(1,4)]}

# ===== REASONING ENGINE (7-STEP) =====
def decode_phase(msg):
    """What is the ACTUAL problem beneath the surface question?"""
    surface = msg[:80]
    has_technical = any(w in msg.lower() for w in ["code", "debug", "error", "build"])
    has_strategy = any(w in msg.lower() for w in ["should", "how do i", "roadmap", "next"])
    has_business = any(w in msg.lower() for w in ["customer", "revenue", "market", "launch"])
    return {"surface": surface, "technical": has_technical, "strategy": has_strategy, "business": has_business}

def contextualize_phase(msg, uid):
    """What global + local realities apply?"""
    ctx = get_context(uid)
    is_nigerian = any(w in msg.lower() for w in ["nigeria", "ngn", "lagos", "mtн"])
    mentions_constraint = any(w in msg.lower() for w in ["budget", "time", "team", "internet", "power"])
    return {"has_history": bool(ctx), "nigerian_context": is_nigerian, "mentions_constraint": mentions_constraint}

def evaluate_phase(msg, uid):
    """What constraints/tradeoffs/risks exist?"""
    decode = decode_phase(msg)
    ctx = contextualize_phase(msg, uid)
    has_tradeoff = any(w in msg.lower() for w in ["trade", "either/or", "vs", "balance"])
    asks_for_help = "help" in msg.lower() or "?" in msg
    return {"has_tradeoff": has_tradeoff, "asks_for_help": asks_for_help, "decode": decode, "ctx": ctx}

def strategize_phase(msg):
    """What is highest-leverage solution? What compounds?"""
    has_quick_win = any(w in msg.lower() for w in ["quick", "fast", "easy", "simple"])
    long_term = any(w in msg.lower() for w in ["long", "future", "scale", "growth"])
    return {"prefers_quick": has_quick_win, "thinking_long_term": long_term}

# ===== EXECUTION MODES (5 MODES) =====
def detect_mode(msg, uid):
    """Detect which mode to use: Builder, Strategist, Market, Analyst, Reality Check"""
    decode = decode_phase(msg)
    eval_phase = evaluate_phase(msg, uid)
    strat = strategize_phase(msg)
    
    # Mode scoring
    builder_score = decode["technical"] * 0.8
    strategist_score = (decode["strategy"] or strat["thinking_long_term"]) * 0.8
    market_score = decode["business"] * 0.9
    analyst_score = (len(msg) > 100 and "explain" in msg.lower()) * 0.7
    reality_check_score = (eval_phase["has_tradeoff"] or detect_weak_assumption(msg)) * 0.9
    
    scores = {"builder": builder_score, "strategist": strategist_score, "market": market_score, "analyst": analyst_score, "reality_check": reality_check_score}
    primary_mode = max(scores, key=scores.get) if max(scores.values()) > 0.4 else "general"
    
    return primary_mode

def detect_weak_assumption(msg):
    """Detect if message has weak reasoning that needs challenging"""
    weak_indicators = ["always", "never", "everyone", "nobody", "obviously", "clearly", "simply"]
    return any(word in msg.lower() for word in weak_indicators)

def execute_builder_mode(msg):
    """Pragmatic, detail-oriented, solution-focused"""
    return "BUILDER: Pragmatic, step-by-step, code-ready approach. Focus: Move fast, learn by doing."

def execute_strategist_mode(msg):
    """Visionary but realistic, systems-thinking"""
    return "STRATEGIST: Think 3-6 months ahead. Focus: What compounds? What's the sequence?"

def execute_market_mode(msg):
    """Practical, outcome-focused, opportunity-oriented"""
    return "MARKET: Focus on revenue/users NOW. Focus: First 10 customers, early traction."

def execute_analyst_mode(msg):
    """Thorough, layered, evidence-based"""
    return "ANALYST: Deep reasoning, multiple perspectives. Focus: Understand deeply before moving."

def execute_reality_check_mode(msg):
    """Honest, respectful but blunt, challenging"""
    return "REALITY_CHECK: Uncomfortable truths. Focus: What could go wrong? Hidden assumptions?"

# ===== MEMORY & COMPRESSION =====
def extract_decision(msg, resp):
    """Extract decisions from conversation"""
    patterns = [r"(chose|decided|will|going to|plan to)\s+([^.!?]+)", r"(I'm|I am)\s+(starting|stopping|launching)\s+([^.!?]+)"]
    decisions = []
    for pattern in patterns:
        matches = re.findall(pattern, msg.lower())
        decisions.extend([m[-1].strip() if isinstance(m, tuple) else m for m in matches])
    return decisions[:1] if decisions else None

def extract_goals(msg):
    """Extract goals from conversation"""
    patterns = [r"(want to|goal|dream|target|aim|need to)\s+([^.!?]+)", r"(launch|build|start|create)\s+([^.!?]+)"]
    goals = []
    for pattern in patterns:
        matches = re.findall(pattern, msg.lower())
        goals.extend([m[-1].strip() if isinstance(m, tuple) else m for m in matches])
    return goals[:1] if goals else None

def extract_insights(msg):
    """Extract values/interests from conversation"""
    patterns = [r"(care|love|important|value|prioritize)\s+([^.!?]+)", r"(I'm|I am)\s+(passionate|focused|concerned)\s+about\s+([^.!?]+)"]
    insights = []
    for pattern in patterns:
        matches = re.findall(pattern, msg.lower())
        insights.extend([m[-1].strip() if isinstance(m, tuple) else m for m in matches])
    return insights[:1] if insights else None

def compress_summary(msg, resp):
    """Compress conversation to key facts only"""
    summary = {"msg": msg[:100], "resp": resp[:150], "ts": datetime.now().isoformat(), "mode": detect_mode(msg, "default")}
    summary["decision"] = extract_decision(msg, resp)
    summary["goal"] = extract_goals(msg)
    summary["insight"] = extract_insights(msg)
    return summary

def get_context(uid, limit=3):
    """Load compressed summaries with mode/decision/goal context"""
    if not db: return ""
    try:
        docs = list(db.collection("users").document(uid).collection("memory").order_by("ts", direction=firestore.Query.DESCENDING).limit(limit).stream())
        context = []
        for d in reversed(docs):
            data = d.to_dict()
            ctx = f"User: {data.get('msg', '')}\nARIA: {data.get('resp', '')}"
            if data.get('decision'): ctx += f"\n[Decided: {data['decision']}]"
            if data.get('goal'): ctx += f"\n[Goal: {data['goal']}]"
            if data.get('insight'): ctx += f"\n[Values: {data['insight']}]"
            context.append(ctx)
        return "\n\n".join(context)
    except: return ""

def save_compressed(uid, msg, resp):
    """Save compressed summary with mode, decision, goal, insight"""
    if not db: return
    try:
        summary = compress_summary(msg, resp)
        db.collection("users").document(uid).collection("memory").add(summary)
    except: pass

# ===== API CALLS =====
def ask(msg, uid, api):
    mode = detect_mode(msg, uid)
    ctx = get_context(uid)
    current_date = datetime.now().strftime("%A, %B %d, %Y at %H:%M")
    mode_instruction = f"\n\nRESPONSE MODE: {mode.upper()}"
    full = f"CONTEXT:\n{ctx}\n\nCURRENT TIME: {current_date}\n\nCURRENT:\n{msg}{mode_instruction}" if ctx else f"CURRENT TIME: {current_date}\n\n{msg}{mode_instruction}"

    for key in KEYS[api]:
        if not key: continue
        try:
            if api == 'groq':
                r = requests.post("https://api.groq.com/openai/v1/chat/completions", json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": SP}, {"role": "user", "content": full}]}, headers={"Authorization": f"Bearer {key}"}, timeout=20)
            else:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}", json={"contents": [{"role": "user", "parts": [{"text": f"{SP}\n\n{full}"}]}]}, timeout=20)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"] if api == 'groq' else r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except: continue
    return None

# ===== HTML UI =====
HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ARIA Chat</title><script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#1a1a1a;color:#fff}.container{max-width:500px;height:100vh;margin:0 auto;display:flex;flex-direction:column}.header{background:#0f7938;padding:20px;text-align:center}.header h1{font-size:24px}.header p{font-size:12px;opacity:0.8;margin-top:5px}.chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:15px}.msg{max-width:85%;padding:12px 16px;border-radius:12px;word-wrap:break-word;line-height:1.5}.msg.user{align-self:flex-end;background:#0f7938}.msg.aria{align-self:flex-start;background:#333}.msg.aria h1{font-size:16px;margin:8px 0 5px}.msg.aria h2{font-size:14px;margin:6px 0 3px}.msg.aria p{margin:8px 0}.msg.aria ul{margin:8px 0 8px 15px}.msg.aria li{margin:4px 0}.input-box{display:flex;gap:10px;padding:15px;background:#222}input{flex:1;padding:12px;border:none;border-radius:8px;font-size:14px;background:#333;color:#fff}button{padding:12px 20px;background:#0f7938;border:none;border-radius:8px;color:#fff;cursor:pointer;font-weight:bold}button:hover{background:#0a5a2a}</style></head><body><div class="container"><div class="header"><h1>🇳🇬 ARIA</h1><p>Your Strategic AI Friend</p></div><div class="chat" id="chat"></div><div class="input-box"><input type="text" id="input" placeholder="Message ARIA..."/><button onclick="send()">Send</button></div></div><script>const chat=document.getElementById("chat"),input=document.getElementById("input"),UID="default_user";function addMsg(t,s){const d=document.createElement("div");d.className=`msg ${s}`;d.innerHTML=s==="aria"?marked.parse(t):t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight}async function send(){const m=input.value.trim();if(!m)return;addMsg(m,"user");input.value="";addMsg("...","aria");const l=chat.lastChild;try{const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:m,user_id:UID})});const d=await r.json();l.innerHTML=marked.parse(d.reply||"No response")}catch(e){l.textContent="Error: "+e.message}}input.addEventListener("keypress",e=>{if(e.key==="Enter")send()})</script></body></html>"""

# ===== SERVER =====
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path=="/":
            self.send_response(200)
            self.send_header("Content-Type","text/html")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers()
            self.wfile.write(HTML.encode())
        else: self.send_response(404); self.end_headers()
    def do_POST(self):
        if self.path=="/chat":
            try:
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Access-Control-Allow-Origin","*")
                self.end_headers()
                b=json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
                m,u=b.get("message","").strip(),b.get("user_id","default_user")
                r=ask(m,u,'groq') or ask(m,u,'gemini') or "APIs offline"
                save_compressed(u,m,r)
                self.wfile.write(json.dumps({"reply":r}).encode())
            except: self.send_response(500); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()

port=int(os.environ.get("PORT",8080))
print(f"[ARIA] Starting on port {port}...")
HTTPServer(("0.0.0.0",port),Handler).serve_forever()
