# SQLite for local database storage
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import os

# Database file path: data/banking_system.db
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "banking_system.db")


# Create database connection with Row factory for dict-like access
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn


# Context manager for database connections - ensures proper commit/rollback
@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()  # Commit transaction on success
    except Exception:
        conn.rollback()  # Rollback on any error
        raise
    finally:
        conn.close()  # Always close connection


# Helper to get current timestamp in ISO format
def utcnow():
    return datetime.utcnow().isoformat()


# Initialize database schema - creates tables if they don't exist
# Called on application startup via lifespan handler
def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Main table for storing name change requests
        # Stores customer info, extracted data, scores, and status
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_requests (
                request_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                old_name TEXT NOT NULL,
                new_name TEXT NOT NULL,
                extracted_data TEXT,              -- JSON: Data extracted from document
                confidence_score TEXT,             -- JSON: AI confidence scores
                ai_summary TEXT,                   -- AI-generated compliance summary
                ai_recommendation TEXT,            -- APPROVE/REJECT from AI
                status TEXT NOT NULL,             -- Current request status
                checker_decision TEXT,             -- Human checker decision
                checker_id TEXT,                   -- Who reviewed the request
                rejection_reason TEXT,             -- Reason if rejected
                rps_reference TEXT,               -- Banking system reference
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Audit log table - tracks all events for compliance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                event_type TEXT NOT NULL,         -- Event type (e.g., "VALIDATION_COMPLETED")
                event_data TEXT NOT NULL,          -- JSON: Event details
                timestamp TEXT NOT NULL,
                FOREIGN KEY (request_id) REFERENCES pending_requests(request_id)
            )
        """)
        
        # RPS updates table - records all banking system updates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rps_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                rps_reference TEXT,               -- Reference from banking system
                updated_fields TEXT,               -- JSON: What was updated
                status TEXT,                       -- Update status
                created_at TEXT NOT NULL,
                FOREIGN KEY (request_id) REFERENCES pending_requests(request_id)
            )
        """)
        
        # Index on status for efficient filtering (e.g., get pending reviews)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_status 
            ON pending_requests(status)
        """)
        
        # Index on creation time for sorting
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_created 
            ON pending_requests(created_at)
        """)
        
        # Index on request_id for efficient audit log lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_request 
            ON audit_logs(request_id)
        """)


# Repository class for pending_requests table operations
# Provides CRUD operations for name change requests
class RequestRepository:
    @staticmethod
    def create_request(
        request_id: str,
        customer_id: str,
        old_name: str,
        new_name: str,
        status: str = "DRAFT"
    ) -> Dict[str, Any]:
        now = utcnow()
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pending_requests 
                (request_id, customer_id, old_name, new_name, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (request_id, customer_id, old_name, new_name, status, now, now))
            
            return {
                "request_id": request_id,
                "customer_id": customer_id,
                "old_name": old_name,
                "new_name": new_name,
                "status": status,
                "created_at": now,
                "updated_at": now
            }
    
    @staticmethod
    def get_request(request_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pending_requests WHERE request_id = ?
            """, (request_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
        return None
    
    # Get requests filtered by status (e.g., get all pending human review)
    # If no status provided, returns all requests ordered by creation time
    @staticmethod
    def get_pending_requests(status: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            
            if status:
                cursor.execute("""
                    SELECT * FROM pending_requests 
                    WHERE status = ?
                    ORDER BY created_at DESC
                """, (status,))
            else:
                cursor.execute("""
                    SELECT * FROM pending_requests 
                    ORDER BY created_at DESC
                """)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    # Dynamic UPDATE - only updates fields that are provided (not None)
    # Builds SET clause dynamically based on which fields need updating
    # Always updates updated_at timestamp
    @staticmethod
    def update_request(
        request_id: str,
        extracted_data: Optional[Dict[str, Any]] = None,
        confidence_score: Optional[Dict[str, Any]] = None,
        ai_summary: Optional[str] = None,
        ai_recommendation: Optional[str] = None,
        status: Optional[str] = None,
        checker_decision: Optional[str] = None,
        checker_id: Optional[str] = None,
        rejection_reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        updates = []
        params = []
        now = utcnow()
        
        if extracted_data is not None:
            updates.append("extracted_data = ?")
            params.append(json.dumps(extracted_data))
        
        if confidence_score is not None:
            updates.append("confidence_score = ?")
            params.append(json.dumps(confidence_score))
        
        if ai_summary is not None:
            updates.append("ai_summary = ?")
            params.append(ai_summary)
        
        if ai_recommendation is not None:
            updates.append("ai_recommendation = ?")
            params.append(ai_recommendation)
        
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        
        if checker_decision is not None:
            updates.append("checker_decision = ?")
            params.append(checker_decision)
        
        if checker_id is not None:
            updates.append("checker_id = ?")
            params.append(checker_id)
        
        if rejection_reason is not None:
            updates.append("rejection_reason = ?")
            params.append(rejection_reason)
        
        updates.append("updated_at = ?")
        params.append(now)
        params.append(request_id)
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE pending_requests 
                SET {', '.join(updates)}
                WHERE request_id = ?
            """, params)
            
            if cursor.rowcount > 0:
                return RequestRepository.get_request(request_id)
        return None
    
    # Record an RPS (banking system) update for audit purposes
    @staticmethod
    def add_rps_update(request_id: str, rps_reference: str, updated_fields: Dict[str, Any], status: str) -> int:
        now = utcnow()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rps_updates (request_id, rps_reference, updated_fields, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (request_id, rps_reference, json.dumps(updated_fields), status, now))
            return cursor.lastrowid if cursor.lastrowid is not None else 0
    
    # Get RPS updates - optionally filtered by request_id
    @staticmethod
    def get_rps_updates(request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            if request_id:
                cursor.execute("""
                    SELECT * FROM rps_updates WHERE request_id = ? ORDER BY created_at DESC
                """, (request_id,))
            else:
                cursor.execute("SELECT * FROM rps_updates ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    # Get all RPS updates for a specific customer (via JOIN with pending_requests)
    @staticmethod
    def get_customer_rps_history(customer_id: str) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.* FROM rps_updates r
                JOIN pending_requests p ON r.request_id = p.request_id
                WHERE p.customer_id = ?
                ORDER BY r.created_at DESC
            """, (customer_id,))
            return [dict(row) for row in cursor.fetchall()]


# Repository class for audit_logs table operations
class AuditRepository:
    @staticmethod
    def log_event(request_id: str, event_type: str, event_data: Dict[str, Any]) -> str:
        import uuid
        log_id = str(uuid.uuid4())
        now = utcnow()
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_logs (log_id, request_id, event_type, event_data, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (log_id, request_id, event_type, json.dumps(event_data), now))
        
        return log_id
    
    # Get all audit logs for a request, ordered by timestamp (chronological)
    @staticmethod
    def get_logs(request_id: str) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM audit_logs 
                WHERE request_id = ?
                ORDER BY timestamp ASC
            """, (request_id,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


# Initialize database on module import (creates tables if needed)
init_db()
