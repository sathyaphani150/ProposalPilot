# backend/app/api/v1/ws.py
"""
ProposalPilot AI — WebSocket Streaming for Agentic War Room
Real-time updates as agents think and generate outputs.
"""

import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.agents.graph import astream_war_room_graph
from app.agents.state import create_initial_war_room_state
from app.database import AsyncSessionLocal
from app.services.war_room_service import get_rfp_analysis, get_rfp_session_or_404

router = APIRouter(prefix="/ws", tags=["WebSocket"])


def _analysis_to_dict(analysis: Any) -> dict[str, Any]:
    """Normalize ORM analysis objects into a plain dict for graph state."""
    if hasattr(analysis, "to_dict"):
        return analysis.to_dict()

    if isinstance(analysis, dict):
        return dict(analysis)

    raise TypeError(f"Unsupported analysis payload type: {type(analysis)!r}")


@router.websocket("/war-room/{session_id}")
async def war_room_stream(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time War Room agent streaming.
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for War Room session {session_id}")

    try:
        async with AsyncSessionLocal() as db:
            session = await get_rfp_session_or_404(db, uuid.UUID(session_id))
            analysis = await get_rfp_analysis(db, uuid.UUID(session_id))

            if not analysis:
                await websocket.send_json({"type": "error", "content": "RFP analysis not found"})
                return

            # Create initial state
            initial_state = create_initial_war_room_state(
                rfp_session_id=session_id,
                rfp_analysis=_analysis_to_dict(analysis),
            )

            # Stream events from LangGraph
            async for event in astream_war_room_graph(initial_state):
                if "event" in event and event["event"] == "on_chain_end":
                    # Simplified: send agent outputs
                    await websocket.send_json({
                        "type": "agent_update",
                        "agent": event.get("name", "unknown"),
                        "content": event.get("data", ""),
                        "timestamp": "now"
                    })
                elif "data" in event:
                    await websocket.send_json({
                        "type": "token",
                        "content": str(event["data"]),
                        "agent": event.get("metadata", {}).get("agent", "supervisor")
                    })

            # Final message
            await websocket.send_json({
                "type": "complete",
                "content": "War Room execution finished successfully."
            })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except:
            pass
    finally:
        await websocket.close()
