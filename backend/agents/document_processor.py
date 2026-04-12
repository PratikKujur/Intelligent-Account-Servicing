"""
Document Processor - LLM-powered extraction using LangChain + Groq.
Supports both OCR (via pytesseract) and Vision models for direct image processing.
Extracts structured data (name, DOB, Aadhaar) from identity documents.
"""

import base64
import io
import os
import re
from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from langchain_groq import ChatGroq
from pypdf import PdfReader
import pytesseract
from PIL import Image
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field


# Pydantic schema for LLM output parsing
class DocumentData(BaseModel):
    name: Optional[str] = Field(description="Full legal name as shown on document")
    date_of_birth: Optional[str] = Field(
        description="Date of birth in any format (DD/MM/YYYY, YYYY-MM-DD, etc)"
    )
    aadhar_number: Optional[str] = Field(description="Aadhaar card number (12 digits)")
    raw_text: Optional[str] = Field(description="Original extracted text from document")
    document_authentic: bool = Field(
        default=True, description="Whether document appears genuine"
    )


# Dataclass for extraction results (used throughout pipeline)
@dataclass
class ExtractionResult:
    name: Optional[str]
    date_of_birth: Optional[str]
    aadhar_number: Optional[str]
    raw_text: str
    forgery_flag: bool
    document_authentic: bool = True


# LLM prompt for extracting data from OCR text
EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert document analyst specializing in Indian identity documents.
Extract structured information from the provided document text.

Return JSON with ONLY these fields:
- name: Full legal name as it appears on the document
- date_of_birth: Date of birth (try to normalize to DD/MM/YYYY format)
- aadhar_number: Aadhaar card number (12 digits, may have spaces or be in format XXX-XXXX-XXXX)
- raw_text: The complete text extracted from the document
- document_authentic: true if document appears genuine, false if suspicious/forged

If a field cannot be found, use null. Be precise with Aadhaar numbers.""",
        ),
        ("human", "Extract data from this document:\n\n{document_text}"),
    ]
)


# LLM prompt for Vision model - directly analyzes image without OCR
VISION_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an expert document analyst specializing in Indian identity documents.
Examine the uploaded image and extract structured information.

Return JSON with ONLY these fields:
- name: Full legal name as it appears on the document
- date_of_birth: Date of birth (try to normalize to DD/MM/YYYY format)
- aadhar_number: Aadhaar card number (12 digits, may have spaces or be in format XXX-XXXX-XXXX)
- raw_text: The complete text visible in the document image
- document_authentic: true if document appears genuine, false if suspicious/forged

Look carefully for signs of tampering, poor image quality, or inconsistency. Return null for fields you cannot confidently determine.""",
    ),
    ("human", [
        {"type": "text", "text": "Extract structured data from this identity document image:"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,{image_data}"}}
    ])
])


