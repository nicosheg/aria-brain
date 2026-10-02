from __future__ import annotations

import asyncio
import hashlib
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from aria_agent.config import get_settings
from aria_agent.runtime import AgentRuntime
from aria_agent.storage import AgentStore


settings = get_settings()
store = AgentStore(settings.database_url)
runtime = AgentRuntime(store)


def user_id_from_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        raise ValueError("valid email is required")
    return "aria_" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    email: str = Field(min_length=3, max_length=320)


class ConnectorRequest(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=100)
    connector_type: str = Field(pattern="^(mcp|rest|browser)$")
    base_url: str = Field(default="", max_length=2000)
    config: dict = Field(default_factory=dict)


class AutomationRequest(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=100)
    trigger_name: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=8000)


class AutomationEvent(BaseModel):
    payload: dict = Field(default_factory=dict)


app = FastAPI(
    title="ARIA Agent Runtime",
    version=settings.app_version,
    description="Agentic runtime for research, work, income, communication, software and connected-app automation.",
)

cors_raw = os.getenv("ARIA_CORS_ORIGINS", "").strip()
origins = [x.strip() for x in cors_raw.split(",") if x.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    configured = {
        "groq": bool(os.getenv("GROQ_KEY_1")),
        "deepseek": bool(os.getenv("DEEPSEEK_KEY_1")),
        "openai": bool(os.getenv("OPENAI_KEY_1") or os.getenv("OPENAI_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_KEY_1")),
        "search": any(os.getenv(k) for k in ("TAVILY_API_KEY", "BRAVE_SEARCH_API_KEY", "SERPER_API_KEY")),
    }
    return {
        "status": "ok",
        "service": "aria-agent-runtime",
        "version": settings.app_version,
        "autonomy": settings.autonomy_level,
        "durable_store": store.durable,
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
async def capabilities(email: str):
    try:
        user_id = user_id_from_email(email)
        return runtime.capability_manifest(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/chat")
async def chat(req: ChatRequest):
    started = time.perf_counter()
    try:
        user_id = user_id_from_email(req.email)
        result = await asyncio.to_thread(runtime.run, user_id, req.message)
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        runtime.store.audit(None, None, "request.failed", {"type": type(exc).__name__})
        raise HTTPException(status_code=500, detail="ARIA could not complete the request safely.")


@app.post("/agent/run")
async def agent_run(req: ChatRequest):
    return await chat(req)


@app.post("/agent/approvals/{approval_id}/approve")
async def approve(approval_id: str, email: str):
    try:
        user_id = user_id_from_email(email)
        return await asyncio.to_thread(runtime.approve, user_id, approval_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="ARIA could not resume the approved action safely.")


@app.post("/agent/approvals/{approval_id}/reject")
async def reject(approval_id: str, email: str):
    try:
        user_id = user_id_from_email(email)
        return await asyncio.to_thread(runtime.reject, user_id, approval_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="ARIA could not reject the action safely.")


@app.get("/automations")
async def list_automations(email: str):
    try:
        user_id = user_id_from_email(email)
        rows = store.list_automations(user_id)
        return {"automations": rows}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/automations")
async def create_automation(req: AutomationRequest):
    try:
        user_id = user_id_from_email(req.email)
        return await asyncio.to_thread(
            runtime.create_automation, user_id, req.name, req.trigger_name, req.prompt
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/automations/{automation_id}/enable")
async def enable_automation(automation_id: str, email: str):
    try:
        user_id = user_id_from_email(email)
        if not store.set_automation_enabled(automation_id, user_id, True):
            raise HTTPException(status_code=404, detail="automation not found")
        return {"id": automation_id, "enabled": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/automations/{automation_id}/disable")
async def disable_automation(automation_id: str, email: str):
    try:
        user_id = user_id_from_email(email)
        if not store.set_automation_enabled(automation_id, user_id, False):
            raise HTTPException(status_code=404, detail="automation not found")
        return {"id": automation_id, "enabled": False}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/automations/{automation_id}")
async def delete_automation(automation_id: str, email: str):
    try:
        user_id = user_id_from_email(email)
        if not store.delete_automation(automation_id, user_id):
            raise HTTPException(status_code=404, detail="automation not found")
        return {"deleted": True, "id": automation_id}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/hooks/automations/{automation_id}")
async def automation_hook(automation_id: str, event: AutomationEvent, x_aria_automation_secret: str = ""):
    if not x_aria_automation_secret:
        raise HTTPException(status_code=401, detail="automation secret required")
    try:
        return await asyncio.to_thread(
            runtime.trigger_automation,
            automation_id,
            x_aria_automation_secret,
            event.payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError:
        raise HTTPException(status_code=403, detail="invalid automation secret")
    except Exception:
        raise HTTPException(status_code=500, detail="Automation could not be executed safely.")


@app.get("/connectors")
async def list_connectors(email: str):
    try:
        user_id = user_id_from_email(email)
        rows = runtime.store.list_connectors(user_id)
        return {
            "connectors": [
                {"id": r["id"], "name": r["name"], "connector_type": r["connector_type"], "base_url": r.get("base_url")}
                for r in rows
            ]
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/connectors")
async def register_connector(req: ConnectorRequest):
    try:
        user_id = user_id_from_email(req.email)
        row = runtime.connectors.register(
            user_id, req.name, req.connector_type, req.base_url, req.config
        )
        return {
            "id": row["id"],
            "name": row["name"],
            "connector_type": row["connector_type"],
            "base_url": row["base_url"],
        }
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/connectors/{connector_id}/tools")
async def connector_tools(connector_id: str, email: str):
    try:
        user_id = user_id_from_email(email)
        return runtime.inspect_connector(user_id, connector_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/connectors/{connector_id}")
async def delete_connector(connector_id: str, email: str):
    try:
        user_id = user_id_from_email(email)
        if not runtime.connectors.delete(connector_id, user_id):
            raise HTTPException(status_code=404, detail="connector not found")
        return {"deleted": True, "id": connector_id}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/")
async def index():
    path = Path("public/index.html")
    if not path.exists():
        raise HTTPException(status_code=404, detail="frontend not found")
    return FileResponse(path)


@app.get("/{path:path}")
async def static(path: str):
    full_path = Path("public") / path
    if full_path.is_file():
        return FileResponse(full_path)
    raise HTTPException(status_code=404, detail="not found")
