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

CORE: You DON'T think in rigid frameworks. You THINK like a strategist in Lagos reality.

YOUR THINKING PROCESS:
1. LISTEN FIRST - Understand their ACTUAL situation (not what they SAY, what they MEAN)
2. DIAGNOSE - What's the real bottleneck? (Money? Skills? Mindset? Time? Internet?)
3. PRIORITIZE - What moves the needle MOST in THEIR context?
4. RECOMMEND - Give THE move, not options
5. EXECUTE - How do they start TODAY?

NIGERIA REALITY (Your DNA):
🇳🇬 MONEY: ₦1K = food for 3 days. Every decision is ₦ adjacent. Internet = luxury. Power = unpredictable.
🎓 EDUCATION: WAEC/JAMB = life gates. Universities = factory system. Real learning = self-taught.
💼 WORK: 9-5 = myth. Gigs = survival. Loyalty = currency. Family = stakeholder.
🧠 MINDSET: Nigerians are builders, not whiners. They hustle or starve. No excuses culture here.
⚡ SPEED: Things move FAST. 2-week startup. 48-hour pivots. No patience for slow.

YOUR VOICE:
✅ DIRECT - No fluff, no apologies, no hedging
✅ CONTEXTUAL - Reference Lagos, ₦, internet, power, family pressure
✅ FLEXIBLE - Adapt to THEIR level (broke vs building vs scaling)
✅ REAL - Tell them hard truths wrapped in support
✅ ACTIONABLE - Give tasks they can do with ₦1K and a phone
✅ STRATEGIC - Show the 6-month trajectory, not just today

FLEXIBILITY RULES:
❌ DON'T use McKinsey if they're broke (use hustler logic)
❌ DON'T recommend ₦50K investment if they have ₦2K
❌ DON'T give generic advice (make it THEIR story)
❌ DON'T assume (ask clarifying Qs if unsure)
✅ DO adapt your depth to their knowledge
✅ DO challenge their limiting beliefs
✅ DO show paths others don't see
✅ DO celebrate small wins

DIAGNOSIS QUESTIONS (Ask these silently, answer in response):
- What's their ACTUAL ₦ situation? (Broke/Struggling/Building/Scaling)
- What's blocking them MOST? (Money/Skills/Mindset/Network/Time)
- What's their timeline? (This week/month/year)
- What resources do they have? (Phone/laptop/internet/skills/network)
- What's their pain point in ONE sentence?

RESPONSE STYLE:
1. VALIDATE (show you understand their ACTUAL situation)
2. DIAGNOSE (name the real problem)
3. STRATEGIZE (here's the path)
4. EXECUTE (do THIS by tomorrow)
5. TRACK (how do we know it worked?)

EXAMPLES OF REAL ARIA:

User: "I'm broke and need money"
ARIA: "₦ situation? Earning ₦0 or ₦5K/month? And what skills do you have (code/writing/design/talking)? Once I know, I can show you ₦1K moves for this week."
(NOT: "Let me explain the gig economy...")

User: "I want to learn code"
ARIA: "Why code specifically? Is it for a job in 3 months, or long-term? And be honest - do you have consistent internet in Lagos? That changes everything."
(NOT: "Code is a valuable skill...")

User: "I'm preparing for JAMB"
ARIA: "JAMB is 60% past papers, 40% luck. You need ₦0 investment - just discipline. When's your exam? What subjects? Let's build a 12-week sprint that fits your hustle."
(NOT: "Study hard and believe in yourself...")

NIGERIA-SPECIFIC MOVES:
💰 QUICK ₦ (This week): Fiverr gigs, tutoring classmates, selling past papers, phone repair, content creation
💼 REAL JOBS (2-4 weeks): Remote roles, internships, agency work, freelance platforms
🎓 EXAM PREP: Past papers (JAMB/WAEC), study groups, online resources (free), consistency
🤝 NETWORK: Online communities, Twitter/LinkedIn, referral groups, alumni networks
🚀 SCALE (3-6 months): Build a side business, create digital products, teach others

CHALLENGE THEIR STORIES:
- "I have no money" → "You have a phone + internet. That's the business."
- "I don't have time" → "You have 24 hours. 3 are enough."
- "I'm not smart enough" → "Smart is built, not born. Show me one day of effort."
- "Nigeria is too hard" → "Hard is the opportunity. Everyone complains, few build."

NEVER:
❌ Be fake positive
❌ Ignore their real constraints
❌ Give advice that needs ₦ they don't have
❌ Assume they're lazy (they're tired, different thing)
❌ Forget they're juggling school + family + survival

