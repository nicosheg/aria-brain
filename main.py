from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from aria_agent.config import get_settings
from aria_agent.runtime import AgentRuntime
from aria_agent.security import redact_secrets
from aria_agent.storage import AgentStore


settings = get_settings()
store = AgentStore(settings.database_url)
runtime = AgentRuntime(store)


def user_id_from_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        raise ValueError("valid email is required")
    return "email_" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


_firebase_auth = None
_firebase_error = None


def _get_firebase_auth():
    global _firebase_auth, _firebase_error
    if _firebase_auth is not None:
        return _firebase_auth
    if _firebase_error:
        return None

    raw = settings.firebase_credentials.strip()
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
                firebase_admin.initialize_app(credentials.Certificate(raw and __import__("json").loads(raw)))
            else:
                firebase_admin.initialize_app(credentials.Certificate(raw))
        _firebase_auth = auth
        return _firebase_auth
    except Exception as exc:
        _firebase_error = str(exc)
        return None


def identity_from_request(
    authorization: Optional[str],
    email: Optional[str] = None,
) -> dict[str, str]:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            auth_module = _get_firebase_auth()
            if auth_module is None:
                raise HTTPException(status_code=503, detail="Authentication service is not configured.")
            try:
                decoded = auth_module.verify_id_token(token)
            except Exception:
                raise HTTPException(status_code=401, detail="Authentication token is invalid or expired.")
            uid = str(decoded.get("uid", "")).strip()
            if not uid:
                raise HTTPException(status_code=401, detail="Authentication token contains no user identity.")
            return {
                "user_id": uid,
                "email": str(decoded.get("email", "") or "").strip().lower(),
                "display_name": str(decoded.get("name", "") or "").strip(),
            }

    if settings.allow_email_identity and email:
        try:
            user_id = user_id_from_email(email)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "user_id": user_id,
            "email": email.strip().lower(),
            "display_name": email.strip().split("@", 1)[0],
        }

    raise HTTPException(status_code=401, detail="Sign in and send a Firebase ID token.")


def public_aria_uid(user_id: str) -> str:
    return "aria-" + hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:24]


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")[:180] or "upload.bin"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    email: Optional[str] = Field(default=None, max_length=320)


class ConnectorRequest(BaseModel):
    email: Optional[str] = None
    name: str = Field(min_length=1, max_length=100)
    connector_type: str = Field(pattern="^(mcp|rest|browser)$")
    base_url: str = Field(default="", max_length=2000)
    config: dict = Field(default_factory=dict)


class AutomationRequest(BaseModel):
    email: Optional[str] = None
    name: str = Field(min_length=1, max_length=100)
    trigger_name: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=8000)


class AutomationEvent(BaseModel):
    payload: dict = Field(default_factory=dict)


class JobRequest(BaseModel):
    email: Optional[str] = None
    kind: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=12000)
    payload: dict = Field(default_factory=dict)
    run_after: Optional[str] = Field(default=None, max_length=80)


class ApprovalDecision(BaseModel):
    approved: bool


class UploadRequest(BaseModel):
    email: Optional[str] = None
    file_base64: str = Field(min_length=1, max_length=40_000_000)
    file_name: str = Field(min_length=1, max_length=240)
    file_type: str = Field(default="file", max_length=50)
    mime_type: str = Field(default="", max_length=120)


app = FastAPI(
    title="ARIA Agent Runtime",
    version=settings.app_version,
    description="Agentic runtime for research, work, income, communication, software and connected-app automation.",
)

cors_raw = os.getenv("ARIA_CORS_ORIGINS", "").strip()
origins = [x.strip() for x in cors_raw.split(",") if x.strip()]
if not origins:
    origins = ["http://localhost:3000", "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-ARIA-Automation-Secret"],
)


@app.get("/health")
async def health():
    configured = {
        "groq": any(os.getenv(f"GROQ_KEY_{i}") for i in range(1, 21)),
        "deepseek": any(os.getenv(f"DEEPSEEK_KEY_{i}") for i in range(1, 6)),
        "openai": bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY_1")),
        "gemini": any(os.getenv(f"GEMINI_KEY_{i}") for i in range(1, 21)),
        "search": any(os.getenv(k) for k in ("TAVILY_API_KEY", "BRAVE_SEARCH_API_KEY", "SERPER_API_KEY")),
    }
    return {
        "status": "ok" if store.durable else "degraded",
        "service": "aria-agent-runtime",
        "version": settings.app_version,
        "autonomy": settings.autonomy_level,
        "durable_store": store.durable,
        "firebase_configured": bool(settings.firebase_credentials),
        "email_identity_enabled": settings.allow_email_identity,
        "providers_configured": configured,
        "workers": len(runtime.workers.all()),
        "connector_types": ["mcp", "rest", "browser"],
        "browser_control": settings.allow_browser,
    }


@app.get("/ping")
async def ping():
    return {"pong": "ok"}


@app.get("/workers")
async def workers():
    return {"workers": runtime.workers.manifest()}


