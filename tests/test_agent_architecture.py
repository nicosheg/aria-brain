from pathlib import Path


def test_worker_catalog_is_large_and_unique():
    from aria_agent.workers import WORKER_SPECS
    names = [x[0] for x in WORKER_SPECS]
    assert len(names) >= 20
    assert len(names) == len(set(names))


def test_storage_local_fallback(tmp_path):
    from aria_agent.storage import AgentStore
    store = AgentStore()
    store._use_postgres = False
    store._path = Path(tmp_path) / "agent_store.json"
    store._path.parent.mkdir(parents=True, exist_ok=True)
    store._write_local(store._empty_local())
    store.ensure_user("u", "u@example.com", "Test")
    store.add_memory("u", "goal", "Build a portfolio", importance=0.9)
    assert store.search_memory("u", "portfolio")[0]["content"] == "Build a portfolio"



def test_connector_danger_classification():
    from aria_agent.connectors import needs_mcp_approval
    assert needs_mcp_approval("delete_file")
    assert needs_mcp_approval("send_email")
    assert needs_mcp_approval("get_file") is False


def test_no_legacy_singleton_in_runtime():
    source = Path("main.py").read_text("utf-8")
    assert "from brain import ask" not in source

def test_api_routes_are_not_shadowed():
    import main
    paths = [getattr(route, "path", "") for route in main.app.routes]
    assert paths.index("/chat") < paths.index("/{path:path}")
    assert paths.index("/context") < paths.index("/{path:path}")
    assert paths.index("/get-uid") < paths.index("/{path:path}")


def test_browser_tools_are_exposed():
    from aria_agent.tools import build_tools
    from aria_agent.storage import AgentStore
    from aria_agent.browser import BrowserController

    tools = build_tools("u", AgentStore(), BrowserController(enabled=False), False)
    names = {tool.name for tool in tools}
    assert {"browser_inspect_elements", "browser_click_ref", "browser_fill_ref", "browser_select_ref", "browser_upload_ref"} <= names


