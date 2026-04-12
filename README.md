# Intelligent Account Servicing Workflow (IASW)

## 1. About This Application

**IASW (Intelligent Account Servicing Workflow)** is an **agentic AI system** designed for banking operations, specifically for processing **Aadhaar-based name change requests** with **Human-in-the-Loop (HITL) approval**.

### Core Purpose

- Automate verification of customer name change requests using AI agents
- Extract data from Aadhaar identity documents using OCR and Vision AI
- Calculate confidence scores for name change validity
- Generate AI-powered summaries and recommendations
- Require human checker approval before updating the core banking system (RPS)

### Key Workflow

1. Customer submits a name change request with optional Aadhaar document
2. AI agents process and verify the request
3. Request is staged for human review
4. A human checker reviews AI findings and makes a final decision
5. Only upon checker approval is the core banking system (RPS) updated

---

## 2. How to Setup the Application

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- GROQ API Key (for LLM inference)

### Backend Setup

```bash
# Navigate to project root
cd Intelligent-Account-Servicing

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn langchain-groq langchain-core pydantic pypdf pytesseract python-dotenv Pillow psycopg2-binary

# Configure environment variables
# Create .env file with your API keys:
# Copy .env.example and update with your values

# Install Tesseract OCR (system dependency)
# Ubuntu/Debian:
sudo apt-get install tesseract-ocr
# macOS:
brew install tesseract
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
```

### Database Setup

The application supports **PostgreSQL** (recommended for production) and **SQLite** (for development/prototype).

**Using PostgreSQL:**
```bash
# Create PostgreSQL database
psql -U postgres -c "CREATE DATABASE banking_service;"

# Set DATABASE_URL in .env
DATABASE_URL=postgresql://user:password@localhost:5432/banking_service
```

**Using SQLite (default - no setup needed):**
```bash
# DATABASE_URL not set = SQLite automatically
# Database file: data/banking_system.db
```

**Important:** If your password contains special characters (`&`, `@`, `#`, etc.), URL-encode them:
- `P@ssw0rd&123` → `P%40ssw0rd%26123`
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Running the Application

```bash
# Start backend (from project root)
python -m backend.main
# Or: uvicorn backend.main:app --reload --port 8000

# Frontend runs separately (from frontend directory)
npm run dev
```

### Access Points

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Frontend**: http://localhost:5173 (or as shown in terminal)

---

## 3. High Level Design (HLD)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           IASW SYSTEM ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐         ┌──────────────────┐         ┌──────────────────┐
  │   Customer   │         │    IASW API      │         │   Human Checker  │
  │   Frontend   │────────▶│   (FastAPI)      │◀────────│   Dashboard      │
  └──────────────┘         └────────┬─────────┘         └──────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
              ┌─────▼─────┐ ┌──────▼────┐ ┌──────▼──────┐
              │ Validation │ │ Document  │ │  Confidence │
              │   Agent    │ │ Processor │ │   Scorer    │
              └─────┬─────┘ └──────┬────┘ └──────┬──────┘
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                            ┌──────▼──────┐
                            │   Summary   │
                            │   Agent     │
                            └──────┬──────┘
                                   │
                     ┌──────────────┴──────────────┐
                     │                             │
               ┌─────▼─────┐                 ┌──────▼──────┐
               │ PostgreSQL │                 │  Audit Log  │
               │   (SQLite │                 │   Service   │
               │  fallback)│                 └─────────────┘
               └───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │     RPS Mock Service         │
                    │  (Human-in-the-Loop Only)    │
                    └─────────────────────────────┘
                                   │
                            ┌──────▼──────┐
                            │    Core     │
                            │   Banking   │
                            │   System    │
                            └─────────────┘
```

### Request Status Flow

```
DRAFT
   │
   ▼
AI_PROCESSING (AI pipeline running)
   │
   ├──► FAILED (validation/extraction error)
   │
   └──► AI_VERIFIED_PENDING_HUMAN
              │
              ├──► APPROVED (checker approves)
              │
              ├──► REJECTED (checker rejects)
              │
              └──► RPS_UPDATED (approved + RPS updated)
```

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/requests/submit` | POST | Submit new name change request |
| `/api/v1/requests/{id}` | GET | Get request details |
| `/api/v1/requests` | GET | List all requests |
| `/api/v1/requests/pending/review` | GET | Get pending human reviews |
| `/api/v1/checker/decide` | POST | Submit checker decision |
| `/api/v1/audit/{id}` | GET | Get audit trail |
| `/api/v1/health` | GET | Health check |

---

## 4. Agents and Their Purpose

The system uses **4 specialized AI agents**, all powered by **LangChain + Groq LLM** with rule-based fallbacks:

### A. Validation Agent (`backend/agents/validation_agent.py`)

- **Purpose:** Validates input request data
- **Responsibilities:**
  - Ensures both old_name and new_name are present and valid
  - Checks name length (2-100 characters)
  - Validates characters (letters, spaces, hyphens, periods only)
  - Ensures new name differs from old name
  - Validates Aadhaar number format (12 digits)
- **LLM Model:** `llama-3.3-70b-versatile`
- **Fallback:** Rule-based validation if LLM unavailable

### B. Document Processor Agent (`backend/agents/document_processor.py`)

- **Purpose:** Extracts structured data from Aadhaar documents
- **Responsibilities:**
  - Processes PDF and image documents
  - Supports Vision LLM (`meta-llama/llama-4-scout-17b-16e-instruct`) for direct image processing
  - Fallback to OCR (pytesseract) + text extraction
  - Extracts: name, date of birth, Aadhaar number
  - Detects forgery flags and document authenticity
- **Extraction Methods:**
  1. Vision AI (preferred) - direct image analysis
  2. LLM-based extraction with OCR text
  3. Regex-based fallback extraction

