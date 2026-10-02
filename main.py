from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from aria_agent.config import settings
from aria_agent.runtime import AriaRuntime
from aria_agent.storage import store
from aria_agent.security import assert_public_http_url

app = FastAPI(title="ARIA", version="4.0.0")

_origins = [x.strip() for x in os.getenv("ARIA_ALLOWED_ORIGINS", "").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

runtime = AriaRuntime(store)
PUBLIC_ROOT = Path("public").resolve()


@app.on_event("shutdown")
async def shutdown():
    await runtime.close()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=settings.max_message_chars)
    email: Optional[str] = None


class ApprovalRequest(BaseModel):
    approved: bool


class ConnectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=8, max_length=1000)
    kind: str = "mcp"
    token: str = Field(default="", max_length=4000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=12000)
    payload: dict[str, Any] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    score: int = Field(ge=1, le=5)


class UploadRequest(BaseModel):
    file_base64: str = Field(min_length=1, max_length=35_000_000)
    file_name: str = Field(min_length=1, max_length=240)
    file_type: str = "file"
    mime_type: str = ""


_firebase_auth = None
_firebase_error: Optional[str] = None


def _get_firebase_auth():
    global _firebase_auth, _firebase_error
    if _firebase_auth is not None:
        return _firebase_auth
    if _firebase_error:
        return None

    raw = os.getenv("FIREBASE_CREDENTIALS", "").strip()
    if not raw:
        _firebase_error = "FIREBASE_CREDENTIALS is not configured"
        return None

    try:
        import firebase_admin
        from firebase_admin import auth, credentials

        try:
            firebase_admin.get_app()
        except ValueError:
            if raw.startswith("{"):
                firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))
            else:
                firebase_admin.initialize_app(credentials.Certificate(raw))
        _firebase_auth = auth
        return _firebase_auth
    except Exception as exc:
        _firebase_error = str(exc)
        return None


def _identity_from_request(authorization: Optional[str], email: Optional[str] = None) -> dict[str, str]:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            auth_module = _get_firebase_auth()
            if auth_module is None:
                raise HTTPException(503, detail="Authentication service is not configured.")
            try:
                decoded = auth_module.verify_id_token(token)
            except Exception:
                raise HTTPException(401, detail="Authentication token is invalid or expired.")
            uid = str(decoded.get("uid", "")).strip()
            if not uid:
                raise HTTPException(401, detail="Authentication token contains no user identity.")
            user_email = str(decoded.get("email", "") or "")
            display_name = str(decoded.get("name", "") or "")
            store.ensure_user(uid, user_email, display_name)
            return {"user_id": uid, "email": user_email, "display_name": display_name}

    # Deliberately disabled by default. It exists only for local/dev compatibility.
    if settings.allow_email_identity and email:
        normalized = email.strip().lower()
        if "@" not in normalized:
            raise HTTPException(400, detail="A valid email is required.")
        uid = "email:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
        store.ensure_user(uid, normalized, normalized.split("@", 1)[0])
        return {"user_id": uid, "email": normalized, "display_name": normalized.split("@", 1)[0]}

    raise HTTPException(401, detail="Sign in and send a Firebase ID token.")


def _public_aria_uid(user_id: str) -> str:
    return "aria-" + hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:24]


def _require_https_url(url: str) -> str:
    try:
        return assert_public_http_url(url)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")[:180] or "upload.bin"


@app.get("/health")
async def health():
    providers = [(p, m) for p, m, _ in runtime.provider_candidates()]
    database_ready = bool(settings.database_url)
    healthy = bool(providers) and (database_ready or not settings.require_database)
    return {
        "status": "ok" if healthy else "degraded",
        "service": "aria-brain",
        "version": "4.0.0",
        "providers": [{"provider": p, "model": m} for p, m in providers],
        "storage": "postgres" if database_ready else "local",
        "queue_shared": database_ready,
        "database_required": settings.require_database,
        "browser_enabled": settings.browser_enabled,
        "firebase_configured": bool(os.getenv("FIREBASE_CREDENTIALS")),
        "encryption_configured": bool(settings.encryption_key or os.getenv("ARIA_APP_SECRET")),
    }


