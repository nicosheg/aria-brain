from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os
import requests

# Get your 2 API keys
GROQ_KEY_1 = os.environ.get("GROQ_KEY_1", "")
GROQ_KEY_2 = os.environ.get("GROQ_KEY_2", "")
GEMINI_KEY_1 = os.environ.get("GEMINI_KEY_1", "")
GEMINI_KEY_2 = os.environ.get("GEMINI_KEY_2", "")

# Try Groq
def ask_groq(message):
    for key in [GROQ_KEY_1, GROQ_KEY_2]:
        if not key: continue
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": message}]},
                headers={"Authorization": f"Bearer {key}"},
                timeout=20
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
        except:
            continue
    return None

# Try Gemini
def ask_gemini(message):
    for key in [GEMINI_KEY_1, GEMINI_KEY_2]:
        if not key: continue
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                json={"contents": [{"role": "user", "parts": [{"text": message}]}]},
                timeout=20
            )
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except:
            continue
    return None

# Handle incoming messages
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    
    def do_POST(self):
        if self.path == "/chat":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                message = body.get("message", "").strip()
                
                # Try Groq first, then Gemini
                reply = ask_groq(message) or ask_gemini(message) or "APIs offline"
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"reply": reply}).encode())
            except:
                self.send_response(500)
                self.end_headers()

# Start server
port = int(os.environ.get("PORT", 8080))
print(f"[ARIA] Starting on port {port}...")
HTTPServer(("0.0.0.0", port), Handler).serve_forever()
