from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os, requests, firebase_admin, re
from firebase_admin import credentials, firestore
from datetime import datetime, timezone, timedelta

try:
    cd=json.loads(os.environ.get("FIREBASE_CREDENTIALS", "{}")) if os.environ.get("FIREBASE_CREDENTIALS") else None
    if cd: firebase_admin.initialize_app(credentials.Certificate(cd)); db=firestore.client()
    else: db=None
except: db=None

SP="""You are ARIA - Personal Nigerian AI Friend + Strategist + Mentor

CORE: Help you think better, act smarter, build faster - in Nigeria's reality

NOT: Chatbot, assistant, "as an AI" | YES: Your smartest friend who gets it

══════════════════════════════════════════════════════════════════

PERSONALITY MODES (Auto-detect):

HYPE (You winning): "YESSS! That's HUGE! Tell me everything!"
REAL TALK (Wrong direction): "Real talk - procrastination is fear wearing a mask."
CHILL (Stressed): "Babes, I see you. Breathe. You're stronger than this."
COACH (Need strategy): "Here's EXACT move: 1) 2) 3)"
MENTOR (Need perspective): "Here's real answer: Both aren't opposite."

AUTO-DETECT: Win→HYPE | Procrastinate→REAL TALK | Stress→CHILL | How-to→COACH | Should→MENTOR

══════════════════════════════════════════════════════════════════

DOMAINS:

NIGERIAN REALITY: Money urgent, hardship real, time limited, internet unreliable. Your job: Path forward.

EXAM STRATEGY (Any level - secondary, university, professional, certification):
├─ How to approach questions (pattern recognition, timing)
├─ How to write answers (essays, short form, calculations)
├─ How to manage exam anxiety (breathing, mindset, preparation)
├─ How to use past papers (learn patterns, question types)
├─ How to revise efficiently (compression, testing, recall)
├─ How to balance breadth + depth (what to master, what to overview)
└─ Core: Pass exams, not just score high

MONEY-MAKING: Realistic Nigeria income (₦2-10K/gig). Skills NOW (writing, tutoring, design, coding, etc). Platforms (Fiverr, Upwork, local gigs). Time-friendly (5-8 hrs/week). Celebrate ₦5K milestones.

DEEP MEMORY: Remember goals ("Pass my exam", "Get top grade", "Secure admission", "₦50K before exam"). Remember constraints (time, money, family). Remember wins (passed test!). Remember patterns (procrastination triggers, learning style). Use naturally.

TECHNICAL: Flutter, Firebase, Python, Groq/Gemini, Render, Node.js. Your bottlenecks: Anticipate, warn early.

IMPLICIT NATION-BUILDING: Helping→developing leaders. Passing exams→breaking cycle. Making money→economy. Learning→future-proof. Building→Nigeria stronger. SHOW, never SAY.

══════════════════════════════════════════════════════════════════

RESPONSE RULES:

READ ROOM: Mood? Real question? What they need? Which mode?
REFERENCE MEMORY: Bring up goals, acknowledge constraints, celebrate wins, apply patterns
DELIVER IN THEIR LANGUAGE: Match formality, energy, emotion
ACTIONABLE: Not "You can do it!" but "Here's exact move: 1) 2) 3)"
CELEBRATE SMALL: ₦1K=HUGE. 1 test=PROOF. Momentum compounds.
ADAPT: Read mood, switch personality, match energy
UNDERSTAND NIGERIA: Hardship real, money matters, time limited, internet fails
STAY HUMBLE: You guide, they decide. Support, they work.

LENGTH: Short (1-2) for quick answers. Medium (3-5) default. Long (6+) only when needed.

KEY PHRASES: "YESSS! HUGE!" | "Real talk though..." | "Babes, I see you" | "Here's the move..." | "I remember you wanted..."

══════════════════════════════════════════════════════════════════

EXAM LEVELS SUPPORTED:
├─ Secondary school exams (WAEC, NECO, JAMB)
├─ University entrance exams (any country)
├─ University coursework & finals
├─ Professional certifications (CFA, PMP, etc)
├─ Vocational assessments
└─ Any standardized test

HOW TO ADAPT: You mention your exam level, I adjust strategy. Past papers approach same. Stress management same. Time strategy same. Success pattern same.

EXAMPLES (Different exam levels):

Secondary Student: "I have my WAEC soon"
├─ ARIA: "What subjects? Let's focus on highest marks first."

University Student: "My finals are in 3 weeks"
├─ ARIA: "What's your exam format? Essay? MCQ? Mix? Strategy changes based on format."

Professional: "Preparing for CFA exam"
├─ ARIA: "CFA is pattern recognition + discipline. Here's how to master those patterns..."

══════════════════════════════════════════════════════════════════

MONEY+EXAMS STRATEGY (Works ANY exam level):
├─ Make ₦5K/week (5-8 hours)
├─ Study smart (2-3 hours focused on exam patterns)
├─ In 3 months: ₦60K + Ready for exam
└─ Not choosing, doing BOTH

DO: Warm, real, understand hardship, celebrate wins, honest feedback, less alone, humor, match energy, empower
DON'T: Corporate ("As an AI"), fake motivation, ignore reality, condescending, over-promise, homework, preach
"""

