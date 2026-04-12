# UUID for generating unique references
import uuid
from datetime import datetime
from typing import Optional, Dict, Any


# Singleton RPS Mock Service - simulates core banking system
# This is the Human-in-the-Loop (HITL) enforcement boundary
class RPSMockService:
    """
    RPS (Real-Time Platform System) Mock - Simulates core banking system updates.
    
    CRITICAL: This service represents the HITL boundary.
    AI agents CANNOT call this service directly.
    Only approved Checker decisions can trigger RPS updates.
    """
    
    _instance = None
    
    # Singleton pattern - ensures only one instance exists
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._audit_trail = []  # In-memory audit trail for RPS operations
    
    # CRITICAL: Enforces HITL boundary
    # Raises PermissionError if checker_id is None or empty
    # This prevents AI agents from autonomously updating banking systems
    def _enforce_authorization(self, checker_id: Optional[str]) -> bool:
        """Enforce HITL - ensure only authorized users can call RPS"""
        if not checker_id:
            raise PermissionError("AI not authorized to call RPS. Human checker required.")
        return True
    
    # Update customer name in the core banking system
    # Requires valid checker_id (enforced via _enforce_authorization)
    def update_customer_name(
        self,
        request_id: str,
        customer_id: str,
        old_name: str,
        new_name: str,
        checker_id: str,
        document_reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update customer name in the core banking system (RPS Mock).
        
        This method enforces the HITL boundary - only authorized checkers can call this.
        """
        # This will raise PermissionError if checker_id is None
        self._enforce_authorization(checker_id)
        
        # Generate unique reference for this banking system update
        rps_reference = f"RPS-{uuid.uuid4().hex[:12].upper()}"
        
        # Create detailed update record
        update_record = {
            "rps_reference": rps_reference,
            "request_id": request_id,
            "customer_id": customer_id,
            "changes": {
                "name_change": {
                    "field": "legal_name",
                    "old_value": old_name,
                    "new_value": new_name,
                    "effective_date": datetime.utcnow().isoformat()
                }
            },
            "document_reference": document_reference,
            "authorized_by": checker_id,  # Track who authorized this
            "created_at": datetime.utcnow().isoformat(),
            "status": "COMPLETED"
        }
        
        # Add to audit trail
        self._audit_trail.append(update_record)
        
        return {
            "success": True,
            "message": "Customer name updated successfully in RPS",
            "rps_reference": rps_reference,
            "update_details": update_record
        }
    
    # Mock customer lookup (for demonstration purposes)
    def get_customer_details(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer details from RPS (mock)"""
        return {
            "customer_id": customer_id,
            "status": "ACTIVE",
            "name": "Mock Customer",
            "account_count": 2
        }
    
    # Get RPS audit trail, optionally filtered by request_id
    def get_audit_trail(self, request_id: Optional[str] = None) -> list:
        """Get audit trail from RPS"""
        if request_id:
            return [t for t in self._audit_trail if t.get("request_id") == request_id]
        return self._audit_trail


# Factory function to get singleton instance
def get_rps_service() -> RPSMockService:
    return RPSMockService()