### C. Confidence Scorer Agent (`backend/agents/confidence_scorer.py`)

- **Purpose:** Calculates verification confidence scores
- **Scoring Dimensions:**
  - `name_change_request_score` (0-100): Validity of name change
  - `document_to_old_match` (0-100): Document matches old name
  - `document_to_new_match` (0-100): Document matches new name
  - `dob_match` (0-100): Date of birth verification
  - `adhar_match` (0-100): Aadhaar number validation
  - `doc_auth` (0-100): Document authenticity
  - `overall` (0-100): Weighted composite score
- **Recommendation Logic:**
  - >= 85: APPROVE
  - >= 70: APPROVE_WITH_CAUTION
  - >= 50: MANUAL_REVIEW
  - < 50: REJECT

### D. Summary Agent (`backend/agents/summary_agent.py`)

- **Purpose:** Generates human-readable compliance summaries
- **Output Sections:**
  1. Request Details
  2. Document Verification
  3. Name Change Analysis
  4. Flags/Concerns
  5. Recommendation with justification
- **Key Logic:** Understands valid name change patterns (document shows NEW name = valid)

### Human-in-the-Loop Security

The **RPS (Real-Time Platform System) Mock** enforces strict authorization:

```python
def _enforce_authorization(self, checker_id: Optional[str]) -> bool:
    """Enforce HITL - ensure only authorized users can call RPS"""
    if not checker_id:
        raise PermissionError("AI not authorized to call RPS. Human checker required.")
    return True
```

**Critical Rule:** AI agents CANNOT directly update the core banking system. Only a human checker with a valid `checker_id` can trigger RPS updates.

---

## 5. Tech Stack

### Backend Technologies

| Technology | Purpose | Why Chosen |
|------------|---------|------------|
| **FastAPI** | REST API framework | High-performance async framework, automatic OpenAPI docs, Pydantic integration |
| **Uvicorn** | ASGI server | Fast, production-ready ASGI server for running FastAPI |
| **LangChain (core + groq)** | LLM orchestration | Modular agent framework, chain composition, structured output parsing |
| **Groq LLM API** | Language model inference | Fast inference, cost-effective, supports vision models |
| **Pydantic** | Data validation | Type-safe request/response schemas with automatic validation |
| **pypdf** | PDF processing | Lightweight PDF text extraction for Aadhaar documents |
| **pytesseract** | OCR engine | Open-source OCR for text extraction from images |
| **Pillow** | Image processing | Python Imaging Library for handling document images |
| **python-dotenv** | Environment config | Load environment variables from .env files |
| **PostgreSQL** | Database (primary) | Production-ready, concurrent connections, ACID compliance |
| **SQLite** | Database (fallback) | Zero-configuration, file-based, for development/prototype |
| **psycopg2** | PostgreSQL adapter | Python driver for PostgreSQL database |

### Frontend Technologies

| Technology | Purpose | Why Chosen |
|------------|---------|------------|
| **React 18** | UI framework | Component-based architecture, strong ecosystem |
| **TypeScript** | Type safety | Catch errors at compile time, better IDE support |
| **Vite** | Build tool | Fast HMR, optimized builds |
| **React Router** | Client-side routing | SPA navigation |
| **CSS Variables** | Styling | Custom CSS, no framework overhead |

### DevDependencies

| Technology | Purpose |
|------------|---------|
| **@vitejs/plugin-react** | Vite React integration |
| **@types/react** | TypeScript definitions |
| **@types/react-dom** | TypeScript definitions |
| **TypeScript** | Type checking |

### Why These Technologies?

**FastAPI + Pydantic:**
- Native async support for high concurrency
- Automatic request/response validation
- Built-in OpenAPI documentation
- Type safety from Python to API

**LangChain + Groq:**
- Structured agent orchestration with reusable prompts
- Chain composition for complex workflows
- Groq provides fast, low-cost LLM inference
- Vision model support for document analysis

**React + TypeScript:**
- Type-safe frontend development
- Strong tooling and IDE support
- Predictable state management
- Large ecosystem of components

**Vite:**
- Sub-second hot module replacement
- Optimized production builds
- Native ESM support
- Minimal configuration

**pytesseract + pypdf:**
- Open-source document processing
- No external API costs for OCR
- Local processing for privacy

---

## Project Structure

```
Intelligent-Account-Servicing/
├── backend/
│   ├── agents/
│   │   ├── validation_agent.py       # Input validation
│   │   ├── document_processor.py     # OCR + Vision extraction
│   │   ├── confidence_scorer.py      # Score calculation
│   │   └── summary_agent.py          # LLM summary generation
│   ├── api/
│   │   └── routes.py                 # FastAPI endpoints
│   ├── services/
│   │   ├── database.py               # PostgreSQL/SQLite repositories
│   │   ├── ai_pipeline.py            # Pipeline orchestrator
│   │   ├── audit.py                  # Audit logging
│   │   └── rps_mock.py               # RPS mock (HITL boundary)
│   ├── models/
│   │   └── schemas.py                # Pydantic models
│   └── main.py                       # FastAPI app entry
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx     # Overview dashboard
│   │   │   ├── IntakePage.tsx       # Request submission
│   │   │   └── CheckerPage.tsx       # Human review interface
│   │   ├── services/
│   │   │   └── api.ts                # API client
│   │   ├── types/
│   │   │   └── index.ts              # TypeScript interfaces
│   │   └── App.tsx                   # Router setup
│   ├── vite.config.ts
│   └── package.json
├── data/
│   ├── logs/                         # Audit logs (JSON files)
│   ├── uploads/                      # Uploaded documents
│   └── banking_system.db             # SQLite database (if using SQLite)
├── pyproject.toml
├── requirements.txt
└── .env
```
