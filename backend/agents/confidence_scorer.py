"""
Confidence Scorer - LLM-powered scoring using LangChain + Groq.
Calculates multi-dimensional confidence scores for name change verification.
"""
import os
from typing import Dict, Any, Optional
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from difflib import SequenceMatcher  # For fuzzy string matching
import re


# Pydantic schema for LLM output parsing
class ConfidenceScores(BaseModel):
    name_change_request_score: int = Field(description="Name change request validation score 0-100. HIGH (85-100) = valid name change/spelling correction. LOW (0-40) = invalid/already updated.")
    document_to_old_match: int = Field(description="How well extracted name matches OLD name 0-100")
    document_to_new_match: int = Field(description="How well extracted name matches NEW name 0-100. LOW = good for valid name change.")
    dob_match: int = Field(description="Date of birth match score 0-100")
    adhar_match: int = Field(description="Aadhaar number match score 0-100")
    doc_auth: int = Field(description="Document authenticity score 0-100")
    overall: int = Field(description="Overall confidence score 0-100")
    reasoning: str = Field(description="Explanation of scoring")


# LLM prompt for intelligent scoring
# Key insight: Document showing NEW name = valid (already updated)
# Document showing OLD name = needs to be updated
SCORING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at verifying Aadhaar card NAME CHANGE requests.

CRITICAL: Determine if this is a VALID name change request.

NAME CHANGE SCORE (0-100):
- HIGH (85-100): Extracted name matches OLD name but NOT new name (valid name change) OR extracted matches both (spelling correction)
- MEDIUM (50-84): Partial match, needs review
- LOW (0-49): Extracted name matches NEW name only (invalid - document already updated)

DOCUMENT_TO_OLD_MATCH (0-100): How well extracted name matches OLD name. Higher = better identity proof.
DOCUMENT_TO_NEW_MATCH (0-100): How well extracted name matches NEW name. For valid name change: this should be LOW.

Return JSON with all scores and clear reasoning."""),
    ("human", """Old Name: {old_name}
New Name: {new_name}
Requested DOB: {requested_dob}

Extracted Data from Document:
{extracted_data}

