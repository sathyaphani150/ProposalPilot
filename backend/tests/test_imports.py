def test_war_room_modules_import() -> None:
    import app.schemas.war_room  # noqa: F401
    import app.war_room.discussion  # noqa: F401
    import app.war_room.graph  # noqa: F401
    import app.war_room.supervisor  # noqa: F401
