from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class RequestStatus(str, Enum):
    DRAFT = "DRAFT"
    AI_PROCESSING = "AI_PROCESSING"
    AI_VERIFIED_PENDING_HUMAN = "AI_VERIFIED_PENDING_HUMAN"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RPS_UPDATED = "RPS_UPDATED"
    FAILED = "FAILED"


class DecisionType(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class ValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    PENDING = "PENDING"


class SubmissionRequest(BaseModel):
    customer_id: str = Field(..., min_length=1, description="Customer identifier")
    old_name: str = Field(..., min_length=1, description="Current legal name")
    new_name: str = Field(..., min_length=1, description="New legal name after change")
    document_base64: Optional[str] = None
    document_path: Optional[str] = None


class ExtractedData(BaseModel):
    name: Optional[str] = None
    date_of_birth: Optional[str] = None
    aadhar_number: Optional[str] = None
    raw_text: Optional[str] = None
    forgery_flag: bool = False


class ConfidenceScore(BaseModel):
    name_match: int = Field(..., ge=0, le=100, description="Name match percentage")
    doc_auth: int = Field(..., ge=0, le=100, description="Document authenticity score")
    overall: int = Field(..., ge=0, le=100, description="Overall confidence score")


class PendingRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    old_name: str
    new_name: str
    extracted_data: Optional[Dict[str, Any]] = None
    confidence_score: Optional[Dict[str, Any]] = None
    ai_summary: Optional[str] = None
    ai_recommendation: Optional[str] = None
    status: RequestStatus = RequestStatus.DRAFT
    checker_decision: Optional[DecisionType] = None
    checker_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CheckerDecision(BaseModel):
    request_id: str
    decision: DecisionType
    checker_id: str = Field(..., min_length=1)
    rejection_reason: Optional[str] = None


class ValidationResponse(BaseModel):
    status: ValidationStatus
    message: Optional[str] = None


class RPSResponse(BaseModel):
    success: bool
    message: str
    rps_reference: Optional[str] = None


class AuditLog(BaseModel):
    log_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    event_type: str
    event_data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
