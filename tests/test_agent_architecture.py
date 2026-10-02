from pathlib import Path


def test_worker_catalog_is_large_and_unique():
    from aria_agent.workers import WORKER_SPECS
    names = [x[0] for x in WORKER_SPECS]
    assert len(names) >= 40
    assert len(names) == len(set(names))
    assert {"job_finder", "job_creator", "income_architect", "sales_prospector", "automation_designer", "qa_reviewer"} <= set(names)


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


def test_local_job_does_not_run_before_run_after(tmp_path):
    from datetime import datetime, timedelta, timezone
    from aria_agent.storage import AgentStore
    store = AgentStore()
    store._use_postgres = False
    store._path = Path(tmp_path) / "agent_store.json"
    store._path.parent.mkdir(parents=True, exist_ok=True)
    store._write_local(store._empty_local())
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    store.enqueue_job("u", "research", {"goal": "later"}, future)
    assert store.claim_job() is None


def test_connector_danger_classification():
    from aria_agent.connectors import needs_mcp_approval
    assert needs_mcp_approval("delete_file")
    assert needs_mcp_approval("send_email")
    assert needs_mcp_approval("execute_sql")
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


def test_frontend_has_no_non_async_rating_handler():
    source = Path("public/index.html").read_text("utf-8")
    assert "async function sendRating(score, ratingDiv)" in source
    assert "function sendRating(score, ratingDiv)" not in source.replace("async function sendRating(score, ratingDiv)", "")
