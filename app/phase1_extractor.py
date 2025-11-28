# app/phase1_extractor.py
import logging
import re

logger = logging.getLogger("phase1.extractor")


def _clean_contents(text: str) -> str:
    """
    Clean extracted HTML text:
    - Remove long stretches of digits (CSV dumps)
    - Collapse whitespace
    - Limit max length
    """
    if not text:
        return ""

    # Remove raw CSV-like multi-line number blocks
    text = re.sub(r"(?:\d+\s*){50,}", " ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Limit extremely large text
    if len(text) > 3000:
        text = text[:3000] + " ...[truncated]..."

    return text


def identify_quiz_components(all_pages: list) -> dict:
    """
    Convert raw scraper output into structured format for Phase-2 LLM.
    """
    structured_pages = []

    for p in all_pages:
        cleaned_text = _clean_contents(p.get("text", "") or "")

        structured_pages.append({
            "url": p.get("url"),
            "contents": cleaned_text,
            "attachments": p.get("attachments", [])
        })

    return {"pages": structured_pages}
