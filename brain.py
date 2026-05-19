"""
ARIA 3.1 PRODUCTION - Modular Architecture
Each module is independent, testable, extensible
Factory pattern: workers in different fields, all coordinated perfectly
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json, datetime, urllib.request, os, re
import pytz, firebase_admin
from firebase_admin import credentials, firestore

# ============================================================================
# MODULE 1: CONFIG (Centralized settings)
# ============================================================================

class Config:
    """All configuration in one place. Change here, everything updates."""
    
    def __init__(self):
        self.groq_keys = [os.environ.get(f"GROQ_KEY_{i+1}", "") for i in range(5)]
        self.gemini_keys = [os.environ.get(f"GEMINI_KEY_{i+1}", "") for i in range(5)]
        self.firebase_creds = os.environ.get("FIREBASE_CREDENTIALS", "")
        self.my_number = os.environ.get("MY_NUMBER", "")
        self.my_lid = os.environ.get("MY_LID", "")
        self.port = int(os.environ.get("PORT", 8080))
        self.timezone = "Africa/Lagos"
        self.model_groq = "llama-3.3-70b-versatile"
        self.model_gemini = "gemini-2.0-flash"
        self.timeout = 30
        self.memory_truncate = 1000
        self.response_truncate = 300
        self.quality_threshold = 0.7

config = Config()

# ============================================================================
# MODULE 2: TIME UTILITIES (Lagos timezone)
# ============================================================================

class TimeUtils:
    """All time operations. Pure functions, no state."""
    
    @staticmethod
    def get_lagos_time():
        """Current time in Lagos"""
        return datetime.datetime.now(pytz.timezone(config.timezone)).strftime("%a %d %b %Y - %I:%M %p")
    
    @staticmethod
    def get_lagos_date():
        """Current date in Lagos"""
        return datetime.datetime.now(pytz.timezone(config.timezone)).strftime("%Y_%m_%d")

# ============================================================================
# MODULE 3: FIREBASE (Database persistence)
# ============================================================================

class FirebaseManager:
    """Single responsibility: Firebase operations only"""
    
    def __init__(self):
        self.db = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Firebase connection"""
        try:
            if config.firebase_creds:
                cred = credentials.Certificate(json.loads(config.firebase_creds))
                firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                print("[FIREBASE] ✓ Connected")
        except Exception as e:
            print(f"[FIREBASE] ✗ {type(e).__name__}: {str(e)[:30]}")
    
    def is_connected(self):
        return self.db is not None
    
    def save_document(self, collection, document_id, data):
        """Generic save operation"""
        if not self.is_connected():
            return False
        try:
            self.db.collection(collection).document(document_id).set(data, merge=True)
            return True
        except Exception as e:
            print(f"[FIREBASE] Save error: {type(e).__name__}")
            return False
    
    def get_documents(self, collection, filters=None, limit=50):
        """Generic read operation"""
        if not self.is_connected():
            return []
        try:
            query = self.db.collection(collection)
            if filters:
                for field, operator, value in filters:
                    query = query.where(firestore.FieldFilter(field, operator, value))
            return [doc.to_dict() for doc in query.limit(limit).get() if doc.exists]
        except:
            return []

firebase = FirebaseManager()

# ============================================================================
# MODULE 4: MEMORY (3-phase: permanent, in-between, temporary)
# ============================================================================

class MemoryManager:
    """Single responsibility: Memory management only"""
    
    PERMANENT = "aria_permanent"
    IN_BETWEEN = "aria_in_between"
    TEMPORARY = "aria_temporary"
    LEARNINGS = "aria_learnings"
    
    @staticmethod
    def save_temporary(sender, role, content):
        """Save today's messages (volatile)"""
        if not content:
            return
        today = TimeUtils.get_lagos_date()
        data = {
            "date": today,
            "messages": firestore.ArrayUnion([{
                "timestamp": TimeUtils.get_lagos_time(),
                "sender": sender,
                "role": role,
                "content": content[:config.memory_truncate]
            }])
        }
        firebase.save_document(MemoryManager.TEMPORARY, today, data)
    
    @staticmethod
    def save_in_between(sender, role, content):
        """Save 1-2 week messages (semi-permanent)"""
        if not content:
            return
        today = TimeUtils.get_lagos_date()
        data = {
            "date": today,
            "messages": firestore.ArrayUnion([{
                "timestamp": TimeUtils.get_lagos_time(),
                "sender": sender,
                "role": role,
                "content": content[:config.memory_truncate]
            }])
        }
        firebase.save_document(MemoryManager.IN_BETWEEN, today, data)
    
    @staticmethod
    def get_memory(sender, limit=50):
        """Get all memory (temporary + learnings)"""
        memory = []
        
        # Get recent temporary messages
        temp_docs = firebase.get_documents(MemoryManager.TEMPORARY, limit=2)
        for doc in temp_docs:
            for msg in doc.get("messages", []):
                if msg.get("role") in ["user", "assistant"]:
                    memory.append({"role": msg["role"], "content": msg["content"]})
        
        # Get learnings
        learnings = firebase.get_documents(MemoryManager.LEARNINGS, [
            ("sender", "==", sender),
            ("confidence", ">=", 0.6)
        ], limit=5)
        for learning in learnings:
            memory.append({
                "role": "system",
                "content": f"LEARNED: {learning.get('topic', '')} ({learning.get('confidence', 0):.0%})"
            })
        
        return memory[:limit]
    
    @staticmethod
    def save_learning(sender, topic, content, source, quality_score):
        """Save what ARIA learned"""
        confidence = 0.95 if source == "user" else min(0.89, 0.5 + (quality_score * 0.4))
        
        data = {
            "sender": sender,
            "topic": topic,
            "content": content[:config.memory_truncate],
            "source": source,
            "quality_score": quality_score,
            "confidence": confidence,
            "learned_date": TimeUtils.get_lagos_time(),
            "created_at": firestore.SERVER_TIMESTAMP
        }
        firebase.save_document(MemoryManager.LEARNINGS, f"{sender}_{int(__import__('time').time())}", data)

