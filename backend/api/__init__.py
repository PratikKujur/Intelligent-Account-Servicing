# API package - exports router for FastAPI app configuration
# All REST endpoints are defined in routes.py

from backend.api.routes import router

__all__ = ["router"]  # FastAPI router with all /api/v1 endpoints
