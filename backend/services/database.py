import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import os

DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "banking_system.db")


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def utcnow():
    return datetime.utcnow().isoformat()


def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_requests (
                request_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                old_name TEXT NOT NULL,
                new_name TEXT NOT NULL,
                extracted_data TEXT,
                confidence_score TEXT,
                ai_summary TEXT,
                ai_recommendation TEXT,
                status TEXT NOT NULL,
                checker_decision TEXT,
                checker_id TEXT,
                rejection_reason TEXT,
                rps_reference TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (request_id) REFERENCES pending_requests(request_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rps_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                rps_reference TEXT,
                updated_fields TEXT,
                status TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (request_id) REFERENCES pending_requests(request_id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_status 
            ON pending_requests(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_created 
            ON pending_requests(created_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_request 
            ON audit_logs(request_id)
        """)


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
    
    @staticmethod
    def add_rps_update(request_id: str, rps_reference: str, updated_fields: Dict[str, Any], status: str) -> int:
        """Add an RPS update record"""
        now = utcnow()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rps_updates (request_id, rps_reference, updated_fields, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (request_id, rps_reference, json.dumps(updated_fields), status, now))
            return cursor.lastrowid
    
    @staticmethod
    def get_rps_updates(request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get RPS updates, optionally filtered by request_id"""
        with get_db() as conn:
            cursor = conn.cursor()
            if request_id:
                cursor.execute("""
                    SELECT * FROM rps_updates WHERE request_id = ? ORDER BY created_at DESC
                """, (request_id,))
            else:
                cursor.execute("SELECT * FROM rps_updates ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get_customer_rps_history(customer_id: str) -> List[Dict[str, Any]]:
        """Get RPS history for a specific customer"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.* FROM rps_updates r
                JOIN pending_requests p ON r.request_id = p.request_id
                WHERE p.customer_id = ?
                ORDER BY r.created_at DESC
            """, (customer_id,))
            return [dict(row) for row in cursor.fetchall()]


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


init_db()
