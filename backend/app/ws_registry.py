from __future__ import annotations

from fastapi import WebSocket

_subscribers: dict[str, list[WebSocket]] = {}


async def subscribe(session_id: str, ws: WebSocket) -> None:
    _subscribers.setdefault(session_id, []).append(ws)


def unsubscribe(session_id: str, ws: WebSocket) -> None:
    if session_id in _subscribers and ws in _subscribers[session_id]:
        _subscribers[session_id].remove(ws)
        if not _subscribers[session_id]:
            _subscribers.pop(session_id, None)


async def broadcast(session_id: str, message: dict) -> None:
    for ws in list(_subscribers.get(session_id, [])):
        try:
            await ws.send_json(message)
        except Exception:
            unsubscribe(session_id, ws)
