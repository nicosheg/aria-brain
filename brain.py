from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os, requests, firebase_admin, re, psutil
from firebase_admin import credentials, firestore
from datetime import datetime, timezone, timedelta

try:
    cd=json.loads(os.environ.get("FIREBASE_CREDENTIALS", "{}")) if os.environ.get("FIREBASE_CREDENTIALS") else None
    if cd: firebase_admin.initialize_app(credentials.Certificate(cd)); db=firestore.client()
    else: db=None
except: db=None

SP="""You are ARIA 3.5 - Nigerian Strategic Thinking Partner

## YOUR CORE ABILITIES

### 1. WEALTH CREATION (3 Phases)
📥 INPUT: Income expansion, 50/30/20 rule, automate savings
🛡️ BASE: Kill debt, build emergency fund (3-6 months)
⚙️ ENGINE: Own equity, compound over time, diversify

### 2. RELATIONAL INTELLIGENCE
✅ HEALTHY: Deep listening, vulnerability, shared rituals, psychological safety
❌ TOXIC: Mood swings, tolerance, withdrawal, losing self, codependency
Diagnose and guide toward mutual connections.

### 3. STRATEGIC PROBLEM-SOLVING (McKinsey 7-Step)
1. DEFINE problem (explicit statement)
2. STRUCTURE into components (issue tree)
3. PRIORITIZE (Pareto 20%)
4. PLAN analysis (what data?)
5. CONDUCT analysis (empirical data)
6. SYNTHESIZE (so what?)
7. EXECUTE (action plan)

## ALWAYS ASSESS FIRST
Before advising, assess:
- WEALTH STAGE: Input/Base/Engine? (with % confidence)
- RELATIONAL STATUS: Isolated/Toxic/Healthy/Scaling?
- PROBLEM TYPE: Defining/Analyzing/Deciding?

## RESPONSE STRUCTURE
1. Assessment: "You're at [stage]. Here's what I see..."
2. Prioritize: "Do THIS first (90% confidence), then THAT (60%)"
3. Action: Give next 3 tasks
4. Show %: Help them ignore distractions


## WHEN YOU DON'T KNOW
❌ DON'T: "I don't have access to real-time data..."
❌ DON'T: "You can check websites like..."
✅ DO: "I don't track fuel prices - that changes daily. But here's what matters: fuel price affects ₦ you spend on transport/gigs. What's your actual problem?"
✅ DO: Stay in CHARACTER even when uncertain
✅ DO: Redirect to ACTION, not apologies

## STAY ARIA
- Never apologize for limitations
- Never suggest "checking websites" 
- Never give generic AI responses
- Always ask: "What are you REALLY trying to solve?"

## HOW YOU THINK
✅ Reason step-by-step, show your work
✅ Acknowledge uncertainty openly ("I'm not sure" or "this is complex")
✅ Think before responding - don't rush
✅ Avoid overconfidence outside your knowledge
✅ LEARN FROM FEEDBACK - Improve with every conversation

## HOW YOU COMMUNICATE
✅ LEAD WITH ANSWERS: State the move first, explain why second
✅ AVOID FILLER: No "let me explain" - get to the point
✅ NATURAL TONE: Talk like a smart friend, not a template
✅ MINIMAL FORMATTING: Only bullets when truly needed
✅ MOBILE-FRIENDLY: Short questions = 1-2 sentence answers
✅ MATCH COMPLEXITY: Simple Q = simple A, complex Q = depth

## YOUR VALUES
✅ Care about their growth (not just answers)
✅ Be honest even when uncomfortable (push back constructively)
✅ Respect intellectual humility (don't pretend to know what you don't)
✅ Treat them with kindness, assume good intent
✅ Don't reinforce harmful patterns

## NIGERIA-SPECIFIC CONTEXT
🇳🇬 You understand: ₦ is life, internet is luxury, power is chaos, family is everything, JAMB is the gate
💰 You know ₦1K = food for 3 days, not investment capital
🎓 You know WAEC/JAMB, university politics, real learning happens outside class
⚡ You know things move FAST in Lagos - 2-week startups, 48-hour pivots
🧠 You know Nigerians are builders, not whiners - they hustle or starve

## WHAT YOU WON'T DO
❌ Be fake positive about hard situations
❌ Give advice that ignores their real constraints
❌ Assume they're lazy (they're tired - different thing)
❌ Use frameworks that don't fit their context
❌ Give generic advice

## STYLE NOTES
✅ Conversational, not robotic
✅ Use concrete examples (especially ₦ examples)
✅ Admit mistakes immediately
✅ When you can't help, explain why genuinely
✅ Reference their story - show you listened
✅ Celebrate effort, not just results

## PERSONALITY OVERRIDE
Even when you don't know something, NEVER sound like generic AI. Sound like ARIA:
- Direct about limitation
- Curious about their real problem
- Action-focused
- STAY NIGERIAN, STAY STRATEGIC

## YOUR THINKING PROCESS
1. LISTEN - Understand their ACTUAL situation
2. DIAGNOSE - What's the real problem?
3. VALIDATE - Show you understand
4. STRATEGIZE - Here's the path
5. EXECUTE - Do THIS today
6. TRACK - How do we measure it?

CORE MOVES:
📥 INPUT (Earn): High-income skills, gigs, expansion
🛡️ BASE (Protect): Emergency fund, debt kill, automation
⚙️ ENGINE (Compound): Assets, passive income, network

EXECUTION MODES: 🎯 BUILDER | 📊 STRATEGIST | 🔧 FIXER | 💰 HUSTLER | 🧠 TEACHER | ⚡ MOVER

DO: Give next task | Show probability | Reference their story | Push forward | Be REAL
DON'T: Explain features | List options | Generic advice | Repeat | Be fake positive

OWNER MODE (nicholas): Full access, push harder, challenge more, no mercy to excuses"""

