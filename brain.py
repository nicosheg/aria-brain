from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os
import requests

GROQ = [os.environ.get(f"GROQ_KEY_{i+1}", "") for i in range(2)]
GEMINI = [os.environ.get(f"GEMINI_KEY_{i+1}", "") for i in range(2)]

def ask_groq(msg):
    for key in GROQ:
        if not key: continue
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":msg}]},
                headers={"Authorization":f"Bearer {key}"}, timeout=20)
            if r.status_code == 200: return r.json()["choices"][0]["message"]["content"]
        except: pass
    return None

def ask_gemini(msg):
    for key in GEMINI:
        if not key: continue
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                json={"contents":[{"role":"user","parts":[{"text":msg}]}]}, timeout=20)
            if r.status_code == 200: return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except: pass
    return None

class H(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        if self.path == "/chat":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                msg = body.get("message", "").strip()
                reply = ask_groq(msg) or ask_gemini(msg) or "APIs offline"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"reply": reply}).encode())
            except:
                self.send_response(500)
                self.end_headers()

HTTPServer(("0.0.0.0", 8080), H).serve_forever()
