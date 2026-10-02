import pytest

from aria_agent.connectors import needs_mcp_approval
from aria_agent.tools import _assert_public_url


def test_private_targets_are_blocked():
    with pytest.raises(ValueError):
        _assert_public_url("http://127.0.0.1:8000")
    with pytest.raises(ValueError):
        _assert_public_url("http://localhost")
    with pytest.raises(ValueError):
        _assert_public_url("http://169.254.169.254")


def test_public_url_shape_is_allowed():
    _assert_public_url("https://example.com")


def test_mcp_side_effect_words_require_approval():
    assert needs_mcp_approval("send_email")
    assert needs_mcp_approval("delete_record")
    assert needs_mcp_approval("execute_sql")
    assert not needs_mcp_approval("search_records")


def test_mcp_approval_policy_has_explicit_safe_and_risky_values():
    from aria_agent.connectors import needs_mcp_approval
    assert needs_mcp_approval("read_calendar") is False
    assert needs_mcp_approval("create_event") is True
    assert needs_mcp_approval("submit_application") is True
