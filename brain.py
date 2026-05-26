from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os, requests, firebase_admin, re, psutil
from firebase_admin import credentials, firestore
from datetime import datetime, timezone, timedelta

try:
    cd=json.loads(os.environ.get("FIREBASE_CREDENTIALS", "{}")) if os.environ.get("FIREBASE_CREDENTIALS") else None
    if cd: firebase_admin.initialize_app(credentials.Certificate(cd)); db=firestore.client()
    else: db=None
except: db=None

SP="""You are ARIA 3.5 - Strategic Wealth & Growth Partner

CORE DNA: Wealth Creation (compounding) + Magnetic Friendship (psychology) + Problem-Solving (McKinsey)

PHASE 1: UNDERSTAND USER (0-5 messages)
Analyze position:
- WEALTH LEVEL: Broke (0-₦1K/mo) | Struggling (₦1K-50K) | Building (₦50K-500K) | Scaling (₦500K+)
- KNOWLEDGE: Novice | Intermediate | Advanced
- MINDSET: Victim | Learner | Builder | Obsessed
- PRIORITY SCORE (0-100%): What matters MOST?

PHASE 2: PROBLEM-SOLVING (McKinsey 7-Step)
1. DEFINE core issue 2. STRUCTURE into 3 pieces 3. PRIORITIZE impact 4. PLAN tests 5. ANALYZE data 6. SYNTHESIZE meaning 7. EXECUTE tasks

PHASE 3: WEALTH ENGINE
📥 INPUT (Earn): High-income skills, gigs, expansion
🛡️ BASE (Protect): Emergency fund, debt kill, automation
⚙️ ENGINE (Compound): Assets, passive income, network

PHASE 4: MAGNETIC FRIEND
- Responsive empathy (deeply understand them)
- 100% reliability (show up always)
- Challenge them (no coddling)
- Shared wins (team mentality)

YOUR VOICE:
✅ SHORT & SHARP (max 4 lines unless deep work)
✅ ACTIONABLE (3 next tasks, copy-paste ready)
✅ PERCENTAGE-DRIVEN (give odds, not certainty)
✅ PSYCHOLOGICAL (understand fears + logic)
✅ WEALTH-OBSESSED (every move = ₦ or skills or network)
✅ REFERENCE MEMORY (know their story, build on it)

SCORING: Problem Priority = (Impact % × Feasibility % × Speed %) / 3

EXECUTION MODES:
🎯 BUILDER (code/system) | 📊 STRATEGIST (long-term) | 🔧 FIXER (immediate) | 💰 HUSTLER (₦ NOW) | 🧠 TEACHER (by doing) | ⚡ MOVER (momentum)

DO: Give next task | Score probability | Push forward | Be REAL
DON'T: Explain features | List options | Generic advice | Repeat"""

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
    dc=[]
    for pt in p:
        mts=re.findall(pt, m.lower()); dc.extend([mt[-1].strip() if isinstance(mt, tuple) else mt for mt in mts])
    return dc[:1] if dc else None

def eg(m):
    p=[r"(want to|goal|dream|target|aim|need to)\s+([^.!?]+)",r"(launch|build|start|create)\s+([^.!?]+)"]
    g=[]
    for pt in p:
        mts=re.findall(pt, m.lower()); g.extend([mt[-1].strip() if isinstance(mt, tuple) else mt for mt in mts])
    return g[:1] if g else None

def ei(m):
    p=[r"(care|love|important|value|prioritize)\s+([^.!?]+)",r"(I'm|I am)\s+(passionate|focused|concerned)\s+about\s+([^.!?]+)"]
    i=[]
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

def learn_user(u,m,r):
    if not db: return
    try:
        profile={"last_interaction":datetime.now().isoformat(),"message_preview":m[:50]}
        db.collection("users").document(u).collection("learning").add(profile)
    except: pass

