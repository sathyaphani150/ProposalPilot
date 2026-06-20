"""
ProposalPilot AI — Celery Application
Configured async task queue for background processing.
"""
from celery import Celery  # type: ignore[import-untyped]
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "proposalpilot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.ingestion_tasks",
        "app.tasks.war_room_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # Acknowledge only after task completes
    worker_prefetch_multiplier=1,  # One task at a time per worker
    task_routes={
        "app.tasks.ingestion_tasks.*": {"queue": "ingestion"},
        "app.tasks.war_room_tasks.*": {"queue": "war_room"},
    },
)
