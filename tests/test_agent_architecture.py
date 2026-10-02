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


def test_frontend_had_no_await_in_non_async_rating_handler():
    source = Path("public/index.html").read_text("utf-8")
    assert "async function sendRating" in source
    assert "\n    function sendRating(score, ratingDiv)" not in source
    assert "safeMarkdown(text)" in source