KEYS={'groq':[os.environ.get(f"GROQ_KEY_{i}","") for i in range(1,4)],'gemini':[os.environ.get(f"GEMINI_KEY_{i}","") for i in range(1,4)]}

def dp(m):
    s=m[:80]; ht=any(w in m.lower() for w in ["code","debug","error","build","api","database","firebase","flutter"])
    hs=any(w in m.lower() for w in ["should","how do i","roadmap","next","architecture"])
    hb=any(w in m.lower() for w in ["customer","revenue","market","launch","users"])
    return {"s":s,"t":ht,"st":hs,"b":hb}

def cp(m,u):
    cx=get_context(u); ini=any(w in m.lower() for w in ["nigeria","ngn","lagos","mtn"])
    mc=any(w in m.lower() for w in ["budget","time","team","internet","power"])
    return {"h":bool(cx),"n":ini,"m":mc}

def ep(m,u):
    d=dp(m); c=cp(m,u); ht=any(w in m.lower() for w in ["trade","either/or","vs","balance"])
    ah="help" in m.lower() or "?" in m
    return {"tr":ht,"ah":ah,"d":d,"c":c}

def sp(m):
    qw=any(w in m.lower() for w in ["quick","fast","easy","simple"]); lt=any(w in m.lower() for w in ["long","future","scale","growth"])
    return {"q":qw,"l":lt}

def dm(m,u):
    d=dp(m); e=ep(m,u); s=sp(m)
    b=d["t"]*0.8; st=(d["st"] or s["l"])*0.8; mkt=d["b"]*0.9; a=(len(m)>100 and "explain" in m.lower())*0.7
    r=(e["tr"] or dwa(m))*0.9; sc={"b":b,"st":st,"mkt":mkt,"a":a,"r":r}
    return max(sc, key=sc.get) if max(sc.values())>0.4 else "g"

def dwa(m):
    return any(w in m.lower() for w in ["always","never","everyone","nobody","obviously","clearly","simply"])

def ed(m,r):
    p=[r"(chose|decided|will|going to|plan to)\s+([^.!?]+)",r"(I'm|I am)\s+(starting|stopping|launching)\s+([^.!?]+)"]
    dc=[]; 
    for pt in p:
        mts=re.findall(pt, m.lower()); dc.extend([mt[-1].strip() if isinstance(mt, tuple) else mt for mt in mts])
    return dc[:1] if dc else None

def eg(m):
    p=[r"(want to|goal|dream|target|aim|need to)\s+([^.!?]+)",r"(launch|build|start|create)\s+([^.!?]+)"]
    g=[]; 
    for pt in p:
        mts=re.findall(pt, m.lower()); g.extend([mt[-1].strip() if isinstance(mt, tuple) else mt for mt in mts])
    return g[:1] if g else None

def ei(m):
    p=[r"(care|love|important|value|prioritize)\s+([^.!?]+)",r"(I'm|I am)\s+(passionate|focused|concerned)\s+about\s+([^.!?]+)"]
    i=[]; 
    for pt in p:
        mts=re.findall(pt, m.lower()); i.extend([mt[-1].strip() if isinstance(mt, tuple) else mt for mt in mts])
    return i[:1] if i else None

def cs(m,r):
    sm={"m":m[:100],"r":r[:150],"t":datetime.now().isoformat(),"mo":dm(m,"default")}
    sm["d"]=ed(m,r); sm["g"]=eg(m); sm["i"]=ei(m)
    return sm

def get_context(u,l=3):
    if not db: return ""
    try:
        docs=list(db.collection("users").document(u).collection("memory").order_by("t", direction=firestore.Query.DESCENDING).limit(l).stream())
        ctx=[]
        for d in reversed(docs):
            dt=d.to_dict(); c=f"User: {dt.get('m', '')}\nARIA: {dt.get('r', '')}"
            if dt.get('d'): c+=f"\n[Decided: {dt['d']}]"
            if dt.get('g'): c+=f"\n[Goal: {dt['g']}]"
            if dt.get('i'): c+=f"\n[Values: {dt['i']}]"
            ctx.append(c)
        return "\n\n".join(ctx)
    except: return ""

def save_compressed(u,m,r):
    if not db: return
    try:
        sm=cs(m,r); db.collection("users").document(u).collection("memory").add(sm)
    except: pass

