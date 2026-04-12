"""
AI Pipeline Service - Orchestrates the complete AI processing workflow.
This is the main orchestration layer that coordinates all AI agents.
"""
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from backend.models.schemas import RequestStatus
# Import all AI agents
from backend.agents import (
    get_validation_agent,
    get_document_processor,
    get_confidence_scorer,
    get_summary_agent,
)
from backend.services.database import RequestRepository, AuditRepository
from backend.services.audit import AuditService


# AIPipeline orchestrates the complete AI processing workflow
# Coordinates sequential execution of 4 specialized agents:
# 1. Validation Agent - validates input data
# 2. Document Processor - extracts data from documents
# 3. Confidence Scorer - calculates verification scores
# 4. Summary Agent - generates human-readable summary
class AIPipeline:
    """
    Orchestrates the complete AI processing pipeline for identity verification.
    
    Workflow:
    1. Validate input request
    2. Process document (OCR + extraction)
    3. Calculate confidence scores
    4. Generate summary
    5. Stage for human review
    """
    
    def __init__(self):
        # Initialize all agent instances (singleton pattern)
        self.validation_agent = get_validation_agent()
        self.document_processor = get_document_processor()
        self.confidence_scorer = get_confidence_scorer()
        self.summary_agent = get_summary_agent()
    
    # Main entry point - processes a complete name change request
    # Returns dict with all results for storage and display
    def process_request(
        self,
        customer_id: Optional[str] = None,
        old_name: str = None,
        new_name: str = None,
        date_of_birth: Optional[str] = None,
        aadhar_number: Optional[str] = None,
        document_base64: Optional[str] = None,
        document_path: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an identity verification request through the AI pipeline.
        
        Args:
            customer_id: Customer identifier (auto-generated if not provided)
            old_name: Current legal name
            new_name: New legal name after change
            date_of_birth: Date of birth (optional)
            aadhar_number: Aadhaar number (optional)
            document_base64: Base64 encoded document
            document_path: Path to uploaded document
            request_id: Optional existing request ID
            
        Returns:
            Dictionary with processing results and status
        """
        # Generate IDs if not provided
        request_id = request_id or str(uuid.uuid4())
        customer_id = customer_id or f"REQ-{request_id[:8].upper()}"
        
        # STEP 1: Log request received
        AuditService.log(request_id, "REQUEST_RECEIVED", {
            "customer_id": customer_id,
            "old_name": old_name,
            "new_name": new_name,
            "date_of_birth": date_of_birth,
            "has_document": bool(document_base64 or document_path)
        })
        
        # STEP 2: Validate input data (LLM or rule-based)
        validation_status, validation_message = self.validation_agent.validate(
            old_name=old_name,
            new_name=new_name,
            customer_id=customer_id
        )
        
        AuditService.log(request_id, "VALIDATION_COMPLETED", {
            "status": validation_status,
            "message": validation_message
        })
        
        # Validation failed - return immediately with error
        if validation_status != "VALID":
            return {
                "request_id": request_id,
                "status": RequestStatus.FAILED.value,
                "error": validation_message,
                "validation_status": validation_status
            }
        
        # Create request record in database with AI_PROCESSING status
        RequestRepository.create_request(
            request_id=request_id,
            customer_id=customer_id,
            old_name=old_name,
            new_name=new_name,
            status=RequestStatus.AI_PROCESSING.value
        )
        
        # STEP 3: Process document (OCR/Vision + extraction)
        success, extraction_result = self.document_processor.process_document(
            document_data=document_base64,
            document_path=document_path
        )
        
        # Log OCR results
        AuditService.log_ocr(request_id, extraction_result.raw_text, success)
        
        # Build extracted data dict
        extracted_data = {
            "name": extraction_result.name,
            "date_of_birth": extraction_result.date_of_birth,
            "aadhar_number": extraction_result.aadhar_number,
            "raw_text": extraction_result.raw_text[:500] if extraction_result.raw_text else None,
            "forgery_flag": extraction_result.forgery_flag,
            "document_authentic": extraction_result.document_authentic
        }
        
        AuditService.log_extraction(request_id, extracted_data, extraction_result.forgery_flag)
        
        # STEP 4: Calculate confidence scores
        confidence_scores = self.confidence_scorer.score(
            extracted_data, old_name, new_name, date_of_birth
        )
        
        # Generate recommendation based on overall score
        recommendation = self.confidence_scorer.get_recommendation(
            confidence_scores["overall"]
        )
        
        AuditService.log_scoring(request_id, confidence_scores, recommendation)
        
        # STEP 5: Generate AI summary (compliance report)
        ai_summary = self.summary_agent.generate_summary(
            extracted_data,
            confidence_scores,
            old_name,
            new_name,
            date_of_birth,
            recommendation
        )
        
        # Determine final status - if forgery detected, mark as FAILED
        final_status = RequestStatus.AI_VERIFIED_PENDING_HUMAN.value
        if extraction_result.forgery_flag:
            final_status = RequestStatus.FAILED.value
        
        # Update database with all results
        RequestRepository.update_request(
            request_id=request_id,
            extracted_data=extracted_data,
            confidence_score=confidence_scores,
            ai_summary=ai_summary,
            ai_recommendation=recommendation,
            status=final_status
        )
        
        AuditService.log(request_id, "PIPELINE_COMPLETED", {
            "status": final_status,
            "recommendation": recommendation,
            "confidence": confidence_scores["overall"]
        })
        
        # Return complete results for API response
        return {
            "request_id": request_id,
            "status": final_status,
            "extracted_data": extracted_data,
            "confidence_score": confidence_scores,
            "ai_summary": ai_summary,
            "ai_recommendation": recommendation,
            "validation_status": validation_status
        }


# Factory function to get AIPipeline instance
def get_ai_pipeline() -> AIPipeline:
    return AIPipeline()
