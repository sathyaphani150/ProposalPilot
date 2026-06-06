"""
ProposalPilot AI — War Room Celery Tasks (Placeholder)
"""
from app.tasks.celery_app import celery_app

@celery_app.task(name="app.tasks.war_room_tasks.run_war_room_task")
def run_war_room_task(session_id: str):
    pass
