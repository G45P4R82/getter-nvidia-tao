import pytest

from tao_mcp import server


def test_mutations_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TAO_MCP_ALLOW_MUTATIONS", raising=False)
    with pytest.raises(PermissionError):
        server.tao_create_workspace.fn("test-workspace", "I_CONFIRM")


def test_workspace_name_is_validated(monkeypatch):
    monkeypatch.setenv("TAO_MCP_ALLOW_MUTATIONS", "true")
    with pytest.raises(ValueError):
        server.tao_create_workspace.fn("../escape", "I_CONFIRM")


def test_log_bound_is_validated():
    with pytest.raises(ValueError):
        server.tao_get_job_logs.fn("12345678", 50001)
