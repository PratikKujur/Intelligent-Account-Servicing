"""
AI Pipeline Service - Orchestrates the complete AI processing workflow.
"""
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from backend.models.schemas import RequestStatus
from backend.agents import (
    get_validation_agent,
    get_document_processor,
    get_confidence_scorer,
    get_summary_agent,
)
from backend.services.database import RequestRepository, AuditRepository
from backend.services.audit import AuditService


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
        self.validation_agent = get_validation_agent()
        self.document_processor = get_document_processor()
        self.confidence_scorer = get_confidence_scorer()
        self.summary_agent = get_summary_agent()
    
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
        request_id = request_id or str(uuid.uuid4())
        customer_id = customer_id or f"REQ-{request_id[:8].upper()}"
        
        AuditService.log(request_id, "REQUEST_RECEIVED", {
            "customer_id": customer_id,
            "old_name": old_name,
            "new_name": new_name,
            "date_of_birth": date_of_birth,
            "has_document": bool(document_base64 or document_path)
        })
        
        validation_status, validation_message = self.validation_agent.validate(
            old_name=old_name,
            new_name=new_name,
            customer_id=customer_id
        )
        
        AuditService.log(request_id, "VALIDATION_COMPLETED", {
            "status": validation_status,
            "message": validation_message
        })
        
        if validation_status != "VALID":
            return {
                "request_id": request_id,
                "status": RequestStatus.FAILED.value,
                "error": validation_message,
                "validation_status": validation_status
            }
        
        RequestRepository.create_request(
            request_id=request_id,
            customer_id=customer_id,
            old_name=old_name,
            new_name=new_name,
            status=RequestStatus.AI_PROCESSING.value
        )
        
        success, extraction_result = self.document_processor.process_document(
            document_data=document_base64,
            document_path=document_path
        )
        
        AuditService.log_ocr(request_id, extraction_result.raw_text, success)
        
        extracted_data = {
            "name": extraction_result.name,
            "date_of_birth": extraction_result.date_of_birth,
            "aadhar_number": extraction_result.aadhar_number,
            "raw_text": extraction_result.raw_text[:500] if extraction_result.raw_text else None,
            "forgery_flag": extraction_result.forgery_flag,
            "document_authentic": extraction_result.document_authentic
        }
        
        AuditService.log_extraction(request_id, extracted_data, extraction_result.forgery_flag)
        
        confidence_scores = self.confidence_scorer.score(
            extracted_data, old_name, new_name, date_of_birth
        )
        
        recommendation = self.confidence_scorer.get_recommendation(
            confidence_scores["overall"]
        )
        
        AuditService.log_scoring(request_id, confidence_scores, recommendation)
        
        ai_summary = self.summary_agent.generate_summary(
            extracted_data,
            confidence_scores,
            old_name,
            new_name,
            date_of_birth,
            recommendation
        )
        
        final_status = RequestStatus.AI_VERIFIED_PENDING_HUMAN.value
        
        if extraction_result.forgery_flag:
            final_status = RequestStatus.FAILED.value
        
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
        
        return {
            "request_id": request_id,
            "status": final_status,
            "extracted_data": extracted_data,
            "confidence_score": confidence_scores,
            "ai_summary": ai_summary,
            "ai_recommendation": recommendation,
            "validation_status": validation_status
        }


def get_ai_pipeline() -> AIPipeline:
    return AIPipeline()
