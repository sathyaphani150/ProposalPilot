# backend/app/agents/error_handler.py
"""
ProposalPilot AI — Agent Error Handling & Retries
Centralized error recovery and observability for the multi-agent system.
"""

import asyncio
from functools import wraps
from typing import Any, Callable, TypeVar

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.exceptions import ValidationError, LLMServiceError
T = TypeVar("T")


def agent_retry(max_attempts: int = 3):
    """Decorator for agent nodes with smart retries."""
    def decorator(func: Callable):
        @wraps(func)
        @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (LLMServiceError, ConnectionError, TimeoutError)
        ),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying {func.__name__} after {retry_state.attempt_number} failures"
        ),
    )
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Agent error in {func.__name__}: {e}")
                if "rate limit" in str(e).lower() or "quota" in str(e).lower():
                    await asyncio.sleep(5)  # Backoff for Groq rate limits
                raise
        return wrapper
    return decorator


async def handle_agent_error(state: Any, error: Exception, agent_name: str) -> dict:
    """Graceful error handling with fallback message."""
    error_msg = f"[{agent_name.upper()} Agent] Failed: {str(error)[:200]}"

    logger.error(f"Agent {agent_name} failed: {error}")

    # Store error in state
    if hasattr(state, 'error'):
        state.error = error_msg

    # Add fallback output
    if hasattr(state, f"{agent_name}_output"):
        setattr(state, f"{agent_name}_output", error_msg)

    return {
        f"{agent_name}_output": error_msg,
        "error": error_msg,
        "messages": [{"role": "system", "content": error_msg}]
    }


# Observability Helper (LangSmith / Logging)
def log_agent_execution(agent_name: str, state: Any):
    """Log structured execution data for observability."""
    try:
        logger.info(f"AGENT_EXECUTION | {agent_name} | "
                   f"Iteration: {getattr(state, 'iteration', 'N/A')} | "
                   f"Context Tokens: ~{len(str(state.rfp_analysis))//4}")
    except:
        pass