# app/main.py
import traceback
import logging
import json
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.scrapers import extract_webpage_recursive
from app.phase1_extractor import identify_quiz_components
from app.phase2_llm import phase2_llm
from app.phase2_script_builder import _make_prompt, build_script
from app.phase2_executor import execute_phase2_script
from app.config import STUDENT_EMAIL, STUDENT_SECRET

import copy   # <-- REQUIRED for safe FACTS copy
import os      # <<< NEW >>>
from datetime import datetime   # <<< NEW >>>

import os
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = os.getenv("LOG_DIR", ".")
LOG_FILE = os.path.join(LOG_DIR, "worker.log")

logging.basicConfig(level=logging.INFO)

file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding="utf-8"
)
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
file_handler.setFormatter(formatter)

# Attach file handler to root logger
logging.getLogger().addHandler(file_handler)

logger = logging.getLogger("app.main")


app = FastAPI()


# --------------------------------------------------------
# NEW: persistent failed-submission logging
# --------------------------------------------------------
FAILED_LOG_FILE = "failed_submissions.jsonl"   # <<< NEW >>>

def record_failed_submission(url, answer, reason, attempt):   # <<< NEW >>>
    """
    Persist failed evaluator responses to a JSONL file.
    Each line is a JSON object.
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "url": url,
        "answer": answer,
        "reason": reason,
        "attempt_number": attempt,
    }
    try:
        with open(FAILED_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write failed submission log: {e}")
# --------------------------------------------------------


# ---------- Request Model ----------
class Phase1Request(BaseModel):
    url: str
    secret: str


# ---------- Helper: evaluator submit ----------
def submit_to_evaluator(url: str, answer):
    import requests

    payload = {
        "email": STUDENT_EMAIL,
        "secret": STUDENT_SECRET,
        "url": url,
        "answer": answer,
    }

    logger.info(f"Submitting evaluator payload: {payload}")

    try:
        resp = requests.post(
            "https://tds-llm-analysis.s-anand.net/submit",
            json=payload,
            timeout=20,
        )

        try:
            return resp.json()
        except Exception:
            return {"correct": False, "reason": "bad json", "url": None}

    except Exception as e:
        logger.error(f"Evaluator submit failed: {e}")
        return {"correct": False, "url": None}


# ---------- Helper: produce answer from facts ----------
def generate_and_execute(facts, current_url, prior_error=None, prompt_attempt_start=1):
    """
    Runs the LLM prompt generation (up to 3 attempts handled inside phase2_llm if configured)
    and executes the built script. Returns (answer, last_error_string).
    """
    last_error = prior_error
    llm_raw = None

    # Try generating LLM script up to 3 times
    for attempt in range(prompt_attempt_start, 4):

        # -----------------------------------------------------------------
        # *** PATCH START — SAFE evaluator feedback injection into FACTS ***
        # -----------------------------------------------------------------
        facts_for_llm = copy.deepcopy(facts)

        # Insert evaluator feedback (None or text) into the facts the LLM sees
        facts_for_llm["evaluator_feedback"] = last_error if last_error is not None else None

        # Ensure student email is explicitly present for personalized tasks
        try:
            from app.config import STUDENT_EMAIL as _STU_EMAIL
        except Exception:
            _STU_EMAIL = None
        facts_for_llm["student_email"] = _STU_EMAIL
        # -----------------------------------------------------------------
        # *** PATCH END ***
        # -----------------------------------------------------------------

        prompt = _make_prompt(facts_for_llm, current_url, last_error, attempt)

        try:
            llm_raw = phase2_llm(prompt)
            break
        except Exception as e:
            logger.warning(f"LLM generation failed attempt {attempt}/3: {e}")
            last_error = str(e)

    if llm_raw is None:
        logger.error("LLM failed after 3 attempts.")
        return None, last_error

    # Build and execute the script (executor may retry internally)
    try:
        script = build_script(facts, llm_raw, current_url)
        result = execute_phase2_script(script)

        if result and result.get("status") == "ok":
            answer = result["json"]["answer"]
            return answer, None
        else:
            exec_err = result.get("error") if result else "unknown executor failure"
            logger.error("Script failed: %s", exec_err)
            return None, str(exec_err)

    except Exception as e:
        logger.error(f"Script build/execution failure: {e}")
        return None, str(e)


# ---------- Background Worker ----------
def run_worker(initial_url: str):
    logger.info(f"Background worker started for {initial_url}")
    current_url = initial_url

    while True:

        # PHASE 1: SCRAPE
        try:
            if STUDENT_EMAIL and "email=" not in current_url:
                sep = "&" if "?" in current_url else "?"
                current_url = f"{current_url}{sep}email={STUDENT_EMAIL}"

            scraped = extract_webpage_recursive(current_url, max_depth=1)
            logger.info(f"Scraped pages: {len(scraped['pages'])}")
        except Exception as e:
            logger.error(f"Scraping error: {e}")
            return

        # PHASE 1: EXTRACT FACTS
        facts = identify_quiz_components(scraped["pages"])

        # PHASE 2: GENERATE + EXECUTE
        answer, last_error = generate_and_execute(facts, current_url)

        # PHASE 3: SUBMIT + RETRY POLICY
        MAX_EVAL_RETRIES = 2
        eval_attempt = 0
        moved_to_next = False

        while True:
            eval_attempt += 1
            resp = submit_to_evaluator(current_url, answer)

            if not resp or "correct" not in resp or "url" not in resp:
                logger.info("Invalid evaluator response. Stopping.")
                return

            correct = bool(resp.get("correct"))
            next_url = resp.get("url")
            reason = resp.get("reason")

            # ------------------------------------
            logger.info(f"Evaluator feedback reason: {reason!r}")
            # ------------------------------------

            # ------------------------------------------------------
            # NEW: Log failed response to file if incorrect
            # ------------------------------------------------------
            if not correct:     # <<< NEW >>>
                record_failed_submission(
                    url=current_url,
                    answer=answer,
                    reason=reason,
                    attempt=eval_attempt,
                )
            # ------------------------------------------------------

            # Case A
            if not next_url and correct:
                logger.info("Evaluator indicates correct and no next URL. Stopping worker.")
                return

            # Case B
            if not next_url and not correct:
                if eval_attempt <= MAX_EVAL_RETRIES:
                    logger.info(
                        "Evaluator returned incorrect and no next URL. Reattempting (%d/%d)...",
                        eval_attempt, MAX_EVAL_RETRIES,
                    )
                    answer, last_error = generate_and_execute(
                        facts, current_url, prior_error=reason, prompt_attempt_start=1
                    )
                    continue
                else:
                    logger.info("Max retries exhausted for this question (no next URL). Stopping worker.")
                    return

            # Case C
            if next_url and not correct:
                if eval_attempt <= MAX_EVAL_RETRIES:
                    logger.info(
                        "Evaluator returned incorrect but provided next URL. Will retry (%d/%d) and then move on.",
                        eval_attempt, MAX_EVAL_RETRIES,
                    )
                    answer, last_error = generate_and_execute(
                        facts, current_url, prior_error=reason, prompt_attempt_start=1
                    )
                    continue
                else:
                    logger.info("Retries exhausted; moving on to next URL despite incorrect mark.")
                    current_url = next_url
                    moved_to_next = True
                    break

            # Case D
            if next_url and correct:
                current_url = next_url
                moved_to_next = True
                logger.info(f"Moving to next URL: {current_url}")
                break

            # Safety fallback
            logger.info("Unhandled evaluator response shape; stopping.")
            return

        if moved_to_next:
            continue
        else:
            return


# ---------- Endpoint ----------
@app.post("/phase1")
def phase1(req: Phase1Request, background: BackgroundTasks):
    if req.secret != STUDENT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    background.add_task(run_worker, req.url)
    return {"status": "worker started", "initial_url": req.url}
