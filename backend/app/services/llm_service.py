from __future__ import annotations

import asyncio
import json
import re
import hashlib
import math
from importlib import import_module
from typing import Any, Type, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings, ChatOpenAI, OpenAIEmbeddings
from loguru import logger
from pydantic import BaseModel, SecretStr

from app.config import get_settings
from app.exceptions import LLMServiceError

settings = get_settings()

T = TypeVar("T", bound=BaseModel)

# Three attempts balances transient provider instability against user-visible latency.
STRUCTURED_EXTRACTION_MAX_ATTEMPTS = 3


def _is_non_retryable_llm_error(error: Exception) -> bool:
    """Return True for auth/config errors where retries only flood logs."""
    message = str(error).lower()
    non_retryable_markers = (
        "401",
        "unauthorized",
        "invalid api key",
        "invalid_api_key",
        "api key is not configured",
        "authentication",
    )
    return any(marker in message for marker in non_retryable_markers)


def _llm_retry_delay_seconds(error: Exception, attempt: int) -> float:
    message = str(error).lower()
    if "rate_limit" not in message and "429" not in message:
        return min(2.0 * (attempt + 1), 6.0)
    match = re.search(r"try again in\s+([0-9.]+)\s*(ms|s|sec|second|seconds)?", message)
    if match:
        value = float(match.group(1))
        unit = match.group(2) or "s"
        if unit == "ms":
            value = value / 1000
        return min(max(value + 0.75, 1.0), 12.0)
    return min(4.0 * (attempt + 1), 12.0)


class DeterministicHashEmbeddings:
    """
    Local fallback embeddings for Groq-only setups.

    Groq currently provides chat models, not an embedding API. This lightweight
    hashed bag-of-words embedder keeps retrieval deterministic and non-random
    when OpenAI/Azure/Ollama embeddings are not configured.
    """

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_.+#/-]{1,}", text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)


