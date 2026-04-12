# Services package - exports business logic and data access layers
# Centralizes imports for cleaner code elsewhere

from backend.services.database import RequestRepository, AuditRepository
from backend.services.audit import AuditService
from backend.services.rps_mock import get_rps_service
from backend.services.ai_pipeline import get_ai_pipeline

__all__ = [
    # Database repositories
    "RequestRepository",  # CRUD operations for pending_requests table
    "AuditRepository",    # CRUD operations for audit_logs table
    # Audit service
    "AuditService",       # Centralized audit logging
    # RPS mock service (HITL boundary)
    "get_rps_service",   # Factory for RPS mock singleton
    # AI pipeline orchestrator
    "get_ai_pipeline",   # Factory for AI pipeline
]
