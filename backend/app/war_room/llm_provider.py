from __future__ import annotations

from typing import Any, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class WarRoomLLMProvider:
    """Provider wrapper so agents never talk to vendor SDKs directly."""

    async def structured_output(
        self,
        *,
        system_prompt: str,
        user_content: str,
        output_schema: Type[T],
        temperature: float = 0.2,
        model_name: str | None = None,
    ) -> T | None:
        try:
            from app.services.llm_service import get_llm_service
            return await get_llm_service().structured_extract(
                system_prompt=system_prompt,
                user_content=user_content,
                output_schema=output_schema,
                temperature=temperature,
                model_name=model_name,
            )
        except Exception:
            return None

    async def complete(
        self,
        *,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.2,
        model_name: str | None = None,
    ) -> str | None:
        try:
            from app.services.llm_service import get_llm_service
            return await get_llm_service().complete(
                system_prompt=system_prompt,
                user_content=user_content,
                temperature=temperature,
                model_name=model_name,
            )
        except Exception:
            return None


_provider: WarRoomLLMProvider | None = None


def get_war_room_llm_provider() -> WarRoomLLMProvider:
    global _provider
    if _provider is None:
        _provider = WarRoomLLMProvider()
    return _provider
