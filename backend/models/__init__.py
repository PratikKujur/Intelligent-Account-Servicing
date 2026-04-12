# Models package - exports Pydantic schemas for data validation
# Centralizes imports for cleaner code elsewhere

from backend.models.schemas import (
    RequestStatus,
    DecisionType,
    ValidationStatus,
    SubmissionRequest,
    ExtractedData,
    ConfidenceScore,
    PendingRequest,
    CheckerDecision,
    ValidationResponse,
    RPSResponse,
    AuditLog,
)

__all__ = [
    # Status enums
    "RequestStatus",     # Request lifecycle status (DRAFT, AI_PROCESSING, etc.)
    "DecisionType",     # Checker decision (APPROVE, REJECT)
    "ValidationStatus", # Input validation status
    # Request/response schemas
    "SubmissionRequest",    # Incoming request schema
    "ExtractedData",        # Document extraction results
    "ConfidenceScore",      # Confidence scoring results
    "PendingRequest",       # Full pending request schema
    "CheckerDecision",      # Checker decision submission
    "ValidationResponse",   # Validation response
    "RPSResponse",         # RPS (banking system) response
    "AuditLog",            # Audit log entry schema
]
