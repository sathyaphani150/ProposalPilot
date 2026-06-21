def test_war_room_modules_import() -> None:
    import app.schemas.war_room  # noqa: F401
    import app.war_room.discussion  # noqa: F401
    import app.war_room.graph  # noqa: F401
    import app.war_room.supervisor  # noqa: F401


def test_local_dev_cors_allows_vite_fallback_ports() -> None:
    import re

    from app.main import _local_dev_cors_origin_regex

    pattern = _local_dev_cors_origin_regex()

    assert pattern is not None
    assert re.match(pattern, "http://localhost:5174")
    assert re.match(pattern, "http://127.0.0.1:8124")
    assert re.match(pattern, "https://proposal-pilot-cognine.netlify.app")
    assert re.match(pattern, "https://deploy-preview-12--proposal-pilot-cognine.netlify.app")


def test_war_room_start_routes_are_registered() -> None:
    from fastapi.routing import APIRoute

    from app.main import app

    routes = {
        (route.path, tuple(sorted(getattr(route, "methods", []))))
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    assert ("/api/v1/war-room/run", ("POST",)) in routes
    assert ("/api/v1/war-room/{session_id}/start", ("POST",)) in routes
