from __future__ import annotations

import json
import re
from typing import Any, Type, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings, ChatOpenAI, OpenAIEmbeddings
from loguru import logger
from pydantic import BaseModel

from app.config import get_settings
from app.exceptions import LLMServiceError

settings = get_settings()

T = TypeVar("T", bound=BaseModel)


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
        self._embeddings = None

    # ── Chat Model ─────────────────────────────────────────────────────
    def get_chat_model(
        self,
        *,
        temperature: float = 0.2,
        streaming: bool = False,
        max_tokens: int = 4096,
    ) -> BaseChatModel:
        """Returns the configured chat model. Always use this — never instantiate directly."""
        provider = settings.LLM_PROVIDER.lower()

        if provider == "azure":
            if not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_ENDPOINT:
                raise LLMServiceError("Azure OpenAI credentials are not configured.")
            return AzureChatOpenAI(
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                api_key=settings.AZURE_OPENAI_API_KEY,
                temperature=temperature,
                streaming=streaming,
                max_tokens=max_tokens,
                request_timeout=120,
                max_retries=3,
            )

        if provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise LLMServiceError("OpenAI API key is not configured.")
            return ChatOpenAI(
                model=settings.LLM_MODEL,
                api_key=settings.OPENAI_API_KEY,
                temperature=temperature,
                streaming=streaming,
                max_tokens=max_tokens,
                request_timeout=120,
                max_retries=3,
            )

        if provider == "google":
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
            except ImportError:
                raise LLMServiceError(
                    "langchain-google-genai is not installed. Run: pip install langchain-google-genai"
                )
            if not settings.GOOGLE_API_KEY:
                raise LLMServiceError("Google API key is not configured.")
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-pro",
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=temperature,
                streaming=streaming,
                max_output_tokens=max_tokens,
            )

        if provider == "groq":
            if not settings.GROQ_API_KEY:
                raise LLMServiceError("Groq API key is not configured.")
            return ChatOpenAI(
                base_url="https://api.groq.com/openai/v1",
                model=settings.LLM_MODEL,
                api_key=settings.GROQ_API_KEY,
                temperature=temperature,
                streaming=streaming,
                max_tokens=max_tokens,
                request_timeout=120,
                max_retries=3,
            )

        if provider == "ollama":
            base_url = settings.OLLAMA_URL
            if "api/generate" in base_url:
                base_url = base_url.replace("api/generate", "v1").rstrip("/")
            elif not base_url.endswith("/v1"):
                base_url = base_url.rstrip("/") + "/v1"

            return ChatOpenAI(
                base_url=base_url,
                model=settings.LLM_MODEL,
                api_key="ollama",
                temperature=temperature,
                streaming=streaming,
                max_tokens=max_tokens,
                request_timeout=120,
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
                api_key=settings.AZURE_OPENAI_API_KEY,
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
            # Fallback for offline/development if no OpenAI key for embeddings is provided
            try:
                from langchain_community.embeddings import HuggingFaceEmbeddings
                self._embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            except Exception:
                logger.warning(
                    f"No OpenAI key or HuggingFace libraries found for embeddings. "
                    f"Falling back to mock embeddings of dimension {settings.EMBEDDING_DIMENSIONS}."
                )

                class MockEmbeddings:
                    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
                        return [[0.0] * settings.EMBEDDING_DIMENSIONS for _ in texts]

                    async def aembed_query(self, text: str) -> list[float]:
                        return [0.0] * settings.EMBEDDING_DIMENSIONS

                    def embed_documents(self, texts: list[str]) -> list[list[float]]:
                        return [[0.0] * settings.EMBEDDING_DIMENSIONS for _ in texts]

                    def embed_query(self, text: str) -> list[float]:
                        return [0.0] * settings.EMBEDDING_DIMENSIONS

                self._embeddings = MockEmbeddings()
        else:
            self._embeddings = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                api_key=settings.OPENAI_API_KEY,
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
    ) -> T:
        """
        Extracts structured data from text using JSON-mode / with_structured_output.
        Retries up to 2 times on parse failure.
        """
        model = self.get_chat_model(temperature=temperature)

        # Standard with_structured_output path
        try:
            structured_model = model.with_structured_output(
                output_schema,
                method="json_mode",
                strict=True,
            )
        except Exception:
            structured_model = model.with_structured_output(output_schema)

        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]

        for attempt in range(3):
            try:
                result = await structured_model.ainvoke(messages)
                # If result is already parsed Pydantic schema
                if isinstance(result, output_schema):
                    return result
                elif isinstance(result, dict):
                    return output_schema.model_validate(result)
            except Exception as e:
                logger.warning(
                    f"Standard structured extraction attempt {attempt + 1} failed: {e}. "
                    f"Trying regex fallback."
                )
                try:
                    # Robust custom JSON extraction fallback matching the user's implementation
                    fallback_response = await model.ainvoke(messages)
                    content = str(fallback_response.content).strip()
                    parsed_dict = self._safe_extract_json(content)
                    return output_schema.model_validate(parsed_dict)
                except Exception as fallback_error:
                    logger.error(f"Fallback extraction failed: {fallback_error}")
                    if attempt == 2:
                        raise LLMServiceError(
                            f"Structured extraction failed after 3 attempts: {str(e)} -> {str(fallback_error)}"
                        )

        raise LLMServiceError("Structured extraction failed unexpectedly.")

    # ── Simple Completion ─────────────────────────────────────────────
    async def complete(
        self,
        system_prompt: str,
        user_content: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Single-turn completion returning plain text."""
        model = self.get_chat_model(temperature=temperature, max_tokens=max_tokens)
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
            except Exception:
                idx += 1

        if not results:
            # Try plain regex search for { ... } as last resort
            json_match = re.search(r"\{.*\}", cleaned_content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except Exception:
                    pass
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