def test_job_queue_respects_schedule_and_recovers(tmp_path):
    from aria_agent.storage import AgentStore
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    s = AgentStore()
    s._use_postgres = False
    s._path = Path(tmp_path) / "jobs.json"
    s._write_local(s._empty_local())
    future = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    job_id = s.enqueue_job("u", "test", {"goal": "later"}, run_after=future)
    assert s.claim_job() is None

    row = s._read_local()["jobs"][0]
    row["run_after"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    s._write_local({"memory": [], "connections": [], "runs": [], "jobs": [row], "users": [], "feedback": []})
    claimed = s.claim_job()
    assert claimed["id"] == job_id
    assert claimed["attempts"] == 1

    retried = s.retry_job(job_id, 1, "temporary token=abcdefghijklmnop")
    assert retried
    saved = s._read_local()["jobs"][0]
    assert saved["status"] == "queued"
    assert "abcdefghijklmnop" not in saved["error"]


def test_frontend_has_safe_chat_runtime():
    source = Path("public/index.html").read_text("utf-8")
    assert 'id="chatInput"' in source
    assert 'id="historySearch"' in source
    assert "async function send" in source
    assert "innerHTML" in source
    assert "safeMarkdown" in source


def test_approval_run_can_only_be_claimed_once(tmp_path):
    from aria_agent.storage import AgentStore

    s = AgentStore()
    s._use_postgres = False
    from pathlib import Path
    s._path = Path(tmp_path) / "jobs.json"
    s._write_local(s._empty_local())
    s.save_run("run-1", "u", "openai", "gpt-test", "awaiting_approval", "in", "out", "state", {})
    assert s.claim_run_resume("u", "run-1") is True
    assert s.claim_run_resume("u", "run-1") is False


def test_cognitive_core_routes_without_an_llm():
    from aria_agent.intelligence import CognitiveCore
    frame = CognitiveCore().classify("Find me current remote jobs and help me apply")
    assert frame.intent == "jobs"
    assert frame.requires_web is True
    assert frame.requires_external_action is True
    assert "job_finder" in frame.workers


def test_native_core_handles_basic_requests():
    from aria_agent.intelligence import CognitiveCore
    core = CognitiveCore()
    assert core.native_response("hello", []) is not None
    assert core.native_response("what can you do?", []) is not None


def test_frontend_has_modern_chat_and_history_surface():
    source = Path("public/index.html").read_text("utf-8")
    assert "Conversation History" in source
    assert 'id="chatInput"' in source
    assert 'id="historySearch"' in source
    assert "async function uploadFile" in source


def test_groq_qwen38_is_primary_reasoning_provider(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    from aria_agent.runtime import AriaRuntime

    runtime = AriaRuntime.__new__(AriaRuntime)
    candidates = runtime.provider_candidates()
    assert candidates
    assert candidates[0][0] == "groq"
    assert candidates[0][1] == "qwen/qwen3.8-27b"


def test_cognitive_core_is_model_independent():
    from aria_agent.intelligence import CognitiveCore

    core = CognitiveCore()
    frame = core.classify("Find current remote jobs for me and help me prepare")
    assert frame.intent == "jobs"
    assert "job_finder" in frame.workers


def test_native_memory_and_math_primitives_are_executable(tmp_path):
    from aria_agent.runtime import AriaRuntime
    from aria_agent.storage import AgentStore
    from aria_agent.config import settings
    from pathlib import Path

    s = AgentStore()
    s._use_postgres = False
    s._path = Path(tmp_path) / "agent_store.json"
    s._write_local(s._empty_local())
    r = AriaRuntime(s)
    r.provider_candidates = lambda: []
    result = __import__("asyncio").run(r.run("u", "remember that my target is to become 1% better every day"))
    assert "Remembered:" in result["reply"]
    result = __import__("asyncio").run(r.run("u", "what is 12 * 3"))
    assert result["reply"] == "36.0"


def test_render_is_groq_only_and_reasoning_enabled_by_default():
    source = Path("render.yaml").read_text("utf-8")
    assert "OPENROUTER_API_KEY" not in source
    assert 'value: "groq"' in source
    assert 'value: "qwen/qwen3.8-27b"' in source
    assert 'value: "default"' in source


def test_chat_surfaces_backend_detail():
    source = Path("public/index.html").read_text("utf-8")
    assert "ARIA couldn't connect:" in source
    assert "const raw = await res.text()" in source


def test_reasoning_provider_does_not_send_unsupported_reasoning_format():
    runtime = Path("aria_agent/runtime.py").read_text("utf-8")
    workers = Path("aria_agent/workers.py").read_text("utf-8")
    assert "reasoning_format" not in runtime
    assert "reasoning_format" not in workers


def test_conversation_storage_contract(tmp_path):
    from aria_agent.storage import AgentStore
    from pathlib import Path

    store = AgentStore()
    store._use_postgres = False
    store._path = Path(tmp_path) / "agent_store.json"
    store._write_local(store._empty_local())
    convo = store.create_conversation("u", "Remember my goals")
    store.add_message(convo["id"], "u", "user", "Remember my goals")
    store.add_message(convo["id"], "u", "assistant", "I will remember that.")
    loaded = store.get_conversation("u", convo["id"])
    assert loaded["title"] == "Remember my goals"
    assert [m["role"] for m in loaded["messages"]] == ["user", "assistant"]
    listed = store.list_conversations("u")
    assert listed[0]["id"] == convo["id"]


def test_frontend_has_persistent_conversation_panel():
    source = Path("public/index.html").read_text("utf-8")
    assert 'id="recentList"' in source
    assert 'id="recentSearch"' in source
    assert 'id="newConversationBtn"' in source
    assert "function loadConversations()" in source
    assert "function openConversation(id)" in source
    assert "conversation_id: conversationId" in source


def test_runtime_uses_user_scoped_conversation_lookup():
    source = Path("aria_agent/runtime.py").read_text("utf-8")
    assert "self.store.get_conversation(user_id, conversation_id, include_messages=True)" in source
    assert "self.store.get_conversation(conversation_id, include_messages=True)" not in source