class LLMService:
    """
    Central AI service layer.
    Provides:
      - get_chat_model()  → LangChain chat model for agent use
      - get_embeddings()  → LangChain embeddings model
      - structured_extract() → JSON-mode structured extraction with retry
      - complete()        → Simple single-turn completion
    """

    def __init__(self) -> None:
        self._chat_model: BaseChatModel | None = None
        self._embeddings: Any | None = None
        self._chat_disabled_reason: str | None = None
        self._groq_key_index = 0

    def _next_groq_api_key(self) -> str:
        keys = settings.groq_api_keys
        if not keys:
            raise LLMServiceError("Groq API key is not configured.")
        key = keys[self._groq_key_index % len(keys)]
        self._groq_key_index += 1
        return key

    # ── Chat Model ─────────────────────────────────────────────────────
    def get_chat_model(
        self,
        *,
        temperature: float = 0.2,
        streaming: bool = False,
        model_name: str | None = None,
    ) -> BaseChatModel:
        """Returns the configured chat model. Always use this — never instantiate directly."""
        provider = settings.LLM_PROVIDER.lower()
        selected_model = model_name or settings.LLM_MODEL

        if provider == "azure":
            if not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_ENDPOINT:
                raise LLMServiceError("Azure OpenAI credentials are not configured.")
            return AzureChatOpenAI(  # type: ignore[call-arg,arg-type]
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                azure_deployment=model_name or settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                api_key=SecretStr(settings.AZURE_OPENAI_API_KEY),
                temperature=temperature,
                streaming=streaming,
                timeout=120,
                max_retries=3,
            )

        if provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise LLMServiceError("OpenAI API key is not configured.")
            return ChatOpenAI(  # type: ignore[call-arg,arg-type]
                model=selected_model,
                api_key=SecretStr(settings.OPENAI_API_KEY),
                temperature=temperature,
                streaming=streaming,
                timeout=120,
                max_retries=3,
            )

        if provider == "google":
            try:
                google_module = import_module("langchain_google_genai")
                chat_google = getattr(google_module, "ChatGoogleGenerativeAI")
            except (ImportError, AttributeError) as exc:
                raise LLMServiceError(
                    "langchain-google-genai is not installed. Run: pip install langchain-google-genai"
                ) from exc
            if not settings.GOOGLE_API_KEY:
                raise LLMServiceError("Google API key is not configured.")
            return chat_google(
                model=selected_model if model_name else "gemini-1.5-pro",
                google_api_key=SecretStr(settings.GOOGLE_API_KEY),
                temperature=temperature,
                streaming=streaming,
            )

        if provider == "groq":
            try:
                from langchain_groq import ChatGroq
            except ImportError as exc:
                raise LLMServiceError(
                    "langchain-groq is not installed. Run: pip install langchain-groq"
                ) from exc
            return ChatGroq(  # type: ignore[call-arg,arg-type]
                model=selected_model,
                api_key=SecretStr(self._next_groq_api_key()),
                temperature=temperature,
                streaming=streaming,
                timeout=120,
                max_retries=3,
            )

        if provider == "ollama":
            base_url = settings.OLLAMA_URL
            if "api/generate" in base_url:
                base_url = base_url.replace("api/generate", "v1").rstrip("/")
            elif not base_url.endswith("/v1"):
                base_url = base_url.rstrip("/") + "/v1"

            return ChatOpenAI(  # type: ignore[call-arg,arg-type]
                base_url=base_url,
                model=selected_model,
                api_key=SecretStr("ollama"),
                temperature=temperature,
                streaming=streaming,
                timeout=120,
                max_retries=3,
            )

        raise LLMServiceError(
            f"Unknown LLM provider: '{provider}'. Valid: openai | azure | google | groq | ollama"
        )

    # ── Embeddings ─────────────────────────────────────────────────────
    def get_embeddings(self):
        """Returns the configured embeddings model. Cached after first call."""
        if self._embeddings is not None:
            return self._embeddings

        provider = settings.LLM_PROVIDER.lower()

        if provider == "azure":
            self._embeddings = AzureOpenAIEmbeddings(
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=SecretStr(settings.AZURE_OPENAI_API_KEY),
                api_version=settings.AZURE_OPENAI_API_VERSION,
                model=settings.EMBEDDING_MODEL,
            )
        elif provider == "ollama":
            from langchain_community.embeddings import OllamaEmbeddings
            base_url = settings.OLLAMA_URL.replace("/api/generate", "")
            self._embeddings = OllamaEmbeddings(
                base_url=base_url,
                model=settings.EMBEDDING_MODEL or "nomic-embed-text",
            )
        elif provider == "groq" and not settings.OPENAI_API_KEY:
            logger.warning(
                "Groq does not provide embeddings and OPENAI_API_KEY is not set. "
                "Using deterministic local hash embeddings for retrieval."
            )
            self._embeddings = DeterministicHashEmbeddings(settings.EMBEDDING_DIMENSIONS)
        else:
            self._embeddings = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                api_key=SecretStr(settings.OPENAI_API_KEY),
                dimensions=settings.EMBEDDING_DIMENSIONS,
            )

        return self._embeddings

    # ── Structured Extraction ──────────────────────────────────────────
    async def structured_extract(
        self,
        system_prompt: str,
        user_content: str,
        output_schema: Type[T],
        *,
        temperature: float = 0.0,
        model_name: str | None = None,
    ) -> T:
        """
        Extracts structured data from text using JSON-mode / with_structured_output.
        Retries up to 2 times on parse failure.
        """
        if self._chat_disabled_reason:
            raise LLMServiceError(self._chat_disabled_reason)

        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]

        last_error: Exception | None = None
        for attempt in range(STRUCTURED_EXTRACTION_MAX_ATTEMPTS):
            model = self.get_chat_model(temperature=temperature, model_name=model_name)
            try:
                structured_model = model.with_structured_output(
                    output_schema,
                    method="json_mode",
                    strict=True,
                )
            except (TypeError, ValueError, NotImplementedError) as exc:
                logger.debug(f"Strict JSON structured output setup unavailable; falling back to default method: {exc}")
                structured_model = model.with_structured_output(output_schema)

            try:
                result = await structured_model.ainvoke(messages)
                # If result is already parsed Pydantic schema
                if isinstance(result, output_schema):
                    return result
                elif isinstance(result, dict):
                    return output_schema.model_validate(result)
            except Exception as e:
                last_error = e
                if _is_non_retryable_llm_error(e):
                    self._chat_disabled_reason = (
                        "LLM provider authentication/configuration failed. "
                        "Fix the API key and restart the backend/Celery worker."
                    )
                    logger.warning(
                        "Structured extraction skipped retries because the LLM provider "
                        "returned an auth/config error. Check the configured API key."
                    )
                    raise LLMServiceError(self._chat_disabled_reason)

                logger.warning(
                    f"Standard structured extraction attempt {attempt + 1} failed: {e}. "
                    f"Trying regex fallback."
                )
                await asyncio.sleep(_llm_retry_delay_seconds(e, attempt))
                try:
                    # Robust custom JSON extraction fallback matching the user's implementation
                    fallback_response = await model.ainvoke(messages)
                    content = str(fallback_response.content).strip()
                    parsed_dict = self._safe_extract_json(content)
                    return output_schema.model_validate(parsed_dict)
                except Exception as fallback_error:
                    if _is_non_retryable_llm_error(fallback_error):
                        self._chat_disabled_reason = (
                            "LLM provider authentication/configuration failed. "
                            "Fix the API key and restart the backend/Celery worker."
                        )
                        logger.warning(
                            "Regex fallback skipped retries because the LLM provider "
                            "returned an auth/config error. Check the configured API key."
                        )
                        raise LLMServiceError(self._chat_disabled_reason)

                    logger.error(f"Fallback extraction failed: {fallback_error}")
                    if attempt == STRUCTURED_EXTRACTION_MAX_ATTEMPTS - 1:
                        raise LLMServiceError(
                            f"Structured extraction failed after {STRUCTURED_EXTRACTION_MAX_ATTEMPTS} attempts: {str(e)} -> {str(fallback_error)}"
                        )
                    await asyncio.sleep(_llm_retry_delay_seconds(fallback_error, attempt))

        raise LLMServiceError(f"Structured extraction failed unexpectedly: {last_error}")

    # ── Simple Completion ─────────────────────────────────────────────
    async def complete(
        self,
        system_prompt: str,
        user_content: str,
        *,
        temperature: float = 0.3,
        model_name: str | None = None,
    ) -> str:
        """Single-turn completion returning plain text."""
        model = self.get_chat_model(temperature=temperature, model_name=model_name)
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
        try:
            response = await model.ainvoke(messages)
            return str(response.content)
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            raise LLMServiceError(f"LLM completion failed: {str(e)}")

    # ── Embed Text ─────────────────────────────────────────────────────
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts and return vectors."""
        embeddings_model = self.get_embeddings()
        try:
            # Check if model has async method
            if hasattr(embeddings_model, "aembed_documents"):
                return await embeddings_model.aembed_documents(texts)
            else:
                return embeddings_model.embed_documents(texts)
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise LLMServiceError(f"Embedding generation failed: {str(e)}")

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        embeddings_model = self.get_embeddings()
        try:
            if hasattr(embeddings_model, "aembed_query"):
                return await embeddings_model.aembed_query(text)
            else:
                return embeddings_model.embed_query(text)
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            raise LLMServiceError(f"Query embedding failed: {str(e)}")

    # ── Safe JSON Extraction Helper ────────────────────────────────────
    def _safe_extract_json(self, content: str) -> dict[str, Any]:
        """Custom regex-based decoder to extract and merge JSON dictionary objects safely."""
        cleaned_content = re.sub(r"```json|```", "", content).strip()
        decoder = json.JSONDecoder()
        idx = 0
        results = []

        while idx < len(cleaned_content):
            try:
                obj, end = decoder.raw_decode(cleaned_content[idx:])
                results.append(obj)
                idx += end
            except json.JSONDecodeError as exc:
                logger.debug(f"Skipping invalid JSON fragment while scanning LLM response: {exc}")
                idx += 1

        if not results:
            # Try plain regex search for { ... } as last resort
            json_match = re.search(r"\{.*\}", cleaned_content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError as exc:
                    logger.debug(f"Regex JSON extraction failed to decode matched content: {exc}")
            raise ValueError("No valid JSON found in LLM response content")

        merged = {}
        for r in results:
            if isinstance(r, dict):
                merged.update(r)

        if not isinstance(merged, dict) or not merged:
            raise ValueError("Parsed response content is not a valid, non-empty JSON object")

        return merged


# ── Singleton Instance ─────────────────────────────────────────────────────
_llm_service_instance: LLMService | None = None


def get_llm_service() -> LLMService:
    """FastAPI dependency and general accessor for the LLM service."""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
