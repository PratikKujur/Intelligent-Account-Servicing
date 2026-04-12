# Pydantic for data validation and serialization
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


# Request lifecycle status enum - tracks the current state of each request
# Flow: DRAFT -> AI_PROCESSING -> AI_VERIFIED_PENDING_HUMAN -> (APPROVED|REJECTED) -> RPS_UPDATED
class RequestStatus(str, Enum):
    DRAFT = "DRAFT"                          # Initial state when request is created
    AI_PROCESSING = "AI_PROCESSING"          # AI pipeline is running
    AI_VERIFIED_PENDING_HUMAN = "AI_VERIFIED_PENDING_HUMAN"  # Awaiting human checker review
    APPROVED = "APPROVED"                    # Checker approved the request
    REJECTED = "REJECTED"                    # Checker rejected the request
    RPS_UPDATED = "RPS_UPDATED"              # Banking system has been updated
    FAILED = "FAILED"                        # Processing failed (validation/extraction error)


# Decision types available to human checkers
class DecisionType(str, Enum):
    APPROVE = "APPROVE"                      # Checker approves the name change
    REJECT = "REJECT"                        # Checker rejects the name change


# Validation status for input validation
class ValidationStatus(str, Enum):
    VALID = "VALID"                          # Input data is valid
    INVALID = "INVALID"                      # Input data has errors
    PENDING = "PENDING"                      # Validation not yet performed


# Schema for incoming name change request submission
class SubmissionRequest(BaseModel):
    customer_id: str = Field(..., min_length=1, description="Customer identifier")
    old_name: str = Field(..., min_length=1, description="Current legal name")
    new_name: str = Field(..., min_length=1, description="New legal name after change")
    document_base64: Optional[str] = None    # Base64 encoded document image
    document_path: Optional[str] = None      # Path to uploaded document file


# Schema for data extracted from identity documents via OCR/Vision
class ExtractedData(BaseModel):
    name: Optional[str] = None               # Name as it appears on the document
    date_of_birth: Optional[str] = None      # DOB extracted from document
    aadhar_number: Optional[str] = None       # Aadhaar card number
    raw_text: Optional[str] = None           # Raw text from OCR for debugging
    forgery_flag: bool = False               # Set to True if document appears suspicious


# Schema for confidence scoring results
class ConfidenceScore(BaseModel):
    name_match: int = Field(..., ge=0, le=100, description="Name match percentage")
    doc_auth: int = Field(..., ge=0, le=100, description="Document authenticity score")
    overall: int = Field(..., ge=0, le=100, description="Overall confidence score")


# Full pending request schema with all fields
class PendingRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # Unique ID
    customer_id: str                           # Customer identifier
    old_name: str                              # Current name
    new_name: str                              # Requested new name
    extracted_data: Optional[Dict[str, Any]] = None   # Data from document
    confidence_score: Optional[Dict[str, Any]] = None  # AI confidence scores
    ai_summary: Optional[str] = None           # AI-generated summary
    ai_recommendation: Optional[str] = None   # AI recommendation (APPROVE/REJECT)
    status: RequestStatus = RequestStatus.DRAFT
    checker_decision: Optional[DecisionType] = None   # Human checker decision
    checker_id: Optional[str] = None          # Who made the decision
    rejection_reason: Optional[str] = None    # Reason for rejection (if applicable)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Schema for checker decision submission
class CheckerDecision(BaseModel):
    request_id: str                           # Which request is being decided
    decision: DecisionType                    # APPROVE or REJECT
    checker_id: str = Field(..., min_length=1)  # Checker identifier (enforces HITL)
    rejection_reason: Optional[str] = None    # Required if REJECT


# Schema for validation response
class ValidationResponse(BaseModel):
    status: ValidationStatus                   # VALID or INVALID
    message: Optional[str] = None            # Error details if INVALID


# Schema for RPS (banking system) update response
class RPSResponse(BaseModel):
    success: bool                             # Whether update succeeded
    message: str                              # Status message
    rps_reference: Optional[str] = None      # Reference number from banking system


# Schema for audit log entries
class AuditLog(BaseModel):
    log_id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # Unique log ID
    request_id: str                           # Associated request
    event_type: str                          # Type of event (e.g., "VALIDATION_COMPLETED")
    event_data: Dict[str, Any]               # Event details as JSON
    timestamp: datetime = Field(default_factory=datetime.utcnow)
