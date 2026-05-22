from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os
import requests

# ARIA 3.1 System Prompt - Compressed
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

# Get your API keys (3 each)
GROQ_KEY_1 = os.environ.get("GROQ_KEY_1", "")
GROQ_KEY_2 = os.environ.get("GROQ_KEY_2", "")
GROQ_KEY_3 = os.environ.get("GROQ_KEY_3", "")
GEMINI_KEY_1 = os.environ.get("GEMINI_KEY_1", "")
GEMINI_KEY_2 = os.environ.get("GEMINI_KEY_2", "")
GEMINI_KEY_3 = os.environ.get("GEMINI_KEY_3", "")

# Try Groq
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

# Try Gemini
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
