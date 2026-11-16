import claude_provider


def test_default_model_is_current_family_and_config_is_optional(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("SWELL_CLAUDE_MODEL", raising=False)
    status = claude_provider.status()
    assert status["configured"] is False
    assert status["provider"] == "deterministic"
    assert status["model"] == "claude-sonnet-5"
    assert status["server_side_key"] is True


def test_model_can_be_overridden_without_exposing_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-secret-not-real")
    monkeypatch.setenv("SWELL_CLAUDE_MODEL", "claude-sonnet-4-6")
    status = claude_provider.status()
    assert status["configured"] is True
    assert status["model"] == "claude-sonnet-4-6"
    assert "test-secret-not-real" not in repr(status)
