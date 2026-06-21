from __future__ import annotations

import asyncio
from pathlib import Path
import sys

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.services.llm_service import get_llm_service  # noqa: E402


class DiagnosticOutput(BaseModel):
    answer: str


def _provider_key_name(provider: str) -> str | None:
    return {
        "azure": "AZURE_OPENAI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "ollama": None,
    }.get(provider.lower())


async def main() -> None:
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower()
    key_name = _provider_key_name(provider)

    print(f"LLM_PROVIDER={settings.LLM_PROVIDER}")
    if key_name:
        key_value = getattr(settings, key_name, "")
        print(f"{key_name}_SET={bool(str(key_value).strip())}")
    else:
        print("API_KEY_REQUIRED=False")

    try:
        result = await get_llm_service().structured_extract(
            system_prompt="Return JSON that matches the schema.",
            user_content='Return {"answer": "war room llm diagnostic ok"}.',
            output_schema=DiagnosticOutput,
            temperature=0.0,
        )
    except Exception as exc:
        print(f"EXCEPTION_TYPE={type(exc).__name__}")
        print(f"EXCEPTION_MESSAGE={exc}")
        raise

    print(f"RESULT={result.model_dump()}")


if __name__ == "__main__":
    asyncio.run(main())
