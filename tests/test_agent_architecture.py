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


def test_immediate_business_advice_does_not_force_slow_research_route():
    from aria_agent.intelligence import CognitiveCore
    from aria_agent.runtime import AriaRuntime

    core = CognitiveCore()
    frame = core.classify("If I wanted to start a business now what are your top 3 best advice for me")
    assert frame.requires_web is False
    runtime = AriaRuntime.__new__(AriaRuntime)
    assert runtime._should_use_fast_lane(frame) is True


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
    from aria_agent.runtime import AriaRuntime

    for name in (
        "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY",
        "OPENROUTER_API_KEY", "DASHSCOPE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    for prefix in ("GROQ_KEY", "OPENAI_KEY", "DEEPSEEK_KEY", "GEMINI_KEY", "OPENROUTER_KEY", "DASHSCOPE_KEY"):
        for index in range(1, 21):
            monkeypatch.delenv(f"{prefix}_{index}", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("ARIA_PROVIDER", "groq")
    runtime = AriaRuntime.__new__(AriaRuntime)
    runtime._rejected_provider_keys = set()
    candidates = runtime.provider_candidates()
    assert candidates
    assert candidates[0][0] == "groq"
    assert candidates[0][1] == "qwen/qwen3.8-27b"
    assert len(candidates[0]) == 4


def test_provider_fallback_supports_configured_providers_and_skips_rejected_keys(monkeypatch):
    from aria_agent.runtime import AriaRuntime

    for name in (
        "GROQ_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY",
        "OPENROUTER_API_KEY", "DASHSCOPE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    for prefix in ("GROQ_KEY", "OPENAI_KEY", "DEEPSEEK_KEY", "GEMINI_KEY", "OPENROUTER_KEY", "DASHSCOPE_KEY"):
        for index in range(1, 21):
            monkeypatch.delenv(f"{prefix}_{index}", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv("ARIA_PROVIDER", "groq")

    runtime = AriaRuntime.__new__(AriaRuntime)
    runtime._rejected_provider_keys = set()
    candidates = runtime.provider_candidates()
    assert [candidate[0] for candidate in candidates[:2]] == ["groq", "openai"]
    bad_fingerprint = runtime._key_fingerprint("groq", "groq-test-key")
    runtime._rejected_provider_keys.add(bad_fingerprint)
    candidates_after_rejection = runtime.provider_candidates()
    assert not any(candidate[3] == bad_fingerprint for candidate in candidates_after_rejection)
    assert any(candidate[0] == "openai" for candidate in candidates_after_rejection)


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


def test_render_declares_fallback_providers_and_keeps_groq_as_default():
    source = Path("render.yaml").read_text("utf-8")
    assert "OPENAI_API_KEY" in source
    assert "DEEPSEEK_API_KEY" in source
    assert "GEMINI_API_KEY" in source
    assert "OPENROUTER_API_KEY" in source
    assert "DASHSCOPE_API_KEY" in source
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


def test_frontend_keeps_history_out_of_the_chat_and_uses_fullscreen_archive():
    source = Path("public/index.html").read_text("utf-8")
    assert 'id="historyBtn"' in source
    assert 'id="historyNewConversationBtn"' in source
    assert 'aria-label="Open conversation history"' in source
    assert "🕘" not in source
    assert 'class="recent-panel"' not in source
    assert "thread.className = 'history-thread'" in source
    assert "label.className = 'history-message-label'" in source
    assert "function fetchHistory()" in source
    assert "/conversations?limit=200" in source
    assert "conversation_id: conversationId" in source


def test_runtime_uses_user_scoped_conversation_lookup():
    source = Path("aria_agent/runtime.py").read_text("utf-8")
    assert "self.store.get_conversation(user_id, conversation_id)" in source
    assert "transcript_messages=prior_messages" in source
    assert "self.store.get_conversation(conversation_id, include_messages=True)" not in source


def test_runtime_has_fast_conversation_lane_and_auth_fallback():
    source = Path("aria_agent/runtime.py").read_text("utf-8")
    assert "async def _fast_conversation" in source
    assert "def _should_use_fast_lane" in source
    assert "self._is_authentication_error(exc)" in source
    assert 'request_args["reasoning_effort"] = "none"' in source


def test_frontend_does_not_fetch_aria_uid_before_each_chat_and_refreshes_expired_auth():
    source = Path("public/index.html").read_text("utf-8")
    assert "authenticatedFetch('/chat'" in source
    assert "if (response.status === 401 && currentUser)" in source
    assert "Ensure we have ARIA UID" not in source


def test_chat_authentication_error_is_provider_agnostic_and_user_safe():
    source = Path("main.py").read_text("utf-8")
    assert "The AI provider rejected the configured credentials" in source
    assert "Never share keys in chat" in source


def test_memory_is_idempotent_and_distinct_from_conversation_history(tmp_path):
    from pathlib import Path
    from aria_agent.storage import AgentStore

    s = AgentStore()
    s._use_postgres = False
    s._path = Path(tmp_path) / "memory.json"
    s._write_local(s._empty_local())

    first = s.add_memory("u", "profile", "The user's preferred name is Egwame Nicholas.", importance=0.85)
    second = s.add_memory("u", "profile", "The user's preferred name is Egwame Nicholas.", importance=0.85)
    s.add_memory("u", "conversation_user", "Hi", importance=0.35)
    s.add_memory("u", "conversation_assistant", "Hello", importance=0.35)

    assert first == second
    assert len(s.recent_memory("u")) == 1
    assert s.recent_memory("u")[0]["kind"] == "profile"
    assert s.search_memory("u", "Hi") == []


def test_opportunity_request_routes_to_small_relevant_worker_set():
    from aria_agent.intelligence import CognitiveCore

    frame = CognitiveCore().classify("Help me find my next opportunity")
    assert frame.requires_web is True
    assert "opportunity_scout" in frame.workers
    assert len(frame.workers) <= 4


def test_fast_chat_reads_only_preexisting_transcript_and_never_persists_chat_as_memory():
    from pathlib import Path

    runtime = Path("aria_agent/runtime.py").read_text("utf-8")
    assert "transcript_messages: list[dict] | None = None" in runtime
    assert "transcript_messages=prior_messages" in runtime
    assert 'self.store.add_memory(user_id, "conversation_user"' not in runtime
    assert 'self.store.add_memory(user_id, "conversation_assistant"' not in runtime


def test_render_does_not_define_removed_reasoning_format():
    source = Path("render.yaml").read_text("utf-8")
    assert "ARIA_REASONING_FORMAT" not in source


def test_native_memory_reply_uses_real_newlines():
    from aria_agent.intelligence import CognitiveCore

    reply = CognitiveCore().native_response(
        "What do you remember about me?",
        [{"kind": "profile", "content": "Preferred name is Nicholas."}],
    )
    assert reply is not None
    assert "\n" in reply
    assert "\\n" not in reply


def test_legacy_repeated_memory_reply_is_deduplicated_when_loaded_from_history():
    from aria_agent.storage import normalize_legacy_memory_reply

    old_reply = (
        "Here is the most recent durable context I have:\n"
        "• The user's preferred name is Egwame Nicholas.\n"
        "• The user's preferred name is Egwame Nicholas.\n"
        "• The user's preferred name is Egwame Nicholas.\n"
        "• The user's preferred name is Egwame Nicholas."
    )
    cleaned = normalize_legacy_memory_reply("assistant", old_reply)
    assert cleaned.count("The user's preferred name is Egwame Nicholas.") == 1
    assert cleaned.startswith("Here is the most recent durable context I have:")
    assert "\n" in cleaned and "\\n" not in cleaned

    # Do not silently rewrite normal dialogue or user-authored content.
    assert normalize_legacy_memory_reply("assistant", "Hi\nHi") == "Hi\nHi"
    assert normalize_legacy_memory_reply("user", old_reply) == old_reply


def test_all_45_specialists_are_addressable_by_the_cognitive_router():
    from aria_agent.intelligence import WORKER_KEYWORDS, CognitiveCore
    from aria_agent.workers import WORKER_SPECS

    registered = {name for name, _ in WORKER_SPECS}
    assert len(registered) == 45
    assert set(WORKER_KEYWORDS) == registered
    assert len(WORKER_KEYWORDS) == len(registered)

    examples = {
        "job_alert_monitor": "Set up a job alert and notify me about new jobs",
        "remote_work_scout": "Find remote work from home opportunities",
        "local_opportunity_scout": "Find local opportunities in Lagos",
        "application_builder": "Write a tailored cover letter for this job application",
        "interview_drill": "Run a mock interview and score my answers",
        "offer_pricer": "What should I charge for this service? Help with pricing",
        "lead_list_builder": "Build a lead list of companies to contact",
        "outreach_operator": "Write a cold email outreach sequence",
        "personal_brand": "Improve my personal brand and LinkedIn profile",
        "scam_risk_checker": "Is this job offer a scam?",
        "job_creator": "Write a job description for a new hire",
        "recruiter": "Help me shortlist candidates for recruitment",
        "hiring_ops": "Design our hiring process and onboarding process",
        "data_operator": "Clean this spreadsheet and deduplicate the data",
        "daily_improvement": "Help me become 1% better every day",
        "personal_ops": "Organize my week and manage my routine",
    }
    core = CognitiveCore()
    for worker, prompt in examples.items():
        frame = core.classify(prompt)
        assert worker in frame.workers, (worker, frame.workers)


def test_publisher_profiles_are_hints_not_claims_of_truth():
    from aria_agent.tools import _source_profile

    official = _source_profile("https://www.cbn.gov.ng/monetary-policy/")
    listing = _source_profile("https://www.jobberman.com/jobs/software-engineer")
    unknown = _source_profile("https://example-unverified.test/article")
    assert official["publisher_class"] == "government_or_regulator_domain"
    assert listing["publisher_class"] == "recognized_listing_platform"
    assert unknown["publisher_class"] == "third_party_unverified"
    assert "heuristic" in official["publisher_assessment"].lower()

    technical_docs = _source_profile("https://platform.openai.com/docs/api-reference")
    news = _source_profile("https://www.reuters.com/world/")
    assert technical_docs["publisher_class"] == "primary_technical_documentation"
    assert news["publisher_class"] == "established_news_or_research_publisher"


def test_feedback_changes_routing_only_after_three_linked_ratings(tmp_path):
    from pathlib import Path
    from aria_agent.storage import AgentStore
    from aria_agent.intelligence import CognitiveCore

    s = AgentStore()
    s._use_postgres = False
    s._path = Path(tmp_path) / "online-learning.json"
    s._write_local(s._empty_local())

    for index, score in enumerate((5, 5, 4), start=1):
        run_id = f"learning-run-{index}"
        s.save_run(
            run_id, "user-1", "test", "test-model", "completed",
            "find me current jobs", "Source-backed result",
            metadata={"worker_names": ["job_finder", "role_matcher"], "intent": "jobs"},
        )
        s.add_feedback("user-1", score, run_id=run_id)

    profile = s.worker_feedback_profile("user-1")
    assert profile["job_finder"]["samples"] == 3
    assert profile["job_finder"]["average_score"] == 4.667
    frame = CognitiveCore().classify("Find current jobs", worker_weights=profile)
    assert "job_finder" in frame.workers
    assert s.worker_feedback_profile("another-user") == {}


def test_worker_building_exposes_shared_read_only_research_tools_and_parallel_consultation():
    runtime = Path("aria_agent/runtime.py").read_text("utf-8")
    workers = Path("aria_agent/workers.py").read_text("utf-8")
    tools = Path("aria_agent/tools.py").read_text("utf-8")
    assert '("web_search", "job_search", "web_fetch", "calculator", "search_memory")' in runtime
    assert "consult_specialists_in_parallel" in runtime
    assert "asyncio.gather" in runtime
    assert "SOURCE AND EVIDENCE CONTRACT" in workers
    assert "publisher_class" in tools
    assert '"opened_page"' in tools


def test_response_feedback_is_run_linked_and_no_silent_model_retraining_claim():
    main_source = Path("main.py").read_text("utf-8")
    ui = Path("public/index.html").read_text("utf-8")
    assert "run_id: runId || null" in ui
    assert "store.worker_feedback_profile(user_id)" in Path("aria_agent/runtime.py").read_text("utf-8")
    assert "foundation-model retraining" in main_source
    assert "The rated ARIA response was not found for this user." in main_source


def test_every_worker_has_a_route_phrase_that_selects_it():
    from aria_agent.intelligence import WORKER_KEYWORDS, CognitiveCore

    core = CognitiveCore()
    for worker, phrases in WORKER_KEYWORDS.items():
        phrase = max(phrases, key=len)
        frame = core.classify(phrase)
        assert worker in frame.workers, (worker, phrase, frame.workers)


def test_research_output_requires_opened_direct_source_and_appends_links():
    from aria_agent.runtime import _attach_opened_source_evidence

    blocked = _attach_opened_source_evidence("Generic answer", [], requires_web=True)
    assert "I couldn't verify" in blocked
    assert "Generic answer" not in blocked

    only_search_result = [{
        "access": "search_result",
        "url": "https://example.org/result",
        "title": "Search result",
    }]
    blocked_search = _attach_opened_source_evidence("Unverified", only_search_result, requires_web=True)
    assert "I couldn't verify" in blocked_search

    untrusted_page = [{
        "access": "opened_page",
        "url": "https://example-unverified.test/article",
        "title": "Unverified blog",
        "publisher_class": "third_party_unverified",
    }]
    blocked_untrusted = _attach_opened_source_evidence("Unsupported claim", untrusted_page, requires_web=True)
    assert "could not establish" in blocked_untrusted
    assert "Unsupported claim" not in blocked_untrusted
    assert "https://example-unverified.test/article" in blocked_untrusted

    opened = [{
        "access": "opened_page",
        "url": "https://www.cbn.gov.ng/example",
        "title": "Official page",
        "publisher_class": "government_or_regulator_domain",
        "retrieved_at": "2026-10-14T06:00:00+00:00",
    }]
    result = _attach_opened_source_evidence("Verified research summary", opened, requires_web=True)
    assert result.startswith("Verified research summary")
    assert "Direct source pages opened" in result
    assert "https://www.cbn.gov.ng/example" in result
    assert "government or regulator domain" in result


def test_non_web_specialist_tasks_use_specialist_lane_but_generic_advice_stays_fast():
    from aria_agent.intelligence import CognitiveCore
    from aria_agent.runtime import AriaRuntime

    core = CognitiveCore()
    runtime = AriaRuntime.__new__(AriaRuntime)

    advice = core.classify("If I wanted to start a business now what are your top 3 best advice for me")
    assert runtime._should_use_fast_lane(advice) is True

    cover_letter = core.classify("Write a tailored cover letter for this role")
    assert "application_builder" in cover_letter.workers
    assert cover_letter.requires_web is False
    assert runtime._should_use_fast_lane(cover_letter) is False
