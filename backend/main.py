# FastAPI framework for REST API endpoints
from fastapi import FastAPI
# Async context manager for startup/shutdown events
from contextlib import asynccontextmanager
# CORS middleware to allow frontend-backend communication
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
# Load environment variables from .env file (GROQ_API_KEY)
from dotenv import load_dotenv

load_dotenv()

# Ensure backend module can be imported when running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import API routes and database initialization
from backend.api.routes import router as api_router
from backend.services.database import init_db


# Startup/shutdown handler - initializes database on app start
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # Create tables if they don't exist
    print("IASW Backend started - Database initialized")
    yield
    print("IASW Backend shutting down")


# Create FastAPI application with metadata and lifespan handler
app = FastAPI(
    title="Intelligent Account Servicing Workflow (IASW)",
    description="Agentic AI system for banking account change requests with Human-in-the-Loop approval",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for all origins (allows frontend to call backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routes under /api/v1 prefix
app.include_router(api_router)


# Root endpoint - provides service info and links to documentation
@app.get("/")
async def root():
    return {
        "service": "IASW Backend",
        "version": "1.0.0",
        "description": "Intelligent Account Servicing Workflow",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


# Run server when script is executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
