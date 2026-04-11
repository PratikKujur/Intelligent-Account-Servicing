"""
Summary Agent - LLM-powered summary generation using LangChain + Groq.
"""
import os
from typing import Dict, Any, Optional
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a compliance officer reviewing NAME CHANGE REQUESTS for Aadhaar cards.

IMPORTANT: This is a NAME CHANGE REQUEST. The customer wants to change their name from 'Old Name' to 'New Name'. 
You are verifying that the submitted Aadhaar document belongs to the person filing this request.
(Note: document_to_old_match is low(>=10) means doc name & old name are similar and document_to_new_match is high means doc name & old name are same, 
    these conditions reflect positive for Name change requests.)

Generate a clear summary with these sections:
1. REQUEST DETAILS: Type of request (Name Change), old name, new name, DOB
2. DOCUMENT VERIFICATION: What was extracted from the Aadhaar document
3. NAME CHANGE ANALYSIS: Compare - Old Name vs Extracted Name. The extracted name should match the OLD name for verification to pass.
4. FLAGS/CONCERNS: Any suspicious findings
5. RECOMMENDATION: Clear APPROVE/REJECT guidance, based on all confidence scores and Overall Confidence, 
decide whether it is a valid name change request or not.

Be concise, factual, and highlight any discrepancies."""),
    ("human", """NAME CHANGE REQUEST:
- Current/Old Name: {old_name}
- Requested/New Name: {new_name}
- Date of Birth: {requested_dob}

AADHAAR DOCUMENT EXTRACTED DATA:
{extracted_data}

CONFIDENCE SCORES:
- Name Change Request Score: {name_change_request_score}%
- Document to Old Name Match: {document_to_old_match}%
- Document to New Name Match: {document_to_new_match}%
- DOB Match: {dob_match}%
- Aadhaar Match: {adhar_match}%
- Document Authenticity: {doc_auth}%
- Overall Confidence: {overall}%

Generate verification summary.""")
])


class SummaryAgent:
    """
    LLM-powered summary generation with fallback to rules.
    """
    
    TEXT_MODEL = "llama-3.3-70b-versatile"
    
    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self._llm = None
        self._chain = None
        self._init_llm()
    
    def _init_llm(self):
        if not self.groq_api_key:
            return
        try:
            self._llm = ChatGroq(
                api_key=self.groq_api_key,
                model=self.TEXT_MODEL,
                temperature=0.3,
            )
            self._chain = SUMMARY_PROMPT | self._llm | StrOutputParser()
        except Exception as e:
            print(f"LLM init failed: {e}")
    
    def generate_summary(
        self,
        extracted_data: Dict[str, Any],
        confidence_scores: Dict[str, Any],
        old_name: str,
        new_name: str,
        requested_dob: Optional[str],
        recommendation: str
    ) -> str:
        if self._chain and self.groq_api_key:
            return self._llm_generate_summary(
                extracted_data, confidence_scores,
                old_name, new_name, requested_dob
            )
        return self._rule_based_summary(
            extracted_data, confidence_scores,
            old_name, new_name, requested_dob, recommendation
        )
    
    def _llm_generate_summary(
        self,
        extracted_data: Dict[str, Any],
        confidence_scores: Dict[str, Any],
        old_name: str,
        new_name: str,
        requested_dob: Optional[str]
    ) -> str:
        try:
            return self._chain.invoke({
                "old_name": old_name,
                "new_name": new_name,
                "requested_dob": requested_dob or "Not provided",
                "extracted_data": self._format_data(extracted_data),
                "name_change_request_score": confidence_scores.get("name_change_request_score", 0),
                "document_to_old_match": confidence_scores.get("document_to_old_match", 0),
                "document_to_new_match": confidence_scores.get("document_to_new_match", 0),
                "dob_match": confidence_scores.get("dob_match", 0),
                "adhar_match": confidence_scores.get("adhar_match", 0),
                "doc_auth": confidence_scores.get("doc_auth", 0),
                "overall": confidence_scores.get("overall", 0),
            }).strip()
        except Exception as e:
            print(f"LLM summary failed: {e}")
            return self._rule_based_summary(
                extracted_data, confidence_scores,
                old_name, new_name, requested_dob, "MANUAL_REVIEW"
            )
    
    def _format_data(self, data: Dict[str, Any]) -> str:
        fields = [
            ('name', 'Name'),
            ('date_of_birth', 'Date of Birth'),
            ('aadhar_number', 'Aadhaar Number')
        ]
        lines = [f"- {label}: {data[k]}" for k, label in fields if data.get(k)]
        if data.get('forgery_flag'):
            lines.append("- FORGERY FLAG DETECTED")
        return "\n".join(lines) if lines else "Limited data extracted"
    
    def _rule_based_summary(
        self,
        extracted_data: Dict[str, Any],
        confidence_scores: Dict[str, Any],
        old_name: str,
        new_name: str,
        requested_dob: Optional[str],
        recommendation: str
    ) -> str:
        lines = ["=== NAME CHANGE REQUEST VERIFICATION ===\n"]
        lines.append("REQUEST DETAILS:")
        lines.append(f"  - Type: Name Change Request")
        lines.append(f"  - Current/Old Name: {old_name}")
        lines.append(f"  - Requested/New Name: {new_name}")
        lines.append(f"  - Date of Birth: {requested_dob or 'Not provided'}")
        
        lines.append("\nDOCUMENT EXTRACTED DATA:")
        if extracted_data.get('name'):
            lines.append(f"  - Name from Aadhaar: {extracted_data['name']}")
        if extracted_data.get('date_of_birth'):
            lines.append(f"  - Date of Birth: {extracted_data['date_of_birth']}")
        if extracted_data.get('aadhar_number'):
            lines.append(f"  - Aadhaar Number: {extracted_data['aadhar_number']}")
        
        lines.append("\nNAME CHANGE ANALYSIS:")
        extracted_name = extracted_data.get('name', '')
        old_match = extracted_name.lower().strip() == old_name.lower().strip() if extracted_name else False
        new_match = extracted_name.lower().strip() == new_name.lower().strip() if extracted_name else False
        if extracted_name:
            if old_match:
                lines.append(f"  ✓ Extracted name matches OLD name (valid - document belongs to requester)")
            elif new_match:
                lines.append(f"  ⚠ WARNING: Extracted name matches NEW name (suspicious)")
            else:
                lines.append(f"  ⚠ Extracted: {extracted_name} (no match)")
        
        lines.append("\nCONFIDENCE SCORES:")
        lines.append(f"  - Name Change Request Score: {confidence_scores.get('name_change_request_score', 0)}%")
        lines.append(f"  - Document to Old Name Match: {confidence_scores.get('document_to_old_match', 0)}%")
        lines.append(f"  - Document to New Name Match: {confidence_scores.get('document_to_new_match', 0)}%")
        lines.append(f"  - DOB Match: {confidence_scores.get('dob_match', 0)}%")
        lines.append(f"  - Aadhaar Match: {confidence_scores.get('adhar_match', 0)}%")
        lines.append(f"  - Document Authenticity: {confidence_scores.get('doc_auth', 0)}%")
        lines.append(f"  - Overall: {confidence_scores.get('overall', 0)}%")
        
        if confidence_scores.get('reasoning'):
            lines.append(f"\nASSESSMENT: {confidence_scores['reasoning']}")
        
        lines.append(f"\nRECOMMENDATION: {recommendation}")
        
        return "\n".join(lines)


def get_summary_agent(groq_api_key: Optional[str] = None) -> SummaryAgent:
    return SummaryAgent(groq_api_key)
