# Python logging framework for structured logging
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
import json

# Log directory: data/logs/ (separate from database for easy access)
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging with timestamp, logger name, level, and message
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("iasw.audit")


# AuditService provides centralized audit logging for compliance
# Logs are written to both:
# 1. Python logger (for server logs/monitoring)
# 2. JSON file per request (for detailed audit trail)
class AuditService:
    @staticmethod
    def log(request_id: str, event_type: str, event_data: dict):
        log_entry = {
            "request_id": request_id,
            "event_type": event_type,
            "event_data": event_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Log to Python logger (appears in server console/logs)
        logger.info(f"[{event_type}] Request {request_id}: {event_data}")
        
        # Write to per-request JSON file (for compliance audit trail)
        log_file = os.path.join(LOG_DIR, f"{request_id}.json")
        try:
            # Append to existing log or create new file
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            logs.append(log_entry)
            
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    # Convenience method for logging OCR results
    @staticmethod
    def log_ocr(request_id: str, raw_text: str, success: bool):
        AuditService.log(request_id, "OCR_COMPLETED", {
            "success": success,
            "text_length": len(raw_text) if raw_text else 0,
            "text_preview": raw_text[:200] + "..." if raw_text and len(raw_text) > 200 else raw_text
        })
    
    # Convenience method for logging document extraction results
    @staticmethod
    def log_extraction(request_id: str, extracted_fields: dict, forgery_flag: bool):
        AuditService.log(request_id, "EXTRACTION_COMPLETED", {
            "extracted_fields": extracted_fields,
            "forgery_flag": forgery_flag
        })
    
    # Convenience method for logging confidence scoring results
    @staticmethod
    def log_scoring(request_id: str, scores: dict, recommendation: str):
        AuditService.log(request_id, "SCORING_COMPLETED", {
            "ai_score": scores.get("overall"),
            "name_match": scores.get("name_match"),
            "doc_auth": scores.get("doc_auth"),
            "recommendation": recommendation
        })
    
    # Convenience method for logging human checker decisions
    @staticmethod
    def log_checker_decision(request_id: str, decision: str, checker_id: str, rejection_reason: Optional[str] = None):
        AuditService.log(request_id, "CHECKER_DECISION", {
            "checker_decision": decision,
            "checker_id": checker_id,
            "rejection_reason": rejection_reason
        })
    
    # Convenience method for logging RPS (banking system) updates
    @staticmethod
    def log_rps_update(request_id: str, success: bool, rps_reference: Optional[str] = None):
        AuditService.log(request_id, "RPS_UPDATE", {
            "success": success,
            "rps_reference": rps_reference
        })
