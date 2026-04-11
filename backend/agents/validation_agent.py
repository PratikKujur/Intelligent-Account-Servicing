"""
Validation Agent - LLM-powered validation using LangChain + Groq.
"""
import os
import re
from typing import Dict, Any, Tuple, Optional
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    is_valid: bool
    errors: list
    warnings: list
    explanation: str


VALIDATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Validate identity verification request:
1. Both old_name and new_name are present and valid (letters, spaces only)
2. Names are reasonable length (2-100 chars)
3. New name is different from old name
4. DOB format is reasonable if provided
5. Aadhaar format is valid 12 digits if provided

Return JSON: is_valid, errors[], warnings[], explanation"""),
    ("human", "Customer: {customer_id}\nCurrent Name: {old_name}\nNew Name: {new_name}\nDOB: {dob}\nAadhaar: {adhar}")
])


class ValidationAgent:
    """
    LLM-powered validation with fallback to rules.
    """
    
    NAME_PATTERN = re.compile(r'^[a-zA-Z\s\-\.]+$')
    MIN_LEN, MAX_LEN = 2, 100
    ADHAR_PATTERN = re.compile(r'^\d{12}$|^\d{4}\s?\d{4}\s?\d{4}$')
    TEXT_MODEL = "llama-3.3-70b-versatile"
    
    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self._llm = None
        self._parser = JsonOutputParser(pydantic_schema=ValidationResult)
        self._chain = None
        self._init_llm()
    
    def _init_llm(self):
        if not self.groq_api_key:
            return
        try:
            self._llm = ChatGroq(
                api_key=self.groq_api_key,
                model=self.TEXT_MODEL,
                temperature=0.1,
            )
            self._chain = VALIDATION_PROMPT | self._llm | self._parser
        except Exception as e:
            print(f"LLM init failed: {e}")
    
    def validate(
        self,
        old_name: str,
        new_name: str,
        customer_id: str,
        date_of_birth: Optional[str] = None,
        aadhar_number: Optional[str] = None
    ) -> Tuple[str, str]:
        if self._chain and self.groq_api_key:
            return self._llm_validate(old_name, new_name, customer_id, date_of_birth, aadhar_number)
        return self._rule_validate(old_name, new_name, customer_id, date_of_birth, aadhar_number)
    
    def _llm_validate(
        self,
        old_name: str,
        new_name: str,
        customer_id: str,
        date_of_birth: Optional[str],
        aadhar_number: Optional[str]
    ) -> Tuple[str, str]:
        try:
            result = self._chain.invoke({
                "customer_id": customer_id,
                "old_name": old_name,
                "new_name": new_name,
                "dob": date_of_birth or "Not provided",
                "adhar": aadhar_number or "Not provided"
            })
            if result.get("is_valid", False):
                return ("VALID", result.get("explanation", "Validation passed"))
            return ("INVALID", "; ".join(result.get("errors", [])))
        except Exception as e:
            print(f"LLM validation failed: {e}")
            return self._rule_validate(old_name, new_name, customer_id, date_of_birth, aadhar_number)
    
    def _rule_validate(
        self,
        old_name: str,
        new_name: str,
        customer_id: str,
        date_of_birth: Optional[str],
        aadhar_number: Optional[str]
    ) -> Tuple[str, str]:
        errors = []
        
        if not customer_id or not customer_id.strip():
            errors.append("Customer ID required")
        
        if not old_name or not old_name.strip():
            errors.append("Current name required")
        else:
            old_name = old_name.strip()
            if len(old_name) < self.MIN_LEN:
                errors.append("Current name too short")
            if len(old_name) > self.MAX_LEN:
                errors.append("Current name too long")
            if not self.NAME_PATTERN.match(old_name):
                errors.append("Current name has invalid characters")
        
        if not new_name or not new_name.strip():
            errors.append("New name required")
        else:
            new_name = new_name.strip()
            if len(new_name) < self.MIN_LEN:
                errors.append("New name too short")
            if len(new_name) > self.MAX_LEN:
                errors.append("New name too long")
            if not self.NAME_PATTERN.match(new_name):
                errors.append("New name has invalid characters")
        
        if old_name.lower() == new_name.lower():
            errors.append("New name must be different from current name")
        
        if aadhar_number:
            cleaned = re.sub(r'\s', '', aadhar_number)
            if not cleaned.isdigit() or len(cleaned) != 12:
                errors.append("Invalid Aadhaar format")
        
        if errors:
            return ("INVALID", "; ".join(errors))
        return ("VALID", "Validation passed")
    
    def validate_request_data(self, data: Dict[str, Any]) -> Tuple[str, str]:
        return self.validate(
            old_name=data.get("old_name", ""),
            new_name=data.get("new_name", ""),
            customer_id=data.get("customer_id", ""),
            date_of_birth=data.get("date_of_birth"),
            aadhar_number=data.get("aadhar_number")
        )


def get_validation_agent(groq_api_key: Optional[str] = None) -> ValidationAgent:
    return ValidationAgent(groq_api_key)