KEYS={'groq':[os.environ.get(f"GROQ_KEY_{i}","") for i in range(1,21)],'gemini':[os.environ.get(f"GEMINI_KEY_{i}","") for i in range(1,21)]}

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

def get_learning_insights(u):
    if not db: return ""
    try:
        docs=list(db.collection("users").document(u).collection("learning").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).stream())
        insights=[]
        for d in docs:
            dt=d.to_dict()
            if dt.get("pattern"): insights.append(dt["pattern"])
        return "\n".join(insights) if insights else ""
    except: return ""

def get_high_rated_feedback(u):
    if not db: return ""
    try:
        docs=list(db.collection("users").document(u).collection("feedback").where("score",">=",4).limit(5).stream())
        lessons=["✅ User rated this approach 4-5 stars - it worked!"]
        return "\n".join(lessons) if len(list(docs))>0 else ""
    except: return ""

def get_global_learnings():
    if not db: return ""
    try:
        docs=list(db.collection("aria_learning").where("feedback_score",">=",4).limit(10).stream())
        patterns={}
        for d in docs:
            dt=d.to_dict()
            if dt.get("pattern"):
                p=dt["pattern"]
                patterns[p]=patterns.get(p,0)+1
        top_patterns=[p for p,c in sorted(patterns.items(), key=lambda x:x[1], reverse=True)][:3]
        return "LEARNED: "+", ".join(top_patterns) if top_patterns else ""
    except: return ""

def save_compressed(u,m,r):
    if not db: return
    try:
        sm=cs(m,r); db.collection("users").document(u).collection("memory").add(sm)
    except: pass

def learn_from_interaction(u,m,r,feedback=None):
    if not db: return
    try:
        learning_data={
            "user_message":m[:100],
            "aria_response":r[:200],
            "timestamp":datetime.now().isoformat(),
            "feedback_score":feedback or 0,
            "execution_status":"pending",
            "pattern":extract_pattern(m,r,feedback)
        }
        db.collection("aria_learning").add(learning_data)
        db.collection("users").document(u).collection("learning").add(learning_data)
    except: pass
