from http.server import HTTPServer, BaseHTTPRequestHandler
import json, datetime, urllib.request, time, os, re
import pytz, firebase_admin
from firebase_admin import credentials, firestore

GEMINI_KEYS = [os.environ.get(f"GEMINI_KEY_{i+1}", "") for i in range(5)]
GROQ_KEYS = [os.environ.get(f"GROQ_KEY_{i+1}", "") for i in range(5)]
MY_NUMBER = os.environ.get("MY_NUMBER", "")
MY_LID = os.environ.get("MY_LID", "")

db = None
try:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS", "")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
except:
    pass

def get_lagos_time():
    return datetime.datetime.now(pytz.timezone("Africa/Lagos")).strftime("%a %d %b %Y - %I:%M %p")

def ask_groq(message):
    for key in GROQ_KEYS:
        if not key: continue
        try:
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps({"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": message}]}).encode(),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read())["choices"][0]["message"]["content"]
        except: continue
    return None

def ask_gemini(message):
    for key in GEMINI_KEYS:
        if not key: continue
        try:
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                data=json.dumps({"contents": [{"role": "user", "parts": [{"text": message}]}]}).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read())["candidates"][0]["content"]["parts"][0]["text"]
        except: continue
    return None

def save_memory(sender, role, content):
    if not db or not content: return
    try:
        today = datetime.datetime.now(pytz.timezone("Africa/Lagos")).strftime("%Y_%m_%d")
        db.collection("aria_temporary").document(today).set({
            "date": today,
            "messages": firestore.ArrayUnion([{
                "timestamp": get_lagos_time(),
                "sender": sender,
                "role": role,
                "content": content[:1000]
            }])
        }, merge=True)
    except: pass

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    
    def do_POST(self):
        if self.path == "/chat":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                sender = body.get("sender", "").strip()
                message = body.get("message", "").strip()
                
                if not sender or not message:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"reply": ""}).encode())
                    return
                
                save_memory(sender, "user", message)
                
                groq_reply = ask_groq(message)
                gemini_reply = ask_gemini(message)
                
                if groq_reply and gemini_reply:
                    reply = f"[GROQ]\n{groq_reply[:300]}\n\n[GEMINI]\n{gemini_reply[:300]}"
                elif groq_reply:
                    reply = groq_reply
                elif gemini_reply:
                    reply = gemini_reply
                else:
                    reply = "APIs offline"
                
                save_memory(sender, "assistant", reply)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"reply": reply}).encode())
            except:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"reply": "Error"}).encode())

PORT = int(os.environ.get("PORT", 8080))
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
