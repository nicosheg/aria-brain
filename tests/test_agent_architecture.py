from pathlib import Path


def test_worker_catalog_is_large_and_unique():
    from aria_agent.workers import WORKER_SPECS
    names = [x[0] for x in WORKER_SPECS]
    assert len(names) >= 20
    assert len(names) == len(set(names))


def test_storage_local_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr("aria_agent.config.settings.data_dir", Path(tmp_path))
    monkeypatch.setattr("aria_agent.config.settings.database_url", "")
    from aria_agent.storage import AgentStore
    store = AgentStore()
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