# Document Processor - extracts structured data from identity documents
# Processing hierarchy:
# 1. Vision LLM (best) - directly analyzes image
# 2. OCR + LLM - extracts text then LLM parses
# 3. OCR + Regex (fallback) - basic pattern matching
class DocumentProcessor:
    """
    Processes identity documents using Vision LLM or OCR-based extraction.
    Prefers vision models for direct image processing, falls back to OCR.
    """

    VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"  # Vision-capable model
    TEXT_MODEL = "llama-3.3-70b-versatile"  # Text-only model

    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self._llm = None
        self._parser = JsonOutputParser(pydantic_schema=DocumentData)
        self._chain = None
        self._vision_chain = None
        self._init_llm()

    # Initialize both text and vision LLM chains
    def _init_llm(self):
        if not self.groq_api_key:
            return
        try:
            # Text extraction chain: OCR text -> LLM -> structured JSON
            self._llm = ChatGroq(
                api_key=self.groq_api_key,
                model=self.TEXT_MODEL,
                temperature=0.1,
            )
            self._chain = EXTRACTION_PROMPT | self._llm | self._parser
            
            # Vision chain: Image -> Vision LLM -> structured JSON (no OCR needed)
            self._vision_llm = ChatGroq(
                api_key=self.groq_api_key,
                model=self.VISION_MODEL,
                temperature=0.1,
            )
            self._vision_chain = VISION_EXTRACTION_PROMPT | self._vision_llm | self._parser
        except Exception as e:
            print(f"LLM init failed: {e}")

    # Main entry point - processes document and returns extraction result
    # Tries Vision -> OCR+LLM -> OCR+Regex in order of preference
    def process_document(
        self,
        document_data: Optional[str] = None,
        document_path: Optional[str] = None,
        file_content: Optional[bytes] = None,
    ) -> Tuple[bool, ExtractionResult]:
        image_data = None
        raw_text = None
        
        # Load document from various sources
        if document_path and os.path.exists(document_path):
            image_data = self._read_file_as_base64(document_path)
            raw_text = self._extract_text_from_image_path(document_path)
        elif file_content:
            image_data = base64.b64encode(file_content).decode()
            raw_text = self._extract_text_from_bytes(file_content)
        elif document_data:
            try:
                # Try to decode as base64 image
                decoded = base64.b64decode(document_data)
                image_data = document_data
                raw_text = self._extract_text_from_bytes(decoded)
            except Exception:
                # Treat as raw text if not valid base64
                raw_text = document_data

        # Try Vision LLM first (best quality)
        if self._vision_chain and self.groq_api_key and image_data:
            return self._vision_extract(image_data)
        
        # Try OCR + LLM extraction
        if self._chain and self.groq_api_key and raw_text:
            return self._llm_extract(raw_text)
        
        # Last resort: regex-based extraction
        if raw_text:
            return self._regex_extract(raw_text)
        
        raise ValueError("Unable to read document: No valid document provided or document could not be processed")

    # Read file and convert to base64
    def _read_file_as_base64(self, file_path: str) -> Optional[str]:
        try:
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception:
            return None

    # OCR using pytesseract on image file
    def _extract_text_from_image_path(self, file_path: str) -> Optional[str]:
        try:
            return pytesseract.image_to_string(Image.open(file_path))
        except Exception:
            return None

    # OCR using pytesseract on image bytes
    def _extract_text_from_bytes(self, content: bytes) -> Optional[str]:
        try:
            image = Image.open(io.BytesIO(content))
            return pytesseract.image_to_string(image)
        except Exception:
            return None

    # PDF text extraction (for multi-page documents)
    def _extract_pdf(self, file_path: str) -> str:
        try:
            reader = PdfReader(file_path)
            return "\n".join(page.extract_text() for page in reader.pages)
        except Exception:
            raise ValueError(f"Unable to read PDF file: {file_path}")

    # LLM-based extraction from OCR text
    def _llm_extract(self, raw_text: str) -> Tuple[bool, ExtractionResult]:
        try:
            result = self._chain.invoke({"document_text": raw_text})
            return True, ExtractionResult(
                name=result.get("name"),
                date_of_birth=result.get("date_of_birth"),
                aadhar_number=result.get("aadhar_number"),
                raw_text=result.get("raw_text", raw_text),
                forgery_flag=not result.get("document_authentic", True),
                document_authentic=result.get("document_authentic", True),
            )
        except Exception as e:
            print(f"LLM extract failed: {e}")
            return self._regex_extract(raw_text)

    # Vision LLM extraction - directly analyzes image
    def _vision_extract(self, image_data: str) -> Tuple[bool, ExtractionResult]:
        try:
            result = self._vision_chain.invoke({"image_data": image_data})
            return True, ExtractionResult(
                name=result.get("name"),
                date_of_birth=result.get("date_of_birth"),
                aadhar_number=result.get("aadhar_number"),
                raw_text=result.get("raw_text", ""),
                forgery_flag=not result.get("document_authentic", True),
                document_authentic=result.get("document_authentic", True),
            )
        except Exception as e:
            print(f"Vision extract failed: {e}")
            raise ValueError(f"Unable to process document image: {str(e)}")

    # Regex-based extraction fallback
    # Uses pattern matching to find name, DOB, and Aadhaar
    def _regex_extract(self, raw_text: str) -> Tuple[bool, ExtractionResult]:
        name = self._extract_name(raw_text)
        dob = self._extract_dob(raw_text)
        adhar = self._extract_adhar(raw_text)

        return True, ExtractionResult(
            name=name,
            date_of_birth=dob,
            aadhar_number=adhar,
            raw_text=raw_text,
            forgery_flag=self._detect_forgery(raw_text),
            document_authentic=not self._detect_forgery(raw_text),
        )

    # Extract name using regex patterns
    def _extract_name(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:Name|Beneficiary|Holder)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    # Extract date of birth using regex patterns
    def _extract_dob(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:DOB|Date of Birth|D\.O\.B)[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    # Extract Aadhaar number using regex patterns
    def _extract_adhar(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:Aadhaar|Aadhar|Adhar)[:\s]*(?:No\.?)?[:\s]*(\d{4}\s?\d{4}\s?\d{4})",
            r"(\d{4}\s?\d{4}\s?\d{4})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                adhar = re.sub(r"\s", "", match.group(1))
                if len(adhar) == 12:
                    return f"{adhar[:4]} {adhar[4:8]} {adhar[8:12]}"
        return None

    # Basic forgery detection - flags suspicious keywords
    def _detect_forgery(self, text: str) -> bool:
        suspicious = ["copy", "duplicate", "fake", "forged", "tampered"]
        text_lower = text.lower()
        return any(word in text_lower for word in suspicious)


# Factory function
def get_document_processor(groq_api_key: Optional[str] = None) -> DocumentProcessor:
    return DocumentProcessor(groq_api_key)
