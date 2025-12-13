# app/phase2_dispatcher.py
from typing import Dict

def determine_task_type(phase1_json: Dict) -> str:
    """
    Lightweight classifier to choose a script template / LLM hints.
    Returns one of: 'csv', 'audio', 'compute', 'encoding', 'web', 'general'
    """
    text = " ".join([
        phase1_json.get("question_purpose",""),
        phase1_json.get("raw_text_summary",""),
        phase1_json.get("notes_for_solver","")
    ]).lower()

    attachments = phase1_json.get("attachments", []) or []
    att_types = " ".join([str(a.get("type","")) for a in attachments]).lower()

    if "csv" in text or "csv" in att_types:
        return "csv"
    if "audio" in text or "audio" in att_types or "listen" in text:
        return "audio"
    if any(k in text for k in ["sum", "add", "count", "greater", "less", "average", "median"]):
        return "compute"
    if any(k in text for k in ["base64", "gzip", "gz", "encoded"]):
        return "encoding"
    if any(k in text for k in ["click", "canvas", "game", "click this", "hover"]):
        return "web"
    return "general"