@app.get("/ping")
async def ping():
    return {"pong": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest, authorization: Optional[str] = Header(default=None)):
    identity = _identity_from_request(authorization, req.email)
    try:
        result = await runtime.run(identity["user_id"], req.message)
        return {
            "reply": result["reply"],
            "run_id": result["run_id"],
            "status": result["status"],
            "approval_required": result["approval_required"],
            "interruptions": result["interruptions"],
            "provider": result["provider"],
            "model": result["model"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        # Never expose stack traces, credentials or database details to clients.
        raise HTTPException(502, detail=f"ARIA could not complete the request: {type(exc).__name__}.")


@app.post("/runs/{run_id}/approve")
async def approve_run(run_id: str, req: ApprovalRequest, authorization: Optional[str] = Header(default=None)):
    identity = _identity_from_request(authorization)
    try:
        result = await runtime.run(
            identity["user_id"],
            "Continue the approved action." if req.approved else "Stop the requested action and explain what was not executed.",
            resume_run_id=run_id,
            approve=req.approved,
        )
        return result
    except Exception as exc:
        raise HTTPException(502, detail=f"ARIA could not resume the run: {type(exc).__name__}.")


@app.get("/get-uid")
async def get_uid(authorization: Optional[str] = Header(default=None), email: Optional[str] = None):
    identity = _identity_from_request(authorization, email)
    return {"aria_uid": _public_aria_uid(identity["user_id"]), "user_id": identity["user_id"]}


@app.get("/context")
async def get_context(authorization: Optional[str] = Header(default=None), email: Optional[str] = None):
    identity = _identity_from_request(authorization, email)
    rows = store.recent_memory(identity["user_id"], limit=50)
    lines = []
    for row in reversed(rows):
        if row["kind"] == "conversation_user":
            lines.append("User: " + row["content"])
        elif row["kind"] == "conversation_assistant":
            lines.append("ARIA: " + row["content"])
    return {"context": "\n".join(lines)}


@app.post("/set_user_name")
async def set_user_name(payload: dict, authorization: Optional[str] = Header(default=None)):
    identity = _identity_from_request(authorization, payload.get("email"))
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(400, detail="Name is required.")
    store.ensure_user(identity["user_id"], identity.get("email", ""), name)
    store.add_memory(identity["user_id"], "profile", f"The user's preferred name is {name}.", importance=0.85)
    return {"status": "ok", "aria_uid": _public_aria_uid(identity["user_id"])}


@app.post("/feedback")
async def feedback(req: FeedbackRequest, authorization: Optional[str] = Header(default=None)):
    identity = _identity_from_request(authorization)
    return {"status": "ok", "id": store.add_feedback(identity["user_id"], req.score)}


@app.get("/debug-memory")
async def debug_memory(authorization: Optional[str] = Header(default=None)):
    identity = _identity_from_request(authorization)
    return {"memories": store.recent_memory(identity["user_id"], limit=50)}


@app.post("/connections")
async def add_connection(req: ConnectionRequest, authorization: Optional[str] = Header(default=None)):
    identity = _identity_from_request(authorization)
    safe_url = _require_https_url(req.url)
    kind = req.kind.strip().lower()
    if kind not in {"mcp", "streamable_http", "http", "sse", "http_sse"}:
        raise HTTPException(400, detail="Unsupported MCP connection transport.")
    result = store.save_connection(
        identity["user_id"], req.name.strip(), kind, safe_url, req.token.strip(), req.metadata
    )
    return {"status": "connected", "connection": result}


@app.get("/connections")
async def list_connections(authorization: Optional[str] = Header(default=None)):
    identity = _identity_from_request(authorization)
    return {"connections": store.list_connections(identity["user_id"])}


@app.delete("/connections/{connection_id}")
async def delete_connection(connection_id: str, authorization: Optional[str] = Header(default=None)):
    identity = _identity_from_request(authorization)
    return {"deleted": store.delete_connection(identity["user_id"], connection_id)}


@app.post("/connections/{connection_id}/test")
async def test_connection(connection_id: str, authorization: Optional[str] = Header(default=None)):
    identity = _identity_from_request(authorization)
    conn = store.get_connection(identity["user_id"], connection_id)
    if not conn:
        raise HTTPException(404, detail="Connection not found.")
    try:
        tools = await runtime.connectors.test_connection(identity["user_id"], connection_id, store)
        return {"status": "ok", "name": conn["name"], "tools": tools}
    except Exception as exc:
        raise HTTPException(502, detail=f"Connector test failed: {type(exc).__name__}.") from exc


@app.get("/jobs")
async def list_jobs(authorization: Optional[str] = Header(default=None)):
    identity = _identity_from_request(authorization)
    return {"jobs": store.list_jobs(identity["user_id"], limit=100)}


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, authorization: Optional[str] = Header(default=None)):
    identity = _identity_from_request(authorization)
    return {"cancelled": store.cancel_job(identity["user_id"], job_id)}


@app.post("/jobs")
async def create_job(req: JobRequest, authorization: Optional[str] = Header(default=None)):
    if settings.require_database and not settings.database_url:
        raise HTTPException(503, detail="Durable background jobs require a database-backed queue.")
    identity = _identity_from_request(authorization)
    payload = dict(req.payload)
    payload["goal"] = req.goal
    if len(json.dumps(payload, ensure_ascii=False)) > 50_000:
        raise HTTPException(413, detail="Job payload is too large.")
    job_id = store.enqueue_job(identity["user_id"], req.kind, payload)
    return {"status": "queued", "job_id": job_id}


async def _handle_upload(req: UploadRequest, authorization: Optional[str]) -> dict[str, Any]:
    identity = _identity_from_request(authorization)
    try:
        raw = base64.b64decode(req.file_base64, validate=True)
    except Exception:
        raise HTTPException(400, detail="Invalid base64 upload.")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, detail="File is larger than 25MB.")
    upload_dir = settings.data_dir / "uploads" / identity["user_id"]
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / _safe_filename(req.file_name)
    path.write_bytes(raw)

    kind = "file_upload"
    extracted = ""
    if req.file_type.lower() == "pdf" or req.mime_type.lower() == "application/pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            extracted = "\n".join((p.extract_text() or "") for p in reader.pages)[:30000]
            kind = "pdf_text"
        except Exception:
            kind = "pdf_upload"

    store.add_memory(
        identity["user_id"],
        kind,
        f"Uploaded {req.file_name} ({req.mime_type or req.file_type}), stored at {path.name}.",
        metadata={"file_name": req.file_name, "mime_type": req.mime_type, "path": str(path), "extracted_preview": extracted[:5000]},
        importance=0.55,
    )
    return {
        "status": "uploaded",
        "file_name": req.file_name,
        "full_length": len(extracted),
        "text": extracted,
        "message": "The file is stored in ARIA's private workspace. Image OCR/vision can be handled by a connected vision-capable worker.",
    }


@app.post("/upload-ocr")
async def upload_ocr(req: UploadRequest, authorization: Optional[str] = Header(default=None)):
    return await _handle_upload(req, authorization)


@app.post("/upload-pdf")
async def upload_pdf(req: UploadRequest, authorization: Optional[str] = Header(default=None)):
    return await _handle_upload(req, authorization)


@app.get("/")
async def index():
    return FileResponse(PUBLIC_ROOT / "index.html")


@app.get("/{path:path}")
async def static(path: str):
    candidate = (PUBLIC_ROOT / path).resolve()
    try:
        candidate.relative_to(PUBLIC_ROOT)
    except ValueError:
        raise HTTPException(404, detail="Not found")
    if candidate.is_file():
        return FileResponse(candidate)
    raise HTTPException(404, detail="Not found")
