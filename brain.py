from http.server import HTTPServer, BaseHTTPRequestHandler
import json, datetime, urllib.request, os
import pytz

# Load from .aria-config
for line in open(os.path.expanduser('~/.aria-config')).readlines():
    if '=' in line and not line.startswith('#'):
        key, val = line.split('=', 1)
        os.environ[key.strip()] = val.strip()

GROQ_KEYS = [os.environ.get(f"GROQ_KEY_{i+1}", "") for i in range(5)]
GEMINI_KEYS = [os.environ.get(f"GEMINI_KEY_{i+1}", "") for i in range(5)]

print("[LOADED] Groq:", len([k for k in GROQ_KEYS if k]), "Gemini:", len([k for k in GEMINI_KEYS if k]))

def get_lagos_time():
    return datetime.datetime.now(pytz.timezone("Africa/Lagos")).strftime("%a %d %b %Y - %I:%M %p")

def ask_groq(message):
    for i, key in enumerate(GROQ_KEYS):
        if not key: 
            print(f"  [GROQ {i+1}] No key")
            continue
        try:
            print(f"  [GROQ {i+1}] Trying... key={key[:20]}...")
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps({"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": message}]}).encode(),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                result = json.loads(res.read())
                reply = result["choices"][0]["message"]["content"]
                print(f"  [GROQ {i+1}] ✓ SUCCESS")
                return reply
        except urllib.error.HTTPError as e:
            print(f"  [GROQ {i+1}] ✗ HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            print(f"  [GROQ {i+1}] ✗ Network: {e.reason}")
        except Exception as e:
            print(f"  [GROQ {i+1}] ✗ {type(e).__name__}: {str(e)[:50]}")
    print("  [GROQ] All failed")
    return None

def ask_gemini(message):
    for i, key in enumerate(GEMINI_KEYS):
        if not key: 
            print(f"  [GEMINI {i+1}] No key")
            continue
        try:
            print(f"  [GEMINI {i+1}] Trying... key={key[:20]}...")
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                data=json.dumps({"contents": [{"role": "user", "parts": [{"text": message}]}]}).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                result = json.loads(res.read())
                reply = result["candidates"][0]["content"]["parts"][0]["text"]
                print(f"  [GEMINI {i+1}] ✓ SUCCESS")
                return reply
        except urllib.error.HTTPError as e:
            print(f"  [GEMINI {i+1}] ✗ HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            print(f"  [GEMINI {i+1}] ✗ Network: {e.reason}")
        except Exception as e:
            print(f"  [GEMINI {i+1}] ✗ {type(e).__name__}: {str(e)[:50]}")
    print("  [GEMINI] All failed")
    return None

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        if self.path == "/chat":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                message = body.get("message", "").strip()
                
                print(f"\n[MSG] {message[:50]}")
                groq = ask_groq(message)
                gemini = ask_gemini(message)
                
                reply = groq or gemini or "APIs offline"
                print(f"[REPLY] {reply[:50]}\n")
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"reply": reply}).encode())
            except Exception as e:
                print(f"[ERROR] {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"reply": "Error"}).encode())

print("\n[STARTING] ARIA 8080 (DEBUG)...\n")
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
