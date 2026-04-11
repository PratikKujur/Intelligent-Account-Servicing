"""
API routes for IASW workflow.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import json
import uuid

from backend.models.schemas import (
    CheckerDecision,
    RequestStatus,
)
from backend.services.database import RequestRepository, AuditRepository
from backend.services.audit import AuditService
from backend.services.rps_mock import get_rps_service
from backend.services.ai_pipeline import get_ai_pipeline


router = APIRouter(prefix="/api/v1", tags=["IASW Workflow"])


@router.post("/requests/submit")
async def submit_request(
    customer_id: Optional[str] = Form(None),
    old_name: str = Form(...),
    new_name: str = Form(...),
    date_of_birth: Optional[str] = Form(None),
    aadhar_number: Optional[str] = Form(None),
    document: Optional[UploadFile] = File(None)
):
    """
    Submit a new identity verification request.
    
    This endpoint:
    1. Validates the input
    2. Processes the document via AI pipeline
    3. Stages for human review
    """
    document_base64 = None
    
    if document:
        content = await document.read()
        import base64
        document_base64 = base64.b64encode(content).decode()
    
    pipeline = get_ai_pipeline()
    generated_customer_id = customer_id or f"CUST-{uuid.uuid4().hex[:8].upper()}"
    result = pipeline.process_request(
        customer_id=generated_customer_id,
        old_name=old_name,
        new_name=new_name,
        date_of_birth=date_of_birth,
        aadhar_number=aadhar_number,
        document_base64=document_base64
    )
    
    if result.get("status") == RequestStatus.FAILED.value:
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return {
        "success": True,
        "request_id": result["request_id"],
        "customer_id": generated_customer_id,
        "message": "Request submitted and pending human review",
        "status": result["status"],
        "ai_recommendation": result.get("ai_recommendation")
    }


@router.get("/requests/{request_id}")
async def get_request(request_id: str):
    """Get request details by ID"""
    request_data = RequestRepository.get_request(request_id)
    
    if not request_data:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if request_data.get("extracted_data"):
        request_data["extracted_data"] = json.loads(request_data["extracted_data"])
    if request_data.get("confidence_score"):
        request_data["confidence_score"] = json.loads(request_data["confidence_score"])
    
    return {
        "request_id": request_data["request_id"],
        "customer_id": request_data["customer_id"],
        "name": request_data["old_name"],
        "extracted_data": request_data.get("extracted_data"),
        "confidence_score": request_data.get("confidence_score"),
        "ai_summary": request_data.get("ai_summary"),
        "ai_recommendation": request_data.get("ai_recommendation"),
        "status": request_data["status"],
        "rps_reference": request_data.get("rps_reference"),
        "created_at": request_data["created_at"],
        "updated_at": request_data["updated_at"]
    }


@router.get("/requests")
async def list_requests(status: Optional[str] = None):
    """List all requests, optionally filtered by status"""
    requests = RequestRepository.get_pending_requests(status)
    
    formatted_requests = []
    for req in requests:
        formatted = {
            "request_id": req["request_id"],
            "customer_id": req["customer_id"],
            "name": req["old_name"],
            "extracted_data": json.loads(req["extracted_data"]) if req.get("extracted_data") else None,
            "confidence_score": json.loads(req["confidence_score"]) if req.get("confidence_score") else None,
            "ai_summary": req.get("ai_summary"),
            "ai_recommendation": req.get("ai_recommendation"),
            "status": req["status"],
            "checker_decision": req.get("checker_decision"),
            "rps_reference": req.get("rps_reference"),
            "created_at": req["created_at"],
            "updated_at": req["updated_at"]
        }
        formatted_requests.append(formatted)
    
    return {
        "requests": formatted_requests,
        "total": len(formatted_requests)
    }


@router.get("/requests/pending/review")
async def get_pending_requests():
    """Get all requests pending human review"""
    return await list_requests(status=RequestStatus.AI_VERIFIED_PENDING_HUMAN.value)


@router.post("/checker/decide")
async def checker_decision(decision: CheckerDecision):
    """
    Submit checker decision (HITL boundary).
    """
    request_data = RequestRepository.get_request(decision.request_id)
    
    if not request_data:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if request_data["status"] not in [
        RequestStatus.AI_VERIFIED_PENDING_HUMAN.value,
        RequestStatus.APPROVED.value,
        RequestStatus.REJECTED.value
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"Request cannot be decided in status: {request_data['status']}"
        )
    
    AuditService.log_checker_decision(
        decision.request_id,
        decision.decision.value,
        decision.checker_id,
        decision.rejection_reason
    )
    
    if decision.decision.value == "APPROVE":
        rps_service = get_rps_service()
        
        try:
            rps_result = rps_service.update_customer_name(
                request_id=decision.request_id,
                customer_id=request_data["customer_id"],
                old_name=request_data["old_name"],
                new_name=request_data["new_name"],
                checker_id=decision.checker_id
            )
            
            AuditService.log_rps_update(
                decision.request_id,
                success=True,
                rps_reference=rps_result.get("rps_reference")
            )
            
            RequestRepository.add_rps_update(
                request_id=decision.request_id,
                rps_reference=rps_result.get("rps_reference") or "",
                updated_fields=rps_result.get("update_details", {}),
                status="COMPLETED"
            )
            
            RequestRepository.update_request(
                request_id=decision.request_id,
                status=RequestStatus.RPS_UPDATED.value,
                checker_decision=decision.decision.value,
                checker_id=decision.checker_id
            )
            
            return {
                "success": True,
                "request_id": decision.request_id,
                "customer_id": request_data["customer_id"],
                "status": RequestStatus.RPS_UPDATED.value,
                "message": "Request approved and RPS updated",
                "rps_reference": rps_result.get("rps_reference")
            }
            
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            AuditService.log_rps_update(decision.request_id, success=False)
            raise HTTPException(status_code=500, detail=f"RPS update failed: {str(e)}")
    
    else:
        RequestRepository.update_request(
            request_id=decision.request_id,
            status=RequestStatus.REJECTED.value,
            checker_decision=decision.decision.value,
            checker_id=decision.checker_id,
            rejection_reason=decision.rejection_reason
        )
        
        return {
            "success": True,
            "request_id": decision.request_id,
            "status": RequestStatus.REJECTED.value,
            "message": "Request rejected",
            "rejection_reason": decision.rejection_reason
        }


@router.get("/audit/{request_id}")
async def get_audit_logs(request_id: str):
    """Get audit trail for a request"""
    logs = AuditRepository.get_logs(request_id)
    
    formatted_logs = []
    for log in logs:
        formatted_logs.append({
            "log_id": log["log_id"],
            "request_id": log["request_id"],
            "event_type": log["event_type"],
            "event_data": json.loads(log["event_data"]) if log.get("event_data") else {},
            "timestamp": log["timestamp"]
        })
    
    return {
        "request_id": request_id,
        "logs": formatted_logs
    }


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "IASW Backend",
        "version": "1.0.0"
    }


@router.get("/rps/updates")
async def get_rps_updates(request_id: Optional[str] = None):
    """Get RPS update audit trail"""
    updates = RequestRepository.get_rps_updates(request_id)
    
    return {
        "request_id": request_id,
        "total": len(updates),
        "updates": updates
    }


@router.get("/rps/customer/{customer_id}")
async def get_customer_rps_history(customer_id: str):
    """Get RPS history for a specific customer"""
    updates = RequestRepository.get_customer_rps_history(customer_id)
    
    return {
        "customer_id": customer_id,
        "total_updates": len(updates),
        "updates": updates
    }
