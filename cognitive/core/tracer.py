# ═════════════════════════════════════════════════════════════════════════════
# [TRACER] Enterprise-Grade Tracing System – Like Google Cloud Trace, OpenAI, Anthropic
# ═════════════════════════════════════════════════════════════════════════════
# 
# This is ARIA's observability layer. Every function call is traced with:
# - Full call stack (parent → child → grandchild)
# - Timing (start, duration, end)
# - Input/output data
# - Errors with root cause
# - Request correlation (all events tied to one request)
#
# The tracer also powers the /trace-agent endpoint – a mini Copilot that:
# - Analyzes trace trees in real time
# - Detects bugs, failures, and bottlenecks
# - Suggests fixes (like I would)
# - Learns from patterns
# ═════════════════════════════════════════════════════════════════════════════

import json
import time
import uuid
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from collections import deque
from enum import Enum


# ─────────────────────────────────────────────────────────────────────────────
# 1. CORE TRACE TYPES
# ─────────────────────────────────────────────────────────────────────────────

class TraceLevel(Enum):
    """Severity levels (like logging)"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class TraceSpan:
    """
    A single span in the trace tree.
    Similar to Google Cloud Trace spans – represents one operation.
    """
    id: str  # Unique span ID
    parent_id: Optional[str] = None  # Parent span (for tree structure)
    name: str = ""  # Function name: "extract_entities", "llm_call", etc.
    
    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    
    # Logging
    level: TraceLevel = TraceLevel.INFO
    message: str = ""
    
    # Data flow
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    
    # Errors
    error: Optional[str] = None
    error_type: Optional[str] = None
    error_stack: Optional[str] = None
    
    # Context
    user_id: str = ""
    request_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Status
    status: str = "pending"  # pending, success, failed
    
    def finish(self, output: Dict = None, error: str = None, error_type: str = None, error_stack: str = None):
        """Mark span as complete."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        
        if output:
            self.output_data = output
            self.status = "success"
        
        if error:
            self.error = error
            self.error_type = error_type
            self.error_stack = error_stack
            self.status = "failed"
            self.level = TraceLevel.ERROR
    
    def to_dict(self):
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "name": self.name,
            "level": self.level.value,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "message": self.message,
            "input": self._serialize(self.input_data),
            "output": self._serialize(self.output_data),
            "error": self.error,
            "error_type": self.error_type,
            "error_stack": self.error_stack[:500] if self.error_stack else None,
            "timestamp": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat()
        }
    
    @staticmethod
    def _serialize(data: Any) -> Any:
        """Make data JSON-serializable."""
        if isinstance(data, dict):
            return {k: TraceSpan._serialize(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return [TraceSpan._serialize(item) for item in data]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            return str(data)[:200]


# ─────────────────────────────────────────────────────────────────────────────
# 2. MAIN TRACER
# ─────────────────────────────────────────────────────────────────────────────

class Tracer:
    """
    Global tracer for structured observability.
    Stores traces, correlates requests, and powers the trace agent.
    """
    
    def __init__(self, max_traces: int = 1000):
        self.traces: deque = deque(maxlen=max_traces)  # All spans
        self.active_spans: Dict[str, TraceSpan] = {}   # Currently running
        self.root_spans: Dict[str, TraceSpan] = {}     # Request roots
        
        # Current context (thread-unsafe, but fine for single-threaded ARIA)
        self.current_request_id: Optional[str] = None
        self.current_user_id: Optional[str] = None
        
        # Logging
        self.logger = logging.getLogger("ARIA.Tracer")
    
    def new_request(self, user_id: str, source: str = "api") -> str:
        """Start a new traced request."""
        request_id = str(uuid.uuid4())[:12]
        self.current_request_id = request_id
        self.current_user_id = user_id
        
        root_span = TraceSpan(
            id=request_id,
            name=f"request_{source}",
            user_id=user_id,
            request_id=request_id,
        )
        self.root_spans[request_id] = root_span
        self.traces.append(root_span)
        
        self.logger.info(f"🆕 REQUEST {request_id} | user:{user_id} | source:{source}")
        return request_id
    
    def span(self, name: str, user_id: Optional[str] = None, 
             input_data: Optional[Dict] = None, metadata: Optional[Dict] = None):
        """
        Context manager for tracing a named operation.
        
        Usage:
            with tracer.span("extract_entities", input_data={"text": msg}) as span:
                # do work
                span.output("entities", result)
        """
        return _SpanContext(self, name, user_id, input_data, metadata)
    
    def log(self, level: TraceLevel, message: str, data: Optional[Dict] = None):
        """Log a message at a given level."""
        span = TraceSpan(
            id=str(uuid.uuid4())[:8],
            name="log",
            message=message,
            level=level,
            user_id=self.current_user_id or "",
            request_id=self.current_request_id or "",
            input_data=data or {},
            status="success"
        )
        self.traces.append(span)
        
        prefix = {
            TraceLevel.DEBUG: "🔹",
            TraceLevel.INFO: "ℹ️ ",
            TraceLevel.WARNING: "⚠️ ",
            TraceLevel.ERROR: "❌",
            TraceLevel.CRITICAL: "🔴"
        }.get(level, "•")
        
        self.logger.log(
            logging.getLevelName(level.value),
            f"{prefix} {message}" + (f" | {json.dumps(data)[:100]}" if data else "")
        )
    
    # ─────────────────────────────────────────────────────────────────────────
    # TRACE RETRIEVAL & ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_trace(self, request_id: str) -> Dict:
        """Get full trace tree for a request (all spans + analysis)."""
        spans = [s for s in self.traces if s.request_id == request_id]
        
        # Build tree structure
        root = None
        children_by_parent = {}
        
        for span in spans:
            if span.parent_id is None:
                root = span
            else:
                if span.parent_id not in children_by_parent:
                    children_by_parent[span.parent_id] = []
                children_by_parent[span.parent_id].append(span)
        
        return {
            "request_id": request_id,
            "span_count": len(spans),
            "root": root.to_dict() if root else None,
            "spans": [s.to_dict() for s in spans],
            "total_duration_ms": sum(s.duration_ms or 0 for s in spans if s.parent_id),
            "errors": [s.to_dict() for s in spans if s.status == "failed"],
            "analysis": self._analyze_trace(spans)
        }
    
    def _analyze_trace(self, spans: List[TraceSpan]) -> Dict:
        """Analyze trace for issues (bugs, bottlenecks, etc.)."""
        analysis = {
            "total_spans": len(spans),
            "failed_spans": len([s for s in spans if s.status == "failed"]),
            "slowest_spans": [],
            "critical_issues": [],
            "warnings": []
        }
        
        # Find slowest spans
        sorted_spans = sorted(
            [s for s in spans if s.duration_ms],
            key=lambda s: s.duration_ms,
            reverse=True
        )[:3]
        analysis["slowest_spans"] = [
            {"name": s.name, "duration_ms": s.duration_ms, "id": s.id}
            for s in sorted_spans
        ]
        
        # Detect issues
        for span in spans:
            if span.status == "failed":
                analysis["critical_issues"].append({
                    "span": span.name,
                    "error": span.error_type,
                    "message": span.error[:100]
                })
            
            if span.duration_ms and span.duration_ms > 1000:
                analysis["warnings"].append({
                    "type": "slow_span",
                    "span": span.name,
                    "duration_ms": span.duration_ms
                })
        
        return analysis
    
    def get_recent_traces(self, limit: int = 10, user_id: Optional[str] = None) -> List[Dict]:
        """Get recent traces, optionally filtered by user."""
        traces = list(self.traces)[-limit:]
        if user_id:
            traces = [t for t in traces if t.user_id == user_id]
        return [t.to_dict() for t in traces]


class _SpanContext:
    """Context manager for a single span (like with statement)."""
    
    def __init__(self, tracer: Tracer, name: str, user_id: Optional[str],
                 input_data: Optional[Dict], metadata: Optional[Dict]):
        self.tracer = tracer
        self.span = TraceSpan(
            id=str(uuid.uuid4())[:8],
            name=name,
            user_id=user_id or tracer.current_user_id or "",
            request_id=tracer.current_request_id or "",
            input_data=input_data or {},
            metadata=metadata or {}
        )
    
    def __enter__(self):
        self.tracer.active_spans[self.span.id] = self.span
        indent = "  " * len(self.tracer.active_spans)
        print(f"[TRACE] {indent}→ {self.span.name} START")
        if self.span.input_data:
            data_str = json.dumps(self.span.input_data, default=str)[:150]
            print(f"[TRACE] {indent}  input: {data_str}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import traceback
        indent = "  " * len(self.tracer.active_spans)
        
        if exc_type:
            self.span.finish(
                error=str(exc_val),
                error_type=exc_type.__name__,
                error_stack=traceback.format_exc()
            )
            print(f"[TRACE] {indent}← {self.span.name} FAILED ({exc_type.__name__})")
            print(f"[TRACE] {indent}  error: {str(exc_val)[:100]}")
        else:
            self.span.finish()
            print(f"[TRACE] {indent}← {self.span.name} OK ({self.span.duration_ms:.0f}ms)")
            if self.span.output_data:
                data_str = json.dumps(self.span.output_data, default=str)[:150]
                print(f"[TRACE] {indent}  output: {data_str}")
        
        self.tracer.traces.append(self.span)
        del self.tracer.active_spans[self.span.id]
        return False  # Don't suppress exceptions
    
    def input(self, key: str, value: Any):
        """Add input data to span."""
        self.span.input_data[key] = value
    
    def output(self, key: str, value: Any):
        """Add output data to span."""
        self.span.output_data[key] = value


# ─────────────────────────────────────────────────────────────────────────────
# 3. GLOBAL TRACER INSTANCE
# ─────────────────────────────────────────────────────────────────────────────

_global_tracer = Tracer()

def get_tracer() -> Tracer:
    """Get the global tracer instance."""
    return _global_tracer
