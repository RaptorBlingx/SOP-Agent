"""LLM and embedding factory — single source of truth for all model init.

Supports four provider lanes: gemini, openai, anthropic, ollama.
Includes structured-output binding, retry logic, and rate limiting.
"""

from __future__ import annotations

import asyncio
from typing import Any, Type

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("llm_factory")

# ---------------------------------------------------------------------------
# Per-provider semaphore for basic rate limiting (Section 12.5)
# ---------------------------------------------------------------------------
_provider_semaphores: dict[str, asyncio.Semaphore] = {}


def _get_semaphore(provider: str) -> asyncio.Semaphore:
    if provider not in _provider_semaphores:
        _provider_semaphores[provider] = asyncio.Semaphore(10)
    return _provider_semaphores[provider]


# ---------------------------------------------------------------------------
# LLM Factory (Section 10.1)
# ---------------------------------------------------------------------------

def get_llm(temperature: float = 0.1) -> BaseChatModel:
    """Create an LLM instance based on the configured provider."""
    settings = get_settings()
    provider = settings.model_provider.lower()

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=temperature,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=temperature,
        )

    else:
        raise ValueError(f"Unsupported MODEL_PROVIDER: {provider}")


# ---------------------------------------------------------------------------
# Embedding Factory (Section 4.4)
# ---------------------------------------------------------------------------

def get_embedding_model():
    """Create an embedding model based on the configured provider."""
    settings = get_settings()
    provider = settings.embedding_provider.lower()

    if provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embed_model,
            google_api_key=settings.gemini_api_key,
        )

    elif provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=settings.openai_embed_model,
            api_key=settings.openai_api_key,
        )

    elif provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
        )

    else:
        raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider}")


# ---------------------------------------------------------------------------
# Structured Output Binding (Section 5.3)
# ---------------------------------------------------------------------------

def bind_structured(llm: BaseChatModel, schema: Type[BaseModel]) -> BaseChatModel:
    """Bind a Pydantic schema for structured output."""
    return llm.with_structured_output(schema)


# ---------------------------------------------------------------------------
# Retry-wrapped LLM calls (Section 12.1)
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def call_llm_with_retry(llm: BaseChatModel, messages: list) -> Any:
    """Invoke an LLM with automatic retry on transient failures."""
    settings = get_settings()
    provider = settings.model_provider.lower()
    sem = _get_semaphore(provider)
    async with sem:
        return await asyncio.wait_for(
            llm.ainvoke(messages),
            timeout=settings.llm_timeout_seconds,
        )


# ---------------------------------------------------------------------------
# Structured invocation with schema validation fallback (Section 12.2)
# ---------------------------------------------------------------------------

async def invoke_structured(
    llm: BaseChatModel,
    schema: Type[BaseModel],
    messages: list,
) -> BaseModel:
    """Invoke LLM with structured output, retrying with repair on validation failure."""
    structured_llm = llm.with_structured_output(schema)
    try:
        return await call_llm_with_retry(structured_llm, messages)
    except (ValidationError, Exception) as exc:
        logger.warning("Structured output failed (%s), retrying with repair instruction", exc)
        repair_msg = {
            "role": "user",
            "content": (
                f"Your previous response did not match the required schema. "
                f"Please respond with valid JSON matching this schema exactly:\n"
                f"{schema.model_json_schema()}"
            ),
        }
        repaired_messages = list(messages) + [repair_msg]
        return await call_llm_with_retry(structured_llm, repaired_messages)
