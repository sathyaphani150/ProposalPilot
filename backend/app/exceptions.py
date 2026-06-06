"""
ProposalPilot AI — Custom Exception Hierarchy
All business exceptions inherit from ProposalPilotError.
FastAPI exception handlers are registered in main.py.
"""
from typing import Any


class ProposalPilotError(Exception):
    """Base exception for all application errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        detail: Any = None,
        *,
        error_code: str | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.detail = detail
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)


# ── 400 Bad Request ────────────────────────────────────────────────────────
class ValidationError(ProposalPilotError):
    status_code = 400
    error_code = "VALIDATION_ERROR"
    message = "Request validation failed."


class InvalidFileTypeError(ProposalPilotError):
    status_code = 400
    error_code = "INVALID_FILE_TYPE"
    message = "Uploaded file type is not supported."


class FileTooLargeError(ProposalPilotError):
    status_code = 400
    error_code = "FILE_TOO_LARGE"
    message = "Uploaded file exceeds maximum allowed size."


# ── 401 Unauthorized ──────────────────────────────────────────────────────
class AuthenticationError(ProposalPilotError):
    status_code = 401
    error_code = "AUTHENTICATION_FAILED"
    message = "Authentication credentials are missing or invalid."


# ── 403 Forbidden ─────────────────────────────────────────────────────────
class PermissionDeniedError(ProposalPilotError):
    status_code = 403
    error_code = "PERMISSION_DENIED"
    message = "You do not have permission to perform this action."


# ── 404 Not Found ─────────────────────────────────────────────────────────
class NotFoundError(ProposalPilotError):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "The requested resource was not found."


class RFPSessionNotFoundError(NotFoundError):
    error_code = "RFP_SESSION_NOT_FOUND"
    message = "RFP session not found."


class KnowledgeItemNotFoundError(NotFoundError):
    error_code = "KNOWLEDGE_ITEM_NOT_FOUND"
    message = "Knowledge base item not found."


class ProposalNotFoundError(NotFoundError):
    error_code = "PROPOSAL_NOT_FOUND"
    message = "Proposal not found."


# ── 409 Conflict ──────────────────────────────────────────────────────────
class ConflictError(ProposalPilotError):
    status_code = 409
    error_code = "CONFLICT"
    message = "Resource already exists or operation conflicts with current state."


# ── 422 Unprocessable ─────────────────────────────────────────────────────
class DocumentParsingError(ProposalPilotError):
    status_code = 422
    error_code = "DOCUMENT_PARSING_FAILED"
    message = "Failed to extract text from uploaded document."


class LLMExtractionError(ProposalPilotError):
    status_code = 422
    error_code = "LLM_EXTRACTION_FAILED"
    message = "AI analysis of the document failed. Please try again."


# ── 429 Rate Limit ────────────────────────────────────────────────────────
class RateLimitError(ProposalPilotError):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests. Please wait before retrying."


# ── 503 Service Unavailable ───────────────────────────────────────────────
class LLMServiceError(ProposalPilotError):
    status_code = 503
    error_code = "LLM_SERVICE_UNAVAILABLE"
    message = "The AI service is temporarily unavailable. Please try again."


class VectorDBError(ProposalPilotError):
    status_code = 503
    error_code = "VECTOR_DB_ERROR"
    message = "Vector database operation failed."


class WarRoomError(ProposalPilotError):
    status_code = 503
    error_code = "WAR_ROOM_ERROR"
    message = "Agent war room encountered an error."