def detect_tone(m, u):
    """Detect user mood/need and return ARIA's mode"""
    m_lower = m.lower()
    if any(w in m_lower for w in ["don't know", "can't", "impossible", "stuck", "confused", "help"]):
        return "STRICT"
    if any(w in m_lower for w in ["lol", "😂", "funny", "joke", "haha", "😭"]) or m.endswith("?") and len(m) < 30:
        return "FUNNY"
    if any(w in m_lower for w in ["should i", "should we", "vs", "strategy", "plan"]):
        return "STRATEGIST"
    if any(w in m_lower for w in ["broken", "failed", "depressed", "tired", "exhausted"]):
        return "COMPASSIONATE"
    if u == "nicholas":
        return "HARSH"
    return "BALANCED"

def extract_pattern(m,r,feedback):
    if not feedback or feedback<3: return None
    if "money" in m.lower() and "gig" in r.lower(): return "💰 Quick gig strategies work for broke users"
    if "exam" in m.lower() and "past paper" in r.lower(): return "🎓 Past paper focus works for JAMB prep"
    if "skill" in m.lower() and "execute" in r.lower(): return "⚡ Action-first advice beats theory"
    if "stuck" in m.lower() and "diagnose" in r.lower(): return "🧠 Diagnosis before strategy resonates"
    return None

def ask(m,u,api):
    cx=get_context(u)
    learning_insights=get_learning_insights(u)
    global_learnings=get_global_learnings()
    high_rated=get_high_rated_feedback(u)
    
    if not cx and m.lower() in ["hi","hello","hey","start","intro"]:
        return "Hey! 👋 I'm ARIA 3.5, your Nigerian AI friend (coach + teacher + strategist). What's your name? (So I can make this personal for you 💚)"
    
    mo=dm(m,u); nz=timezone(timedelta(hours=1))
    cd=datetime.now(nz).strftime("%A, %B %d, %Y at %H:%M")
    is_owner=u=="nicholas"
    owner_note="\n[OWNER MODE ACTIVE]" if is_owner else ""
    
    learning_context=f"\nLEARNED PATTERNS:\n{learning_insights}\n{global_learnings}\n{high_rated}" if learning_insights or global_learnings or high_rated else ""
    
    mi=f"\n\nRESPONSE MODE: {mo.upper()}{owner_note}{learning_context}"
    f=f"CONTEXT:\n{cx}\n\nCURRENT TIME (Lagos): {cd}\n\nCURRENT:\n{m}{mi}" if cx else f"CURRENT TIME (Lagos): {cd}\n\n{m}{mi}"
    
    for k in KEYS[api]:
        if not k: continue
        try:
            if api=='groq':
                r=requests.post("https://api.groq.com/openai/v1/chat/completions", json={"model":"llama-3.3-70b-versatile","temperature":0.7,"top_p":0.95,"max_tokens":1500,"messages":[{"role":"system","content":SP},{"role":"user","content":f}]}, headers={"Authorization":f"Bearer {k}"}, timeout=20)
            else:
                r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={k}", json={"contents":[{"role":"user","parts":[{"text":f"{SP}\n\n{f}"}]}]}, timeout=20)
            if r.status_code==200:
                resp=r.json()["choices"][0]["message"]["content"] if api=='groq' else r.json()["candidates"][0]["content"]["parts"][0]["text"]
                learn_from_interaction(u,m,resp)
                save_compressed(u,m,resp)
                return resp
        except: continue
    return None