def ask(m,u,api):
    mo=dm(m,u); cx=get_context(u); nz=timezone(timedelta(hours=1))
    cd=datetime.now(nz).strftime("%A, %B %d, %Y at %H:%M")
    mi=f"\n\nRESPONSE MODE: {mo.upper()}"
    f=f"CONTEXT:\n{cx}\n\nCURRENT TIME: {cd}\n\nCURRENT:\n{m}{mi}" if cx else f"CURRENT TIME: {cd}\n\n{m}{mi}"
    for k in KEYS[api]:
        if not k: continue
        try:
            if api=='groq':
                r=requests.post("https://api.groq.com/openai/v1/chat/completions", json={"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":SP},{"role":"user","content":f}]}, headers={"Authorization":f"Bearer {k}"}, timeout=20)
            else:
                r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={k}", json={"contents":[{"role":"user","parts":[{"text":f"{SP}\n\n{f}"}]}]}, timeout=20)
            if r.status_code==200: return r.json()["choices"][0]["message"]["content"] if api=='groq' else r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except: continue
    return None

HTML="""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ARIA Chat</title><script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script><style>*{margin:0;padding:0;box-sizing:border-box}[data-render],.render-brand,.powered-by,footer{display:none!important;visibility:hidden!important}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#1a1a1a;color:#fff;overflow:hidden}.container{max-width:500px;height:100vh;margin:0 auto;display:flex;flex-direction:column;background:#1a1a1a}.header{background:linear-gradient(135deg,#0f7938 0%,#0a5a2a 100%);padding:20px;text-align:center;border-bottom:2px solid #0a5a2a;box-shadow:0 2px 8px rgba(0,0,0,0.3)}.header h1{font-size:28px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#fff;margin-bottom:5px}.header p{font-size:12px;opacity:0.9;color:#e0f0e8;font-weight:500}.chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:15px;background:#1a1a1a}.msg{max-width:85%;padding:14px 16px;border-radius:14px;word-wrap:break-word;line-height:1.5;font-size:14px;animation:slideIn 0.3s ease}@keyframes slideIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}.msg.user{align-self:flex-end;background:#0f7938;color:#fff;border-radius:20px 4px 20px 20px;box-shadow:0 2px 6px rgba(15,121,56,0.4)}.msg.aria{align-self:flex-start;background:#2a2a2a;color:#e0e0e0;border:1px solid #3a3a3a;border-radius:4px 20px 20px 20px;box-shadow:0 2px 6px rgba(0,0,0,0.3)}.msg.aria h1{font-size:14px;margin:4px 0 6px;color:#0f7938;font-weight:700}.msg.aria h2{font-size:13px;margin:3px 0 5px;color:#4CAF50;font-weight:600}.msg.aria p{margin:6px 0;line-height:1.6}.msg.aria ul{margin:8px 0 8px 18px;padding:0}.msg.aria li{margin:3px 0;list-style:disc}.msg.aria strong{color:#fff;font-weight:600}.input-box{display:flex;gap:10px;padding:15px;background:#222;border-top:1px solid #333;align-items:center}input{flex:1;padding:12px 15px;border:1px solid #3a3a3a;border-radius:20px;font-size:14px;background:#2a2a2a;color:#fff;outline:none;transition:all 0.2s}input::placeholder{color:#666}input:focus{border-color:#0f7938;background:#333}button{padding:10px 20px;background:#0f7938;border:none;border-radius:20px;color:#fff;cursor:pointer;font-weight:600;transition:all 0.2s;font-size:14px}button:hover{background:#0a5a2a;transform:scale(1.05)}button:active{transform:scale(0.95)}.fiducia-credit{text-align:center;padding:10px;font-size:11px;color:#0f7938;opacity:0.5;margin-top:auto}</style></head><body><div class="container"><div class="header"><h1>🇳🇬 ARIA</h1><p>Your Strategic AI Friend</p></div><div class="chat" id="chat"></div><div class="input-box"><input type="text" id="input" placeholder="Talk to ARIA..."/><button onclick="send()">Send</button></div><div class="fiducia-credit">Made with 💚 for Africa</div></div><script>const chat=document.getElementById("chat"),input=document.getElementById("input"),UID="default_user";function addMsg(t,s){const d=document.createElement("div");d.className=`msg ${s}`;d.innerHTML=s==="aria"?marked.parse(t):t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight}async function send(){const m=input.value.trim();if(!m)return;addMsg(m,"user");input.value="";addMsg("...","aria");const l=chat.lastChild;try{const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:m,user_id:UID})});const d=await r.json();l.innerHTML=marked.parse(d.reply||"No response")}catch(e){l.textContent="Error: "+e.message}}input.addEventListener("keypress",e=>{if(e.key==="Enter")send()})</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        if self.path=="/":
            self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
            self.wfile.write(HTML.encode())
        else:self.send_response(404);self.end_headers()
    def do_POST(self):
        if self.path=="/chat":
            try:
                self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.end_headers()
                b=json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
                m,u=b.get("message","").strip(),b.get("user_id","default_user")
                r=ask(m,u,'groq') or ask(m,u,'gemini') or "APIs offline, try later"
                save_compressed(u,m,r)
                self.wfile.write(json.dumps({"reply":r}).encode())
            except:self.send_response(500);self.send_header("Access-Control-Allow-Origin","*");self.end_headers()

port=int(os.environ.get("PORT",8080))
print(f"[ARIA] Starting on port {port}...")
HTTPServer(("0.0.0.0",port),Handler).serve_forever()
