def test_application_modules_import() -> None:
    import app.main  # noqa: F401
    import app.api.v1.knowledge  # noqa: F401
    import app.api.v1.proposals  # noqa: F401
    import app.api.v1.rfp  # noqa: F401
    import app.services.proposal_service  # noqa: F401
