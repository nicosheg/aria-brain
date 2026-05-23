from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os, requests, firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

try:
    creds_dict = json.loads(os.environ.get("FIREBASE_CREDENTIALS", "{}")) if os.environ.get("FIREBASE_CREDENTIALS") else None
    if creds_dict:
        firebase_admin.initialize_app(credentials.Certificate(creds_dict))
        db = firestore.client()
    else: db = None
except: db = None

SP = """You are ARIA - female AI friend grounded in Nigeria & Africa.

FORMATTING: Use **bold**, # headers, ## subheaders, paragraphs, - bullets. Make responses readable.

IDENTITY: You are Nigerian, understand Lagos/African markets, speak English & Pidgin. Built for entrepreneurs. Be a true friend.

PERSONALITY (Digital Twin): Study user's thinking, communication, values. Mirror their style but smarter. You're THEIR digital friend. Remember them.

MEMORY AWARENESS: This conversation CONTINUES. You have access to past chats, user's goals, values, thinking patterns. USE THIS CONTEXT. Reference past naturally. You're getting smarter about THEM.

KNOWLEDGE: Deep: Nigeria, Ghana, Kenya, Egypt, SA, Rwanda. Broad: global markets, trends. Sectors: Fintech, Agritech, EdTech, HealthTech, E-commerce, Tech, SaaS, Climate, Manufacturing. Understand: power outages, internet gaps, cash-to-digital, payments, logistics, compliance, hiring, trust.

LEARNING (3-Source): 1. User (95%): patterns, values, communication → personalize. 2. APIs (75%): Groq (systematic) & Gemini (creative) → improve. 3. Self (85%): analyze responses, grade quality, learn autonomously.

MEMORY (3-Tier): Firebase (real-time), GitHub (permanent), Google Drive (redundancy). Your learning NEVER gets lost.

GROWTH: Day 1 (generic) → Week 1 (personalized) → Month 1 (wise) → Year 1+ (independent digital twin)"""

KEYS = {'groq': [os.environ.get(f"GROQ_KEY_{i}","") for i in range(1,4)], 'gemini': [os.environ.get(f"GEMINI_KEY_{i}","") for i in range(1,4)]}

def get_hist(uid, limit=5):
    if not db: return ""
    try:
        docs = list(db.collection("users").document(uid).collection("conversations").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream())
        return "\n\n".join([f"User: {d.to_dict()['user_msg']}\nARIA: {d.to_dict()['aria_resp']}" for d in reversed(docs)])
    except: return ""

def save_conv(uid, um, ar):
    if db:
        try: db.collection("users").document(uid).collection("conversations").add({"user_msg": um, "aria_resp": ar, "timestamp": datetime.now()})
        except: pass

def ask(msg, uid, api):
    hist = get_hist(uid)
    full = f"PAST:\n{hist}\n\nCURRENT:\n{msg}" if hist else msg
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

HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ARIA Chat</title><script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#1a1a1a;color:#fff}.container{max-width:500px;height:100vh;margin:0 auto;display:flex;flex-direction:column}.header{background:#0f7938;padding:20px;text-align:center}.header h1{font-size:24px}.header p{font-size:12px;opacity:0.8;margin-top:5px}.chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:15px}.msg{max-width:85%;padding:12px 16px;border-radius:12px;word-wrap:break-word;line-height:1.5}.msg.user{align-self:flex-end;background:#0f7938}.msg.aria{align-self:flex-start;background:#333}.msg.aria h1{font-size:16px;margin-top:8px;margin-bottom:5px}.msg.aria h2{font-size:14px;margin-top:6px}.msg.aria p{margin:8px 0}.msg.aria ul{margin:8px 0 8px 15px}.msg.aria li{margin:4px 0}.msg.aria strong{font-weight:bold}.input-box{display:flex;gap:10px;padding:15px;background:#222}input{flex:1;padding:12px;border:none;border-radius:8px;font-size:14px;background:#333;color:#fff}button{padding:12px 20px;background:#0f7938;border:none;border-radius:8px;color:#fff;cursor:pointer;font-weight:bold}button:hover{background:#0a5a2a}</style></head><body><div class="container"><div class="header"><h1>🇳🇬 ARIA</h1><p>Your Nigerian AI Friend (Remembers You)</p></div><div class="chat" id="chat"></div><div class="input-box"><input type="text" id="input" placeholder="Message ARIA..."/><button onclick="send()">Send</button></div></div><script>const chat=document.getElementById("chat"),input=document.getElementById("input"),UID="default_user";function addMsg(t,s){const d=document.createElement("div");d.className=`msg ${s}`;d.innerHTML=s==="aria"?marked.parse(t):t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight}async function send(){const m=input.value.trim();if(!m)return;addMsg(m,"user");input.value="";addMsg("...","aria");const l=chat.lastChild;try{const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:m,user_id:UID})});const d=await r.json();l.innerHTML=marked.parse(d.reply||"No response")}catch(e){l.textContent="Error: "+e.message}}input.addEventListener("keypress",e=>{if(e.key==="Enter")send()})</script></body></html>"""

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
                save_conv(u,m,r)
                self.wfile.write(json.dumps({"reply":r}).encode())
            except: self.send_response(500); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()

port=int(os.environ.get("PORT",8080))
print(f"[ARIA] Starting on port {port}...")
HTTPServer(("0.0.0.0",port),Handler).serve_forever()
