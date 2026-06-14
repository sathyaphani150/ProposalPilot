"""
ProposalPilot AI — Structured Logging Configuration
Uses loguru with JSON output in production, human-readable in dev.
"""
import logging
import sys
from types import FrameType

from loguru import logger

from app.config import get_settings


class InterceptHandler(logging.Handler):
    """Redirect standard library logging to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno  # type: ignore[assignment]

        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging() -> None:
    settings = get_settings()

    # Remove default loguru handler
    logger.remove()

    if settings.is_production:
        # JSON logs for production (structured log aggregation)
        logger.add(
            sys.stdout,
            format="{message}",
            level="INFO",
            serialize=True,
        )
    else:
        # Human-readable for local development
        logger.add(
            sys.stdout,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
                "<level>{message}</level>"
            ),
            level="DEBUG",
            colorize=True,
        )

    # Intercept uvicorn and SQLAlchemy logs
    for lib_logger in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(lib_logger).handlers = [InterceptHandler()]
        logging.getLogger(lib_logger).propagate = False
