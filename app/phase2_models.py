# app/phase2_models.py
from pydantic import BaseModel, AnyHttpUrl
from typing import List, Dict, Any, Optional

class Phase2Request(BaseModel):
    question_purpose: Optional[str]
    submission_url: AnyHttpUrl
    required_request_json_fields: List[str]
    sample_payload_from_page: Dict[str, Any]
    links_found: List[str] = []
    attachments: List[Dict[str, Any]] = []
    raw_text_summary: Optional[str] = ""
    notes_for_solver: Optional[str] = ""
