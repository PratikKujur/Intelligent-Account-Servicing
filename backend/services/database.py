# Database abstraction layer - supports both SQLite and PostgreSQL
# Use DATABASE_URL env var to switch between databases:
#   - SQLite: DATABASE_URL not set (default)
#   - PostgreSQL: DATABASE_URL=postgresql://user:pass@host:5432/dbname

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import os

# Import database drivers
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

# Database configuration
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "banking_system.db")


def _get_db_config():
    """Get database configuration from environment (lazy evaluation)."""
    return os.getenv("DATABASE_URL"), bool(os.getenv("DATABASE_URL"))


def get_db_connection():
    DATABASE_URL, use_postgres = _get_db_config()
    
    if use_postgres and DATABASE_URL:
        print(f"Connecting to PostgreSQL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
        # Use RealDictCursor to return dict-like rows
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        conn.autocommit = False
        return conn
    else:
        print(f"Connecting to SQLite: {DATABASE_PATH}")
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


# Context manager for database connections - ensures proper commit/rollback
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


# Helper to get current timestamp in ISO format
def utcnow():
    return datetime.utcnow().isoformat()


# Initialize database schema
def init_db():
    _, use_postgres = _get_db_config()
    if use_postgres:
        _init_postgres()
    else:
        _init_sqlite()


def _init_sqlite():
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
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON pending_requests(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_created ON pending_requests(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_logs(request_id)")


def _init_postgres():
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_requests (
                request_id VARCHAR(255) PRIMARY KEY,
                customer_id VARCHAR(255) NOT NULL,
                old_name VARCHAR(255) NOT NULL,
                new_name VARCHAR(255) NOT NULL,
                extracted_data TEXT,
                confidence_score TEXT,
                ai_summary TEXT,
                ai_recommendation VARCHAR(50),
                status VARCHAR(50) NOT NULL,
                checker_decision VARCHAR(50),
                checker_id VARCHAR(255),
                rejection_reason TEXT,
                rps_reference VARCHAR(255),
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id VARCHAR(255) PRIMARY KEY,
                request_id VARCHAR(255) NOT NULL,
                event_type VARCHAR(100) NOT NULL,
                event_data TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                FOREIGN KEY (request_id) REFERENCES pending_requests(request_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rps_updates (
                id SERIAL PRIMARY KEY,
                request_id VARCHAR(255) NOT NULL,
                rps_reference VARCHAR(255),
                updated_fields TEXT,
                status VARCHAR(50),
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (request_id) REFERENCES pending_requests(request_id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON pending_requests(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_created ON pending_requests(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_logs(request_id)")


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert row to dictionary."""
    # Both SQLite (with row_factory) and PostgreSQL (with RealDictCursor) return dict-like rows
    return dict(row)


# Repository class for pending_requests table operations
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
                VALUES (%s, %s, %s, %s, %s, %s, %s)
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
            cursor.execute("SELECT * FROM pending_requests WHERE request_id = %s", (request_id,))
            row = cursor.fetchone()
            
            if row:
                return _row_to_dict(row)
        return None
    
    @staticmethod
    def get_pending_requests(status: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            
            if status:
                cursor.execute("""
                    SELECT * FROM pending_requests 
                    WHERE status = %s
                    ORDER BY created_at DESC
                """, (status,))
            else:
                cursor.execute("SELECT * FROM pending_requests ORDER BY created_at DESC")
            
            rows = cursor.fetchall()
            return [_row_to_dict(row) for row in rows]
    
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
            updates.append("extracted_data = %s")
            params.append(json.dumps(extracted_data))
        
        if confidence_score is not None:
            updates.append("confidence_score = %s")
            params.append(json.dumps(confidence_score))
        
        if ai_summary is not None:
            updates.append("ai_summary = %s")
            params.append(ai_summary)
        
        if ai_recommendation is not None:
            updates.append("ai_recommendation = %s")
            params.append(ai_recommendation)
        
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        
        if checker_decision is not None:
            updates.append("checker_decision = %s")
            params.append(checker_decision)
        
        if checker_id is not None:
            updates.append("checker_id = %s")
            params.append(checker_id)
        
        if rejection_reason is not None:
            updates.append("rejection_reason = %s")
            params.append(rejection_reason)
        
        updates.append("updated_at = %s")
        params.append(now)
        params.append(request_id)
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE pending_requests 
                SET {', '.join(updates)}
                WHERE request_id = %s
            """, params)
            
            if cursor.rowcount > 0:
                return RequestRepository.get_request(request_id)
        return None
    
    @staticmethod
    def add_rps_update(request_id: str, rps_reference: str, updated_fields: Dict[str, Any], status: str) -> int:
        now = utcnow()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rps_updates (request_id, rps_reference, updated_fields, status, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (request_id, rps_reference, json.dumps(updated_fields), status, now))
            return cursor.lastrowid if cursor.lastrowid else 0
    
    @staticmethod
    def get_rps_updates(request_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            if request_id:
                cursor.execute("SELECT * FROM rps_updates WHERE request_id = %s ORDER BY created_at DESC", (request_id,))
            else:
                cursor.execute("SELECT * FROM rps_updates ORDER BY created_at DESC")
            return [_row_to_dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get_customer_rps_history(customer_id: str) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.* FROM rps_updates r
                JOIN pending_requests p ON r.request_id = p.request_id
                WHERE p.customer_id = %s
                ORDER BY r.created_at DESC
            """, (customer_id,))
            return [_row_to_dict(row) for row in cursor.fetchall()]


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
                VALUES (%s, %s, %s, %s, %s)
            """, (log_id, request_id, event_type, json.dumps(event_data), now))
        
        return log_id
    
    @staticmethod
    def get_logs(request_id: str) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM audit_logs 
                WHERE request_id = %s
                ORDER BY timestamp ASC
            """, (request_id,))
            
            rows = cursor.fetchall()
            return [_row_to_dict(row) for row in rows]


init_db()