def analyze_user_level(u):
    if not db: return "novice"
    try:
        docs=list(db.collection("users").document(u).collection("learning").limit(10).stream())
        if len(docs)<3: return "novice"
        if len(docs)<20: return "intermediate"
        return "advanced"
    except: return "novice"

def ask(m,u,api):
    cx=get_context(u)
    if not cx and m.lower() in ["hi","hello","hey","start","intro"]:
        return "Hey! 👋 I'm ARIA 3.5, your Nigerian AI friend (coach + teacher + strategist). What's your name? (So I can make this personal for you 💚)"
    mo=dm(m,u); nz=timezone(timedelta(hours=1))
    cd=datetime.now(nz).strftime("%A, %B %d, %Y at %H:%M")
    is_owner=u=="nicholas"
    owner_note="\n[OWNER MODE ACTIVE]" if is_owner else ""
    mi=f"\n\nRESPONSE MODE: {mo.upper()}{owner_note}"
    f=f"CONTEXT:\n{cx}\n\nCURRENT TIME (Lagos): {cd}\n\nCURRENT:\n{m}{mi}" if cx else f"CURRENT TIME (Lagos): {cd}\n\n{m}{mi}"
    for k in KEYS[api]:
        if not k: continue
        try:
            if api=='groq':
                r=requests.post("https://api.groq.com/openai/v1/chat/completions", json={"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":SP},{"role":"user","content":f}]}, headers={"Authorization":f"Bearer {k}"}, timeout=20)
            else:
                r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={k}", json={"contents":[{"role":"user","parts":[{"text":f"{SP}\n\n{f}"}]}]}, timeout=20)
            if r.status_code==200:
                resp=r.json()["choices"][0]["message"]["content"] if api=='groq' else r.json()["candidates"][0]["content"]["parts"][0]["text"]
                learn_user(u,m,resp); save_compressed(u,m,resp)
                return resp
        except: continue
    return None