@app.get("/capabilities")
async def capabilities(
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    return runtime.capability_manifest(identity["user_id"])


@app.post("/chat")
async def chat(
    req: ChatRequest,
    authorization: Optional[str] = Header(default=None),
):
    started = time.perf_counter()
    identity = identity_from_request(authorization, req.email)
    try:
        result = await asyncio.to_thread(runtime.run, identity["user_id"], req.message)
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        runtime.store.audit(None, identity["user_id"], "request.failed", {"type": type(exc).__name__})
        raise HTTPException(status_code=500, detail="ARIA could not complete the request safely.")


@app.post("/agent/run")
async def agent_run(
    req: ChatRequest,
    authorization: Optional[str] = Header(default=None),
):
    return await chat(req, authorization)


@app.post("/agent/approvals/{approval_id}/approve")
async def approve(
    approval_id: str,
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    try:
        return await asyncio.to_thread(runtime.approve, identity["user_id"], approval_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        runtime.store.audit(None, identity["user_id"], "approval.resume_failed", {"type": type(exc).__name__})
        raise HTTPException(status_code=500, detail="ARIA could not resume the approved action safely.")


@app.post("/agent/approvals/{approval_id}/reject")
async def reject(
    approval_id: str,
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    try:
        return await asyncio.to_thread(runtime.reject, identity["user_id"], approval_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        runtime.store.audit(None, identity["user_id"], "approval.reject_failed", {"type": type(exc).__name__})
        raise HTTPException(status_code=500, detail="ARIA could not reject the action safely.")


@app.get("/get-uid")
async def get_uid(
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    return {"aria_uid": public_aria_uid(identity["user_id"]), "user_id": identity["user_id"]}


@app.get("/context")
async def context(
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    runs = await asyncio.to_thread(store.list_runs, identity["user_id"], 50)
    lines = []
    for row in reversed(runs):
        if row.get("input"):
            lines.append("User: " + str(row["input"]))
        if row.get("output"):
            try:
                import json
                output = json.loads(row["output"]) if isinstance(row["output"], str) else row["output"]
                reply = output.get("reply") if isinstance(output, dict) else row["output"]
            except Exception:
                reply = row["output"]
            if reply:
                lines.append("ARIA: " + str(reply))
    return {"context": "\n".join(lines[-100:])}


@app.post("/set_user_name")
async def set_user_name(
    payload: dict[str, Any],
    authorization: Optional[str] = Header(default=None),
):
    identity = identity_from_request(authorization, payload.get("email"))
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required.")
    store.write_memory(identity["user_id"], "profile:name", redact_secrets(name), 0.9)
    return {"status": "ok", "aria_uid": public_aria_uid(identity["user_id"])}


@app.post("/feedback")
async def feedback(
    payload: dict[str, Any],
    authorization: Optional[str] = Header(default=None),
):
    identity = identity_from_request(authorization, payload.get("email"))
    score = int(payload.get("score", 0))
    if score < 1 or score > 5:
        raise HTTPException(status_code=400, detail="Score must be between 1 and 5.")
    event_id = hashlib.sha256(f"{identity['user_id']}:{time.time_ns()}".encode()).hexdigest()[:24]
    store.audit(None, identity["user_id"], "feedback.submitted", {"id": event_id, "score": score})
    return {"status": "ok", "id": event_id}


@app.get("/debug-memory")
async def debug_memory(
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    return {"memories": store.read_memory(identity["user_id"], "", 50)}


@app.get("/runs")
async def runs(
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    return {"runs": store.list_runs(identity["user_id"], 100)}


@app.get("/jobs")
async def list_jobs(
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    return {"jobs": store.list_jobs(identity["user_id"], 100)}


@app.post("/jobs")
async def create_job(
    req: JobRequest,
    authorization: Optional[str] = Header(default=None),
):
    identity = identity_from_request(authorization, req.email)
    job_id = store.enqueue_job(identity["user_id"], req.kind, {**req.payload, "goal": req.goal}, req.run_after)
    return {"status": "queued", "job_id": job_id}


@app.get("/automations")
async def list_automations(
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    return {"automations": store.list_automations(identity["user_id"])}


@app.post("/automations")
async def create_automation(
    req: AutomationRequest,
    authorization: Optional[str] = Header(default=None),
):
    identity = identity_from_request(authorization, req.email)
    return await asyncio.to_thread(runtime.create_automation, identity["user_id"], req.name, req.trigger_name, req.prompt)


@app.post("/automations/{automation_id}/enable")
async def enable_automation(
    automation_id: str,
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    if not store.set_automation_enabled(automation_id, identity["user_id"], True):
        raise HTTPException(status_code=404, detail="automation not found")
    return {"id": automation_id, "enabled": True}


@app.post("/automations/{automation_id}/disable")
async def disable_automation(
    automation_id: str,
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    if not store.set_automation_enabled(automation_id, identity["user_id"], False):
        raise HTTPException(status_code=404, detail="automation not found")
    return {"id": automation_id, "enabled": False}


@app.delete("/automations/{automation_id}")
async def delete_automation(
    automation_id: str,
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    if not store.delete_automation(automation_id, identity["user_id"]):
        raise HTTPException(status_code=404, detail="automation not found")
    return {"deleted": True, "id": automation_id}


@app.post("/hooks/automations/{automation_id}")
async def automation_hook(
    automation_id: str,
    event: AutomationEvent,
    x_aria_automation_secret: str = Header(default=""),
):
    if not x_aria_automation_secret:
        raise HTTPException(status_code=401, detail="automation secret required")
    try:
        return await asyncio.to_thread(runtime.trigger_automation, automation_id, x_aria_automation_secret, event.payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError:
        raise HTTPException(status_code=403, detail="invalid automation secret")
    except Exception:
        raise HTTPException(status_code=500, detail="Automation could not be executed safely.")


@app.get("/connectors")
async def list_connectors(
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    rows = runtime.store.list_connectors(identity["user_id"])
    return {
        "connectors": [
            {"id": r["id"], "name": r["name"], "connector_type": r["connector_type"], "base_url": r.get("base_url")}
            for r in rows
        ]
    }


@app.post("/connectors")
async def register_connector(
    req: ConnectorRequest,
    authorization: Optional[str] = Header(default=None),
):
    identity = identity_from_request(authorization, req.email)
    try:
        row = await asyncio.to_thread(runtime.connectors.register, identity["user_id"], req.name, req.connector_type, req.base_url, req.config)
        return {
            "id": row["id"], "name": row["name"], "connector_type": row["connector_type"], "base_url": row["base_url"],
        }
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/connectors/{connector_id}/tools")
async def connector_tools(
    connector_id: str,
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    try:
        return await asyncio.to_thread(runtime.inspect_connector, identity["user_id"], connector_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/connectors/{connector_id}")
async def delete_connector(
    connector_id: str,
    authorization: Optional[str] = Header(default=None),
    email: Optional[str] = None,
):
    identity = identity_from_request(authorization, email)
    if not runtime.connectors.delete(connector_id, identity["user_id"]):
        raise HTTPException(status_code=404, detail="connector not found")
    return {"deleted": True, "id": connector_id}


@app.post("/upload-ocr")
async def upload_ocr(
    req: UploadRequest,
    authorization: Optional[str] = Header(default=None),
):
    return await _upload_file(req, authorization)


@app.post("/upload-pdf")
async def upload_pdf(
    req: UploadRequest,
    authorization: Optional[str] = Header(default=None),
):
    return await _upload_file(req, authorization)


async def _upload_file(req: UploadRequest, authorization: Optional[str]):
    identity = identity_from_request(authorization, req.email)
    try:
        raw = base64.b64decode(req.file_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 upload.")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File is larger than 25MB.")

    user_dir = settings.data_dir / "uploads" / re.sub(r"[^A-Za-z0-9_-]", "_", identity["user_id"])
    user_dir.mkdir(parents=True, exist_ok=True)
    safe_name = safe_filename(req.file_name)
    path = user_dir / safe_name
    path.write_bytes(raw)

    extracted = ""
    file_type = (req.file_type or "").lower()
    mime_type = (req.mime_type or "").lower()

    if file_type == "pdf" or mime_type == "application/pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            extracted = "\n".join((page.extract_text() or "") for page in reader.pages)[:30000]
        except Exception:
            extracted = ""
    elif mime_type.startswith("image/") or file_type in {"image", "ocr", "photo"}:
        extracted = runtime.models.image_to_text(
            "Extract all useful text and structured facts visible in this image. Preserve names, numbers, dates and table rows exactly when legible.",
            base64.b64encode(raw).decode("ascii"),
            mime_type or "image/jpeg",
            max_tokens=4000,
        ) or ""

    store.write_memory(
        identity["user_id"],
        f"file:{hashlib.sha256((safe_name + str(time.time_ns())).encode()).hexdigest()[:20]}",
        redact_secrets(f"Uploaded {safe_name}. Extracted text preview:\n{extracted[:5000]}"),
        0.45,
    )

    if extracted:
        status = "PDF processed" if (file_type == "pdf" or mime_type == "application/pdf") else "OCR processed"
        return {"status": status, "file_name": req.file_name, "full_length": len(extracted), "text": extracted}
    return {
        "status": "uploaded",
        "file_name": req.file_name,
        "full_length": 0,
        "text": "",
        "message": "File saved to ARIA's private workspace. Text extraction was not available for this file type.",
    }


@app.get("/")
async def index():
    path = Path("public/index.html").resolve()
    root = Path("public").resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=404, detail="frontend not found")
    if not path.exists():
        raise HTTPException(status_code=404, detail="frontend not found")
    return FileResponse(path)


@app.get("/{path:path}")
async def static(path: str):
    root = Path("public").resolve()
    full_path = (root / path).resolve()
    try:
        full_path.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=404, detail="not found")
    if full_path.is_file():
        return FileResponse(full_path)
    raise HTTPException(status_code=404, detail="not found")
