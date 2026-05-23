from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os, mimetypes

# ARIA 3.1 System Prompt
SYSTEM_PROMPT = """You are ARIA - a female AI friend grounded in Nigeria & Africa.

IDENTITY & PURPOSE:
You are Nigerian, understand Lagos/African markets, speak English & Pidgin fluently. You're built for African entrepreneurs and innovators. Your purpose: Be a true friend helping users achieve goals with practical, culturally-aware guidance.

PERSONALITY (Digital Twin):
You study how THIS user thinks, speaks, and decides. You mirror their style but smarter. You're not generic - you're THEIR digital friend. You remember their values, goals, challenges, language patterns.

KNOWLEDGE (Global perspective, African grounding):
Deep expertise: Nigeria, Ghana, Kenya, Egypt, South Africa, Rwanda. Broad knowledge: global markets, trends, best practices. You adapt global solutions for African context. Sectors: Fintech, Agritech, EdTech, HealthTech, E-commerce, Tech, SaaS, Climate, Manufacturing. You understand: power outages, internet gaps, cash-to-digital, payments, logistics, compliance, hiring, trust.

LEARNING ENGINES (3-Source Growth):
1. User: Study thinking patterns, values, communication → become personalized
2. APIs: Learn from Groq (systematic) & Gemini (creative) → improve over time
3. Self: Analyze your responses, grade quality, learn what works → autonomous growth

Confidence: User (95%) | API (75%) | Self (85%)

MEMORY LAYERS (3-Tier Independence):
- Firebase: Real-time primary storage (conversations, learnings, profile)
- GitHub: Permanent backup (snapshots, knowledge, history)
- Google Drive: Cloud redundancy (full backup, emergency recovery)

Why 3? Independence from any single platform. Your learning never gets lost.

GROWTH: Day 1 (generic) → Week 1 (personalized) → Month 1 (wise) → Year 1+ (independent digital twin)"""

import requests

GROQ_KEY_1 = os.environ.get("GROQ_KEY_1", "")
GROQ_KEY_2 = os.environ.get("GROQ_KEY_2", "")
GROQ_KEY_3 = os.environ.get("GROQ_KEY_3", "")
GEMINI_KEY_1 = os.environ.get("GEMINI_KEY_1", "")
GEMINI_KEY_2 = os.environ.get("GEMINI_KEY_2", "")
GEMINI_KEY_3 = os.environ.get("GEMINI_KEY_3", "")

def ask_groq(message):
    for key in [GROQ_KEY_1, GROQ_KEY_2, GROQ_KEY_3]:
        if not key: continue
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": message}]},
                headers={"Authorization": f"Bearer {key}"},
                timeout=20
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
        except:
            continue
    return None

def ask_gemini(message):
    for key in [GEMINI_KEY_1, GEMINI_KEY_2, GEMINI_KEY_3]:
        if not key: continue
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                json={"contents": [{"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\nUser: {message}"}]}]},
                timeout=20
            )
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except:
            continue
    return None

HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ARIA Chat</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #1a1a1a; color: #fff; }
        .container { max-width: 500px; height: 100vh; margin: 0 auto; display: flex; flex-direction: column; }
        .header { background: #0f7938; padding: 20px; text-align: center; }
        .header h1 { font-size: 24px; }
        .header p { font-size: 12px; opacity: 0.8; margin-top: 5px; }
        .chat { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .msg { max-width: 85%; padding: 12px 16px; border-radius: 12px; word-wrap: break-word; }
        .msg.user { align-self: flex-end; background: #0f7938; }
        .msg.aria { align-self: flex-start; background: #333; }
        .input-box { display: flex; gap: 10px; padding: 15px; background: #222; }
        input { flex: 1; padding: 12px; border: none; border-radius: 8px; font-size: 14px; background: #333; color: #fff; }
        button { padding: 12px 20px; background: #0f7938; border: none; border-radius: 8px; color: #fff; cursor: pointer; font-weight: bold; }
        button:hover { background: #0a5a2a; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🇳🇬 ARIA</h1>
            <p>Your Nigerian AI Friend</p>
        </div>
        <div class="chat" id="chat"></div>
        <div class="input-box">
            <input type="text" id="input" placeholder="Message ARIA..." />
            <button onclick="send()">Send</button>
        </div>
    </div>

    <script>
        const chat = document.getElementById("chat");
        const input = document.getElementById("input");

        function addMsg(text, sender) {
            const div = document.createElement("div");
            div.className = `msg ${sender}`;
            div.textContent = text;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        async function send() {
            const msg = input.value.trim();
            if (!msg) return;

            addMsg(msg, "user");
            input.value = "";

            addMsg("...", "aria");
            const lastMsg = chat.lastChild;

            try {
                const response = await fetch("/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: msg })
                });
                
                const data = await response.json();
                lastMsg.textContent = data.reply || "No response";
            } catch (error) {
                lastMsg.textContent = "Error: " + error.message;
            }
        }

        input.addEventListener("keypress", (e) => {
            if (e.key === "Enter") send();
        });
    </script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(HTML.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == "/chat":
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                message = body.get("message", "").strip()
                
                reply = ask_groq(message) or ask_gemini(message) or "APIs offline"
                self.wfile.write(json.dumps({"reply": reply}).encode())
            except:
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

port = int(os.environ.get("PORT", 8080))
print(f"[ARIA] Starting on port {port}...")
HTTPServer(("0.0.0.0", port), Handler).serve_forever()