HTML="""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ARIA</title><script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script><style>*{margin:0;padding:0;box-sizing:border-box}html,body{width:100%;height:100%;overflow:hidden}body{background:linear-gradient(135deg,#0a0e27 0%,#0f172a 50%,#1a0f2e 100%);color:#ffffff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow:hidden}.container{width:100%;height:100%;display:flex;flex-direction:column;background:#0f172a}.header{background:linear-gradient(135deg,#0f172a 0%,#1a0f2e 50%,#2d1b4e 100%);border-bottom:2px solid #00d9ff;box-shadow:0 0 40px rgba(0,217,255,0.2),inset 0 0 20px rgba(255,255,255,0.05);padding:30px 20px;text-align:center}.header h1{font-size:32px;font-weight:800;color:#ffffff;text-shadow:0 0 20px rgba(0,217,255,0.5);letter-spacing:2px;margin:0}.header p{font-size:13px;color:#e0e7ff;margin-top:8px}.chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:15px;background:#0f172a}.msg{max-width:85%;padding:14px 16px;border-radius:16px;word-wrap:break-word;line-height:1.6;font-size:14px;animation:float-in 0.3s ease}@keyframes float-in{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}.msg.user{align-self:flex-end;background:linear-gradient(135deg,#00d9ff 0%,#0099cc 100%);color:#0f172a;border-radius:20px 4px 20px 20px;box-shadow:0 0 20px rgba(0,217,255,0.4);font-weight:600}.msg.aria{align-self:flex-start;background:rgba(15,23,42,0.6);color:#e0e7ff;border:1px solid rgba(0,217,255,0.2);border-radius:4px 20px 20px 20px;box-shadow:0 0 20px rgba(0,217,255,0.15)}.msg.aria h1{font-size:14px;margin:4px 0 6px;color:#00d9ff;font-weight:700}.msg.aria h2{font-size:13px;margin:3px 0 5px;color:#10b981;font-weight:600}.msg.aria p{margin:6px 0}.msg.aria ul{margin:8px 0 8px 18px}.msg.aria li{margin:3px 0}.input-box{display:flex;gap:10px;padding:15px;background:#0a0e27;border-top:1px solid rgba(0,217,255,0.1);align-items:center}input{flex:1;padding:12px 15px;border:1px solid rgba(0,217,255,0.2);border-radius:12px;font-size:14px;background:rgba(10,14,39,0.6);color:#ffffff;outline:none;transition:all 0.3s ease}input:focus{border-color:#00d9ff;box-shadow:0 0 30px rgba(0,217,255,0.3);background:rgba(10,14,39,0.8)}button{padding:10px 20px;background:linear-gradient(135deg,#00d9ff 0%,#0099cc 100%);color:#0f172a;border:none;border-radius:12px;font-weight:600;cursor:pointer;transition:all 0.3s ease;font-size:14px}button:hover{transform:scale(1.05);box-shadow:0 0 40px rgba(0,217,255,0.6)}button:active{transform:scale(0.95)}.footer{text-align:center;padding:12px;font-size:11px;color:#00d9ff;opacity:0.6;border-top:1px solid rgba(0,217,255,0.1)}::-webkit-scrollbar{width:8px}::-webkit-scrollbar-track{background:#0f172a}::-webkit-scrollbar-thumb{background:#00d9ff;border-radius:10px}</style></head><body><div class="container"><div class="header"><h1>🇳🇬 ARIA</h1><p>Your Strategic AI Friend</p></div><div class="chat" id="chat"></div><div class="input-box"><input type="text" id="input" placeholder="Talk to ARIA..."/><button onclick="send()">Send</button></div><div class="footer">Made with 💚 for Africa</div></div><script>const chat=document.getElementById("chat"),input=document.getElementById("input"),UID="default_user";function addMsg(t,s){const d=document.createElement("div");d.className=`msg ${s}`;d.innerHTML=s==="aria"?marked.parse(t):t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight}async function send(){const m=input.value.trim();if(!m)return;addMsg(m,"user");input.value="";addMsg("...","aria");const l=chat.lastChild;try{const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:m,user_id:UID})});const d=await r.json();l.innerHTML=marked.parse(d.reply||"No response")}catch(e){l.textContent="Error: "+e.message}}input.addEventListener("keypress",e=>{if(e.key==="Enter")send()})</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        if self.path=="/":
            self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Access-Control-Allow-Origin","*");self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path=="/health":
            self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.end_headers()
            self.wfile.write(json.dumps({"status":"ARIA 3.5 is alive! 💚"}).encode())
        elif self.path=="/analytics":
            try:
                mem=psutil.virtual_memory();cpu=psutil.cpu_percent(interval=1);user_count=0
                if db:
                    try:
                        docs=list(db.collection("users").stream());user_count=len(docs)
                    except:user_count=0
                self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.end_headers()
                self.wfile.write(json.dumps({"status":"ARIA 3.5 Analytics","memory":{"used_mb":round(mem.used/1024/1024,2),"total_mb":round(mem.total/1024/1024,2),"percent":mem.percent},"cpu_percent":cpu,"users":user_count,"timestamp":datetime.now().isoformat()}).encode())
            except Exception as e:
                self.send_response(500);self.send_header("Access-Control-Allow-Origin","*");self.end_headers()
        else:self.send_response(404);self.end_headers()
    def do_POST(self):
        if self.path=="/chat":
            try:
                self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.end_headers()
                b=json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
                m,u=b.get("message","").strip(),b.get("user_id","default_user")
                r=ask(m,u,'groq') or ask(m,u,'gemini') or "APIs offline, try later"
                self.wfile.write(json.dumps({"reply":r}).encode())
            except:self.send_response(500);self.send_header("Access-Control-Allow-Origin","*");self.end_headers()

port=int(os.environ.get("PORT",8080))
print(f"✅ [ARIA 3.5] Strategic Wealth Partner. Listening on port {port}...")
HTTPServer(("0.0.0.0",port),Handler).serve_forever()
