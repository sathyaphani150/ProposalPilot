from __future__ import annotations

import pytest

from app.war_room import llm_provider as war_room_llm_provider


@pytest.mark.asyncio
async def test_structured_output_logs_warning_when_llm_service_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    class _FakeLogger:
        def warning(self, message: str) -> None:
            captured.append(message)

    class _BoomService:
        async def structured_extract(self, **_: object) -> object:
            raise RuntimeError("boom")

    monkeypatch.setattr(war_room_llm_provider, "logger", _FakeLogger())
    monkeypatch.setattr("app.services.llm_service.get_llm_service", lambda: _BoomService())

    provider = war_room_llm_provider.WarRoomLLMProvider()
    result = await provider.structured_output(
        system_prompt="system",
        user_content="content",
        output_schema=type("DummyModel", (), {}),
    )

    assert result is None
    assert captured
    assert "War room agent LLM call failed (RuntimeError): boom." in captured[0]