# ============================================================================
# MODULE 5: QUALITY FILTER (Content validation)
# ============================================================================

class QualityFilter:
    """Single responsibility: Filtering and validation only"""
    
    @staticmethod
    def check_response_quality(text):
        """Score response quality 0-1"""
        if not text or len(text) < 10:
            return 0.0
        
        score = 1.0
        
        # Length bonus
        if len(text) < 50:
            score -= 0.2
        
        # Structure bonus (lists, newlines)
        if '\n' in text or any(m in text for m in ['1.', '2.', '•', '-']):
            score += 0.1
        
        # Uncertainty penalty
        uncertain_words = sum(1 for w in ['maybe', 'perhaps', 'probably', 'might'] if w in text.lower())
        if uncertain_words > 2:
            score -= 0.15
        
        # Confidence bonus
        confident_words = sum(1 for w in ['is', 'clearly', 'definitely', 'works'] if w in text.lower())
        if confident_words > 3:
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    @staticmethod
    def is_valid_content(text):
        """Check if content is valid"""
        if not text or len(text.strip()) < 2:
            return False, "Empty"
        if len(text) > 10000:
            return False, "Too long"
        return True, None
    
    @staticmethod
    def truncate_response(text, max_length=1000):
        """Safely truncate response"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."

# ============================================================================
# MODULE 6: API ENSEMBLE (Groq + Gemini simultaneous)
# ============================================================================

class APIManager:
    """Single responsibility: API calls only"""
    
    groq_index = 0
    gemini_index = 0
    
    @staticmethod
    def get_next_groq_key():
        """Round-robin key rotation"""
        key = config.groq_keys[APIManager.groq_index]
        APIManager.groq_index = (APIManager.groq_index + 1) % len(config.groq_keys)
        return key
    
    @staticmethod
    def get_next_gemini_key():
        """Round-robin key rotation"""
        key = config.gemini_keys[APIManager.gemini_index]
        APIManager.gemini_index = (APIManager.gemini_index + 1) % len(config.gemini_keys)
        return key
    
    @staticmethod
    def ask_groq(message, memory=[]):
        """Call Groq API"""
        key = APIManager.get_next_groq_key()
        if not key:
            return None, "No key"
        
        try:
            messages = [{"role": "system", "content": f"You are ARIA 3.1. Female. Friend. Lagos: {TimeUtils.get_lagos_time()}"}]
            messages.extend(memory)
            messages.append({"role": "user", "content": message})
            
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps({"model": config.model_groq, "messages": messages}).encode(),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=config.timeout) as res:
                result = json.loads(res.read())
                reply = result["choices"][0]["message"]["content"]
                return reply, None
        except urllib.error.HTTPError as e:
            return None, f"HTTP {e.code}"
        except Exception as e:
            return None, type(e).__name__
    
    @staticmethod
    def ask_gemini(message, memory=[]):
        """Call Gemini API"""
        key = APIManager.get_next_gemini_key()
        if not key:
            return None, "No key"
        
        try:
            contents = []
            contents.append({"role": "user", "parts": [{"text": f"You are ARIA 3.1. Female. Friend. Lagos: {TimeUtils.get_lagos_time()}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
            
            for m in memory:
                role = "user" if m["role"] == "user" else "model"
                if m["content"].strip():
                    contents.append({"role": role, "parts": [{"text": m["content"]}]})
            
            contents.append({"role": "user", "parts": [{"text": message}]})
            
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{config.model_gemini}:generateContent?key={key}",
                data=json.dumps({"contents": contents}).encode(),
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=config.timeout) as res:
                result = json.loads(res.read())
                reply = result["candidates"][0]["content"]["parts"][0]["text"]
                return reply, None
        except urllib.error.HTTPError as e:
            return None, f"HTTP {e.code}"
        except Exception as e:
            return None, type(e).__name__

# ============================================================================
# MODULE 7: RESPONSE ENGINE (Orchestrate all modules)
# ============================================================================

class ResponseEngine:
    """Orchestrate all modules. Coordinates the factory workers."""
    
    @staticmethod
    def generate_response(sender, message):
        """Generate response using ensemble of APIs + memory + learning"""
        
        # Validate input
        valid, error = QualityFilter.is_valid_content(message)
        if not valid:
            return None
        
        # Get memory
        memory = MemoryManager.get_memory(sender)
        
        # Try both APIs simultaneously
        groq_reply, groq_err = APIManager.ask_groq(message, memory)
        gemini_reply, gemini_err = APIManager.ask_gemini(message, memory)
        
        # Pick best response
        if groq_reply and gemini_reply:
            reply = f"[DUAL]\n{QualityFilter.truncate_response(groq_reply, config.response_truncate)}\nvs\n{QualityFilter.truncate_response(gemini_reply, config.response_truncate)}"
            source = "ensemble"
        elif groq_reply:
            reply = groq_reply
            source = "groq"
        elif gemini_reply:
            reply = gemini_reply
            source = "gemini"
        else:
            reply = "APIs offline - local mode"
            source = "local"
        
        # Learn from good responses
        if source in ["groq", "gemini"]:
            quality = QualityFilter.check_response_quality(reply)
            if quality > config.quality_threshold:
                topic = ' '.join(message.split()[:3])
                MemoryManager.save_learning(sender, topic, reply, source, quality)
        
        return QualityFilter.truncate_response(reply)

# ============================================================================
# MODULE 8: HTTP HANDLER (Request/response only)
# ============================================================================

class ARIAHandler(BaseHTTPRequestHandler):
    """Single responsibility: HTTP protocol only"""
    
    def log_message(self, *args):
        pass  # Silent logging
    
    def do_POST(self):
        if self.path == "/chat":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                sender = body.get("sender", "").strip()
                message = body.get("message", "").strip()
                
                if not sender or not message:
                    self._send_response(200, {"reply": ""})
                    return
                
                # Save input
                MemoryManager.save_temporary(sender, "user", message)
                MemoryManager.save_in_between(sender, "user", message)
                
                # Generate response
                reply = ResponseEngine.generate_response(sender, message)
                
                # Save output
                MemoryManager.save_temporary(sender, "assistant", reply)
                MemoryManager.save_in_between(sender, "assistant", reply)
                
                self._send_response(200, {"reply": reply})
            
            except json.JSONDecodeError:
                self._send_response(400, {"reply": "Invalid JSON"})
            except Exception as e:
                print(f"[ERROR] {type(e).__name__}: {str(e)[:50]}")
                self._send_response(500, {"reply": "Error"})
    
    def _send_response(self, code, data):
        """Send HTTP response"""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

# ============================================================================
# MODULE 9: STARTUP & MONITORING
# ============================================================================

class Startup:
    """Initialize and verify all systems"""
    
    @staticmethod
    def run_diagnostics():
        """Check all systems before starting"""
        print("\n" + "="*70)
        print("ARIA 3.1 - PRODUCTION MODULAR FINAL")
        print("="*70 + "\n")
        
        # Check APIs
        groq_ok = len([k for k in config.groq_keys if k])
        gemini_ok = len([k for k in config.gemini_keys if k])
        print(f"[GROQ] {groq_ok}/5 keys configured")
        print(f"[GEMINI] {gemini_ok}/5 keys configured")
        print(f"[FIREBASE] {'Connected' if firebase.is_connected() else 'Disconnected'}")
        print(f"[PORT] {config.port}")
        print("\n" + "="*70)
        
        if groq_ok == 0 or gemini_ok == 0:
            print("⚠️  WARNING: Some API keys missing!")
        
        return (groq_ok > 0 or gemini_ok > 0)
    
    @staticmethod
    def start_server():
        """Start HTTP server"""
        print(f"[STARTING] ARIA 3.1 on port {config.port}...")
        try:
            HTTPServer(("0.0.0.0", config.port), ARIAHandler).serve_forever()
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] ARIA offline")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    if Startup.run_diagnostics():
        Startup.start_server()
    else:
        print("❌ Cannot start: No valid API keys")
        exit(1)

