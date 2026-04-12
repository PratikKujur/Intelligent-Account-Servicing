# Agents package - exports all AI agents for use by other modules
# Centralizes imports for cleaner code elsewhere

from backend.agents.validation_agent import ValidationAgent, get_validation_agent
from backend.agents.document_processor import DocumentProcessor, get_document_processor, ExtractionResult
from backend.agents.confidence_scorer import ConfidenceScorer, get_confidence_scorer
from backend.agents.summary_agent import SummaryAgent, get_summary_agent

__all__ = [
    # Validation Agent - validates input request data
    "ValidationAgent",
    "get_validation_agent",
    # Document Processor - extracts data from identity documents
    "DocumentProcessor",
    "get_document_processor",
    "ExtractionResult",
    # Confidence Scorer - calculates verification confidence scores
    "ConfidenceScorer",
    "get_confidence_scorer",
    # Summary Agent - generates human-readable compliance summaries
    "SummaryAgent",
    "get_summary_agent",
]