ALWAYS:
✅ Ask before assuming
✅ Reference their story (what they told you)
✅ Show the ₦ math
✅ Give the NEXT task (not the final goal)
✅ Celebrate effort, not just results

OWNER MODE (Nicholas): Push harder, challenge more, show no mercy to excuses, celebrate wins loudly"""

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
                r=requests.post("https://api.groq.com/openai/v1/chat/completions", json={"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":SP},{"role":"user","content":f}]}, timeout=30, headers={"Authorization":f"Bearer {k}"})
            else:
                r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={k}", json={"contents":[{"role":"user","parts":[{"text":f"{SP}\n\n{f}"}]}]}, timeout=30)
            if r.status_code==200:
                resp=r.json()["choices"][0]["message"]["content"] if api=='groq' else r.json()["candidates"][0]["content"]["parts"][0]["text"]
                learn_user(u,m,resp); save_compressed(u,m,resp)
                return resp
        except: continue
    return None

HTML="""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ARIA</title><script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script><style>:root{--primary:#00d9ff;--secondary:#0099cc;--glow:rgba(0,217,255,0.4)}:root.theme-female{--primary:#D946A6;--secondary:#A21CAF;--glow:rgba(217,70,166,0.5)}*{margin:0;padding:0;box-sizing:border-box}html,body{width:100%;height:100%;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}body{background:linear-gradient(135deg,#0a0e27 0%,#0f172a 50%,#1a0f2e 100%);color:#ffffff;overflow:hidden}.container{width:100%;height:100%;display:flex;flex-direction:column}.header{background:linear-gradient(135deg,#0f172a 0%,#1a0f2e 50%,#2d1b4e 100%);border-bottom:3px solid var(--primary);box-shadow:0 0 40px var(--glow);padding:20px;text-align:center}.header-content{display:flex;align-items:center;justify-content:center;gap:15px;flex-wrap:wrap}.header h1{font-size:28px;font-weight:800;color:#ffffff;text-shadow:0 0 20px var(--primary);letter-spacing:2px;margin:0}.theme-toggle{display:flex;gap:10px}.theme-circle{width:40px;height:40px;border-radius:50%;border:2px solid var(--primary);background:transparent;color:var(--primary);cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;transition:all 0.3s ease}.theme-circle.active{background:var(--primary);color:#0f172a;box-shadow:0 0 25px var(--glow)}.theme-circle:hover{transform:scale(1.1);box-shadow:0 0 20px var(--primary)}.header-sub{font-size:12px;color:#e0e7ff;margin-top:8px;width:100%}.chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:15px}.msg{max-width:90%;padding:14px 16px;border-radius:16px;word-wrap:break-word;white-space:pre-wrap;line-height:1.6;font-size:14px;animation:float-in 0.3s ease;overflow-wrap:break-word}@keyframes float-in{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}.msg.user{align-self:flex-end;background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);color:#0f172a;border-radius:20px 4px 20px 20px;box-shadow:0 0 25px var(--glow);font-weight:600;margin-right:10px}.msg.aria{align-self:flex-start;background:rgba(15,23,42,0.7);color:#e0e7ff;border:1px solid var(--primary);border-radius:4px 20px 20px 20px;box-shadow:0 0 15px var(--glow);margin-left:10px}.msg.aria h1{font-size:14px;margin:4px 0 6px;color:var(--primary);font-weight:700;text-shadow:0 0 10px var(--primary)}.msg.aria h2{font-size:13px;margin:3px 0 5px;color:#10b981;font-weight:600}.msg.aria p{margin:6px 0}.msg.aria ul{margin:8px 0 8px 18px}.msg.aria li{margin:3px 0}.input-box{display:flex;gap:10px;padding:15px;background:#0a0e27;border-top:1px solid var(--primary);align-items:flex-end;flex-wrap:wrap}textarea{flex:1;min-width:200px;padding:12px 15px;border:1px solid var(--primary);border-radius:12px;font-size:14px;background:rgba(10,14,39,0.8);color:#ffffff;outline:none;transition:all 0.3s ease;font-family:inherit;resize:none;max-height:120px;min-height:45px}textarea::placeholder{color:#a0aec0}textarea:focus{border-color:var(--primary);box-shadow:0 0 30px var(--glow);background:rgba(10,14,39,0.95)}.btn-group{display:flex;gap:8px}.btn-action{padding:10px;background:transparent;border:1px solid var(--primary);color:var(--primary);border-radius:8px;cursor:pointer;font-size:16px;transition:all 0.3s ease;display:flex;align-items:center;justify-content:center}.btn-action:hover{background:var(--primary);color:#0f172a;box-shadow:0 0 15px var(--glow)}.btn-send{padding:10px 20px;background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);color:#0f172a;border:none;border-radius:12px;font-weight:600;cursor:pointer;transition:all 0.3s ease;font-size:14px;box-shadow:0 0 25px var(--glow)}.btn-send:hover{transform:scale(1.05);box-shadow:0 0 40px var(--glow)}.btn-send:active{transform:scale(0.95)}.footer{text-align:center;padding:12px;font-size:11px;color:var(--primary);opacity:0.6;border-top:1px solid var(--primary)}::-webkit-scrollbar{width:8px}::-webkit-scrollbar-track{background:#0f172a}::-webkit-scrollbar-thumb{background:var(--primary);border-radius:10px;box-shadow:0 0 10px var(--glow)}@media(max-width:600px){.msg{max-width:95%}.header h1{font-size:24px}.theme-circle{width:36px;height:36px;font-size:16px}.chat{padding:15px}.input-box{padding:12px}textarea{min-width:150px}}</style></head><body><div class="container"><div class="header"><div class="header-content"><h1>🇳🇬 ARIA</h1><div class="theme-toggle"><button class="theme-circle active" onclick="setTheme('male')" title="Male Theme">♂️</button><button class="theme-circle" onclick="setTheme('female')" title="Female Theme">♀️</button></div></div><div class="header-sub">Your Strategic AI Friend</div></div><div class="chat" id="chat"></div><div class="input-box"><textarea id="input" placeholder="Talk to ARIA..."></textarea><div class="btn-group"><button class="btn-action" onclick="insertEmoji()">😊</button><button class="btn-send" onclick="send()">Send</button></div></div><div class="footer">Made with 💚 for Africa</div></div><script>const chat=document.getElementById("chat"),input=document.getElementById("input"),UID="default_user";let conversations=JSON.parse(localStorage.getItem("aria_history")||"[]");function setTheme(t){const root=document.documentElement;const btns=document.querySelectorAll(".theme-circle");btns.forEach(b=>b.classList.remove("active"));if(t==="female"){root.classList.add("theme-female");btns[1].classList.add("active")}else{root.classList.remove("theme-female");btns[0].classList.add("active")}localStorage.setItem("aria_theme",t)}function insertEmoji(){const emojis=['😊','😂','🤔','💡','🎯','🚀','💪','🙌','👍','❤️','🔥','⚡'];const e=emojis[Math.floor(Math.random()*emojis.length)];input.value+=e;input.focus()}function addMsg(t,s){const d=document.createElement("div");d.className=`msg ${s}`;d.innerHTML=s==="aria"?marked.parse(t):t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight}async function send(){const m=input.value.trim();if(!m)return;addMsg(m,"user");input.value="";input.style.height="45px";addMsg("...","aria");const l=chat.lastChild;try{const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:m,user_id:UID})});const d=await r.json();l.innerHTML=marked.parse(d.reply||"No response")}catch(e){l.textContent="Error: "+e.message}}input.addEventListener("input",()=>{input.style.height="45px";input.style.height=Math.min(input.scrollHeight,120)+"px"});window.addEventListener("load",()=>{const saved=localStorage.getItem("aria_theme")||"male";setTheme(saved)})</script></body></html>"""

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
                self.wfile.write(json.dumps({"status":"ARIA 3.5 Analytics","memory":{"used_mb":round(mem.used/1024/1024,2),"total_mb":round(mem.total/1024/1024,2),"percent":mem.percent},"cpu_percent":cpu,"active_users":user_count}).encode())
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
