# app/phase2_submitter.py
import requests
from typing import Dict, Any
import logging

logger = logging.getLogger("phase2.submitter")
logger.setLevel(logging.INFO)

def submit_answer(submission_url: str, payload: Dict[str, Any], headers: Dict[str,str] = None, timeout: int = 10):
    headers = headers or {"Content-Type": "application/json"}
    try:
        r = requests.post(submission_url, json=payload, headers=headers, timeout=timeout)
        try:
            return r.json()
        except Exception:
            return {"status_code": r.status_code, "text": r.text}
    except Exception as e:
        logger.exception("submit_answer failed: %s", e)
        return {"error": str(e)}