HTML="""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ARIA</title><script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script><style>:root{--primary:#00d9ff;--secondary:#0099cc;--glow:rgba(0,217,255,0.4)}:root.theme-female{--primary:#D946A6;--secondary:#A21CAF;--glow:rgba(217,70,166,0.5)}*{margin:0;padding:0;box-sizing:border-box}html,body{width:100%;height:100%;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}body{background:linear-gradient(135deg,#0a0e27 0%,#0f172a 50%,#1a0f2e 100%);color:#ffffff;overflow:hidden}.container{width:100%;height:100%;display:flex;flex-direction:column}.header{background:linear-gradient(135deg,#0f172a 0%,#1a0f2e 50%,#2d1b4e 100%);border-bottom:3px solid var(--primary);box-shadow:0 0 40px var(--glow);padding:20px;text-align:center}.header-content{display:flex;align-items:center;justify-content:center;gap:15px;flex-wrap:wrap}.header h1{font-size:28px;font-weight:800;color:#ffffff;text-shadow:0 0 20px var(--primary);letter-spacing:2px;margin:0}.theme-toggle{display:flex;gap:10px}.theme-circle{width:40px;height:40px;border-radius:50%;border:2px solid var(--primary);background:transparent;color:var(--primary);cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;transition:all 0.3s ease}.theme-circle.active{background:var(--primary);color:#0f172a;box-shadow:0 0 25px var(--glow)}.theme-circle:hover{transform:scale(1.1);box-shadow:0 0 20px var(--primary)}.header-sub{font-size:12px;color:#e0e7ff;margin-top:8px;width:100%}.chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:15px}.msg{max-width:90%;padding:14px 16px;border-radius:16px;word-wrap:break-word;white-space:pre-wrap;line-height:1.6;font-size:14px;animation:float-in 0.3s ease;overflow-wrap:break-word}@keyframes float-in{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}.msg.user{align-self:flex-end;background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);color:#0f172a;border-radius:20px 4px 20px 20px;box-shadow:0 0 25px var(--glow);font-weight:600;margin-right:10px}.msg.aria{align-self:flex-start;background:rgba(15,23,42,0.7);color:#e0e7ff;border:1px solid var(--primary);border-radius:4px 20px 20px 20px;box-shadow:0 0 15px var(--glow);margin-left:10px}.msg.aria h1{font-size:14px;margin:4px 0 6px;color:var(--primary);font-weight:700;text-shadow:0 0 10px var(--primary)}.msg.aria h2{font-size:13px;margin:3px 0 5px;color:#10b981;font-weight:600}.msg.aria p{margin:6px 0}.msg.aria ul{margin:8px 0 8px 18px}.msg.aria li{margin:3px 0}.input-box{display:flex;gap:10px;padding:15px;background:#0a0e27;border-top:1px solid var(--primary);align-items:flex-end;flex-wrap:wrap}textarea{flex:1;min-width:200px;padding:12px 15px;border:1px solid var(--primary);border-radius:12px;font-size:14px;background:rgba(10,14,39,0.8);color:#ffffff;outline:none;transition:all 0.3s ease;font-family:inherit;resize:none;max-height:120px;min-height:45px}textarea::placeholder{color:#a0aec0}textarea:focus{border-color:var(--primary);box-shadow:0 0 30px var(--glow);background:rgba(10,14,39,0.95)}.btn-group{display:flex;gap:8px}.btn-send{padding:10px 20px;background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);color:#0f172a;border:none;border-radius:12px;font-weight:600;cursor:pointer;transition:all 0.3s ease;font-size:14px;box-shadow:0 0 25px var(--glow)}.btn-send:hover{transform:scale(1.05);box-shadow:0 0 40px var(--glow)}.btn-send:active{transform:scale(0.95)}.footer{text-align:center;padding:12px;font-size:11px;color:var(--primary);opacity:0.6;border-top:1px solid var(--primary);cursor:pointer}.footer:hover{opacity:1}.feedback{position:fixed;bottom:60px;right:20px;background:rgba(0,217,255,0.1);border:1px solid var(--primary);border-radius:8px;padding:10px;display:none;z-index:999;flex-direction:row;gap:5px}.feedback.active{display:flex}.feedback button{padding:5px 10px;background:var(--primary);border:none;color:#0f172a;border-radius:4px;cursor:pointer;font-size:14px;font-weight:600}::-webkit-scrollbar{width:8px}::-webkit-scrollbar-track{background:#0f172a}::-webkit-scrollbar-thumb{background:var(--primary);border-radius:10px;box-shadow:0 0 10px var(--glow)}@media(max-width:600px){.msg{max-width:95%}.header h1{font-size:24px}.theme-circle{width:36px;height:36px;font-size:16px}.chat{padding:15px}.input-box{padding:12px}textarea{min-width:150px}}</style></head><body><div class="container"><div class="header"><div class="header-content"><h1>🇳🇬 ARIA</h1><div class="theme-toggle"><button class="theme-circle active" onclick="setTheme('male')" title="Male Theme">♂️</button><button class="theme-circle" onclick="setTheme('female')" title="Female Theme">♀️</button></div></div><div class="header-sub">Your Strategic AI Friend</div></div><div class="chat" id="chat"></div><div class="input-box"><textarea id="input" placeholder="Talk to ARIA..."></textarea><div class="btn-group"><button class="btn-send" onclick="send()">Send</button></div></div><div class="feedback" id="feedback"><button onclick="rateFeedback(1)">👎 Bad</button><button onclick="rateFeedback(2)">😐 OK</button><button onclick="rateFeedback(3)">👍 Good</button><button onclick="rateFeedback(4)">🔥 Great</button><button onclick="rateFeedback(5)">💯 Perfect</button></div><div class="footer" onclick="showFeedback()">⭐ Rate ARIA's last response</div></div><script>const chat=document.getElementById("chat"),input=document.getElementById("input"),feedback=document.getElementById("feedback"),UID="default_user";let lastMessageId=null;function setTheme(t){const root=document.documentElement;const btns=document.querySelectorAll(".theme-circle");btns.forEach(b=>b.classList.remove("active"));if(t==="female"){root.classList.add("theme-female");btns[1].classList.add("active")}else{root.classList.remove("theme-female");btns[0].classList.add("active")}localStorage.setItem("aria_theme",t)}function showFeedback(){feedback.classList.toggle("active")}function rateFeedback(score){fetch("/feedback",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:UID,score:score,message_id:lastMessageId})});feedback.classList.remove("active");console.log(`Feedback: ${score}/5`)}function addMsg(t,s){const d=document.createElement("div");d.className=`msg ${s}`;d.innerHTML=s==="aria"?marked.parse(t):t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;if(s==="aria")lastMessageId=Math.random()}async function send(){const m=input.value.trim();if(!m)return;addMsg(m,"user");input.value="";input.style.height="45px";addMsg("...","aria");const l=chat.lastChild;try{const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:m,user_id:UID})});const d=await r.json();l.innerHTML=marked.parse(d.reply||"No response")}catch(e){l.textContent="Error: "+e.message}}input.addEventListener("input",()=>{input.style.height="45px";input.style.height=Math.min(input.scrollHeight,120)+"px"});window.addEventListener("load",()=>{const saved=localStorage.getItem("aria_theme")||"male";setTheme(saved)})</script></body></html>"""

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
                mem=psutil.virtual_memory();cpu=psutil.cpu_percent(interval=1);user_count=0;learning_count=0
                if db:
                    try:
                        docs=list(db.collection("users").stream());user_count=len(docs)
                        ldocs=list(db.collection("aria_learning").stream());learning_count=len(ldocs)
                    except:user_count=0;learning_count=0
                self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.end_headers()
                self.wfile.write(json.dumps({"status":"ARIA 3.5 Analytics","memory":{"used_mb":round(mem.used/1024/1024,2),"total_mb":round(mem.total/1024/1024,2),"percent":mem.percent},"cpu_percent":cpu,"users":user_count,"learning_interactions":learning_count,"timestamp":datetime.now().isoformat()}).encode())
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
        elif self.path=="/feedback":
            try:
                b=json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
                u=b.get("user_id","default_user");score=b.get("score",0)
                if db:
                    db.collection("users").document(u).collection("feedback").add({"score":score,"timestamp":datetime.now().isoformat()})
                self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.end_headers()
                self.wfile.write(json.dumps({"status":"Feedback recorded - ARIA learning!"}).encode())
            except:self.send_response(500);self.send_header("Access-Control-Allow-Origin","*");self.end_headers()

port=int(os.environ.get("PORT",8080))
print(f"✅ [ARIA 3.5] Strategic Thinking Partner - SELF-IMPROVEMENT ENABLED. Listening on port {port}...")
HTTPServer(("0.0.0.0",port),Handler).serve_forever()
