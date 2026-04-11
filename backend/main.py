from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.routes import router as api_router
from backend.services.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("IASW Backend started - Database initialized")
    yield
    print("IASW Backend shutting down")


app = FastAPI(
    title="Intelligent Account Servicing Workflow (IASW)",
    description="Agentic AI system for banking account change requests with Human-in-the-Loop approval",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "service": "IASW Backend",
        "version": "1.0.0",
        "description": "Intelligent Account Servicing Workflow",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