Analyze and return confidence scores.""")
])


# Confidence Scorer - calculates verification confidence scores
# Scores are used to generate AI recommendation (APPROVE/REJECT)
class ConfidenceScorer:
    """
    LLM-powered confidence scoring with fallback to rules.
    """
    
    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self._llm = None
        self._parser = JsonOutputParser(pydantic_schema=ConfidenceScores)
        self._chain = None
        self._init_llm()
    
    # Initialize LLM chain
    def _init_llm(self):
        if not self.groq_api_key:
            return
        try:
            self._llm = ChatGroq(
                api_key=self.groq_api_key,
                model="llama-3.3-70b-versatile",
                temperature=0.1,  # Low temp for consistent scoring
            )
            self._chain = SCORING_PROMPT | self._llm | self._parser
        except Exception as e:
            print(f"LLM init failed: {e}")
    
    # Main entry point - calculates confidence scores
    # Tries LLM scoring first, falls back to rule-based
    def score(
        self,
        extracted_data: Dict[str, Any],
        old_name: str,
        new_name: str,
        requested_dob: Optional[str] = None
    ) -> Dict[str, Any]:
        if self._chain and self.groq_api_key:
            return self._llm_score(extracted_data, old_name, new_name, requested_dob)
        return self._rule_based_score(extracted_data, old_name, new_name, requested_dob)
    
    # LLM-based scoring - uses Groq for intelligent analysis
    def _llm_score(
        self,
        extracted_data: Dict[str, Any],
        old_name: str,
        new_name: str,
        requested_dob: Optional[str]
    ) -> Dict[str, Any]:
        try:
            result = self._chain.invoke({
                "old_name": old_name,
                "new_name": new_name,
                "requested_dob": requested_dob or "Not provided",
                "extracted_data": self._format_data(extracted_data)
            })
            
            name_change_score = result.get("name_change_request_score")
            doc_to_old = result.get("document_to_old_match")
            doc_to_new = result.get("document_to_new_match")
            
            # Validate result has required fields
            if name_change_score is None or doc_to_old is None or doc_to_new is None:
                return self._rule_based_score(extracted_data, old_name, new_name, requested_dob)
            
            return {
                "name_change_request_score": name_change_score,
                "document_to_old_match": doc_to_old,
                "document_to_new_match": doc_to_new,
                "dob_match": result.get("dob_match", 0),
                "adhar_match": result.get("adhar_match", 0),
                "doc_auth": result.get("doc_auth", 0),
                "overall": result.get("overall", 0),
                "reasoning": result.get("reasoning", "")
            }
        except Exception as e:
            print(f"LLM scoring failed: {e}")
            return self._rule_based_score(extracted_data, old_name, new_name, requested_dob)
    
    # Format extracted data for LLM prompt
    def _format_data(self, data: Dict[str, Any]) -> str:
        lines = [f"- {k}: {v}" for k, v in data.items() if k != 'raw_text' and v]
        return "\n".join(lines) if lines else "No data"
    
    # Generate reasoning text for rule-based scoring
    def _generate_reasoning_new(self, nc_score: int, doc_to_old: int, doc_to_new: int, dob: int, adhar: int, auth: int, data: Dict[str, Any], old_name: str, new_name: str) -> str:
        reasons = []
        
        if nc_score >= 85:
            if doc_to_new >= 70:
                reasons.append(f"SPELLING CORRECTION: Document shows '{data.get('name', 'N/A')}' matches new name '{new_name}' and similar to old '{old_name}'")
            else:
                reasons.append(f"VALID NAME CHANGE: Document shows '{data.get('name', 'N/A')}' matches old name '{old_name}', different from new '{new_name}'")
        elif nc_score >= 60:
            reasons.append(f"SUSPICIOUS - Partial match with old name")
        else:
            reasons.append(f"INVALID - Document may show new name or not match request")
        
        if adhar >= 80:
            reasons.append("Valid Aadhaar format")
        elif adhar < 50:
            reasons.append("Invalid Aadhaar format")
        
        if auth >= 80:
            reasons.append("Document appears authentic")
        elif auth < 50:
            reasons.append("Document may be suspicious")
        
        return ". ".join(reasons)
    
    # Rule-based scoring - used when LLM unavailable
    # Uses fuzzy matching (SequenceMatcher) for name comparison
    def _rule_based_score(
        self,
        extracted_data: Dict[str, Any],
        old_name: str,
        new_name: str,
        requested_dob: Optional[str]
    ) -> Dict[str, Any]:
        extracted_name = extracted_data.get("name", "") or ""
        
        # Calculate fuzzy match scores using SequenceMatcher
        doc_to_old = self._fuzzy_match(extracted_name, old_name) if extracted_name else 0
        doc_to_new = self._fuzzy_match(extracted_name, new_name) if extracted_name else 0
        
        # Calculate name change request score
        name_change_request_score = self._calculate_name_change_score(doc_to_old, doc_to_new, old_name, new_name)
        
        # Calculate individual dimension scores
        dob_match = self._calculate_dob_match(extracted_data.get("date_of_birth"), requested_dob)
        adhar_match = self._calculate_adhar_match(extracted_data.get("aadhar_number"))
        doc_auth = self._calculate_doc_auth(extracted_data)
        
        # Penalize scores if forgery detected
        if extracted_data.get('forgery_flag', False):
            doc_to_old = max(0, doc_to_old - 30)
            doc_auth = max(0, doc_auth - 40)
        
        # Calculate weighted overall score
        # Weights: name_change(30%), doc_to_old(25%), dob(15%), adhar(15%), auth(15%)
        overall = int(
            (name_change_request_score * 0.30) +
            (doc_to_old * 0.25) +
            (dob_match * 0.15) +
            (adhar_match * 0.15) +
            (doc_auth * 0.15)
        )
        
        return {
            "name_change_request_score": name_change_request_score,
            "document_to_old_match": doc_to_old,
            "document_to_new_match": doc_to_new,
            "dob_match": dob_match,
            "adhar_match": adhar_match,
            "doc_auth": doc_auth,
            "overall": overall,
            "reasoning": self._generate_reasoning_new(name_change_request_score, doc_to_old, doc_to_new, dob_match, adhar_match, doc_auth, extracted_data, old_name, new_name)
        }
    
    # Calculate name change score based on document matching
    # Key insight: Doc similar to OLD and Doc matching NEW = Change Needed
    def _calculate_name_change_score(self, doc_to_old: int, doc_to_new: int, old_name: str, new_name: str) -> int:
        old_equals_new = old_name.lower().strip() == new_name.lower().strip()
        
        if old_equals_new:
            return 10  # No actual change requested
        if doc_to_old >= 80 and doc_to_new < 50:
            return 95  # Doc shows old name = needs update
        if doc_to_old >= 60 and doc_to_new < 70:
            return 75  # Partial match
        if doc_to_new >= 70 and doc_to_old >= 30:
            return 85  # Spelling correction
        if doc_to_old >= 40:
            return 50  # Needs review
        return 20  # Low confidence
    
    def _calculate_name_match(self, extracted_name: Optional[str], requested_name: str) -> int:
        if not extracted_name:
            return 0
        return self._fuzzy_match(extracted_name, requested_name)
    
    # Calculate DOB match score
    def _calculate_dob_match(self, extracted_dob: Optional[str], requested_dob: Optional[str]) -> int:
        if not extracted_dob:
            return 50  # Neutral score if not provided
        if not requested_dob:
            return 70  # Higher if no DOB to compare
        if self._normalize_date(extracted_dob) == self._normalize_date(requested_dob):
            return 100  # Exact match
        return 40  # Mismatch
    
    # Calculate Aadhaar format validity score
    def _calculate_adhar_match(self, aadhar_number: Optional[str]) -> int:
        if not aadhar_number:
            return 30  # Low if not extracted
        cleaned = re.sub(r'\s', '', aadhar_number)
        if len(cleaned) == 12 and cleaned.isdigit():
            return 100  # Valid format
        return 50  # Invalid format
    
    # Calculate document authenticity score
    def _calculate_doc_auth(self, data: Dict[str, Any]) -> int:
        score = 70  # Base score
        if data.get('forgery_flag', False):
            score -= 40  # Penalty for forgery flag
        if not data.get('name') or not data.get('aadhar_number'):
            score -= 20  # Penalty for missing fields
        return max(0, min(100, score))  # Clamp to 0-100
    
    # Normalize date format for comparison
    def _normalize_date(self, date_str: str) -> str:
        match = re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', date_str)
        if match:
            return match.group().replace('/', '-')
        return date_str
    
    # Fuzzy string matching using SequenceMatcher
    # Returns percentage match (0-100)
    def _fuzzy_match(self, s1: str, s2: str) -> int:
        return int(SequenceMatcher(None, s1.lower().strip(), s2.lower().strip()).ratio() * 100)
    
    # Generate reasoning text (unused in current flow but kept for compatibility)
    def _generate_reasoning(self, name: int, dob: int, adhar: int, auth: int, data: Dict[str, Any]) -> str:
        reasons = []
        if name >= 80:
            reasons.append("Name matches closely")
        elif name >= 50:
            reasons.append("Partial name match")
        else:
            reasons.append("Name mismatch")
        
        if adhar >= 80:
            reasons.append("Valid Aadhaar format")
        elif adhar < 50:
            reasons.append("Invalid Aadhaar format")
        
        if auth >= 80:
            reasons.append("Document appears authentic")
        elif auth < 50:
            reasons.append("Document may be suspicious")
        
        return ". ".join(reasons)
    
    # Convert overall score to recommendation
    def get_recommendation(self, overall: int) -> str:
        if overall >= 85:
            return "APPROVE"
        elif overall >= 70:
            return "APPROVE_WITH_CAUTION"
        elif overall >= 50:
            return "MANUAL_REVIEW"
        return "REJECT"


# Factory function
def get_confidence_scorer(groq_api_key: Optional[str] = None) -> ConfidenceScorer:
    return ConfidenceScorer(groq_api_key)
