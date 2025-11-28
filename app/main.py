# app/main.py
import os
import json
import logging
import traceback
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

from app.scrapers import extract_webpage_recursive
from app.phase1_extractor import identify_quiz_components
from app.phase2_llm import phase2_llm
from app.phase2_script_builder import Phase2ScriptBuilder
from app.phase2_executor import execute_phase2_script
from app.config import STUDENT_SECRET, STUDENT_EMAIL

logger = logging.getLogger("app.main")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
app = FastAPI()


# -----------------------------------------------------
# Pydantic model for Phase-1 trigger
# -----------------------------------------------------
class Phase1Request(BaseModel):
    url: str


# -----------------------------------------------------
# Evaluator submit helper
# -----------------------------------------------------
def submit_to_evaluator(url: str, answer):
    """
    Submits the final answer to evaluator service.
    """
    import requests

    payload = {
        "email": STUDENT_EMAIL,
        "secret": STUDENT_SECRET,
        "url": url,
        "answer": answer,
    }

    logger.info("Submitting evaluator payload: %s", payload)

    try:
        resp = requests.post(
            "https://tds-llm-analysis.s-anand.net/submit",
            json=payload,
            timeout=20,
        )
        text = resp.text.strip()

        try:
            j = resp.json()
            logger.info("Evaluator response: %s", j)
            return j
        except:
            logger.warning("Evaluator returned non-JSON response:\n%s", text)
            return {"correct": False, "url": None}

    except Exception as e:
        logger.error("Evaluator submit failed: %s", e)
        return {"correct": False, "url": None}


# -----------------------------------------------------
# Phase-2 Worker
# -----------------------------------------------------
def run_worker(initial_url: str):
    """
    Runs through the multi-step quiz until evaluator stops giving next URL.
    """
    logger.info("Background worker started for %s", initial_url)
    current_url = initial_url

    while True:
        logger.info("Phase2 iteration for %s", current_url)

        # -------------------------------
        # PHASE-1: SCRAPE
        # -------------------------------
        try:
            scraped = extract_webpage_recursive(current_url, max_depth=1)
            logger.info("Scraped pages: %d", len(scraped["pages"]))
            # logger.info(scraped)
        except Exception as e:
            logger.error("Error scraping %s: %s", current_url, e)
            logger.error(traceback.format_exc())
            return

        # -------------------------------
        # PHASE-1: DETECT FACTS
        # -------------------------------
        facts = identify_quiz_components(scraped['pages'])
        logger.info("Phase-1 facts: %s", facts)

        # -------------------------------
        # PHASE-2 LLM: Build script
        # -------------------------------
        prompt = Phase2ScriptBuilder.make_prompt(facts, current_url)
        logger.info("Phase2: calling LLM")

        llm_raw = phase2_llm(prompt)
        full_script = Phase2ScriptBuilder.build_script(
            facts=facts, llm_body=llm_raw, start_url=current_url
        )
        logger.info("FULLSCRIPT")
        logger.info(full_script)
        # logger.info("*"*12,"FULLSCRIPT","*"*12)

        # -------------------------------
        # PHASE-2 EXECUTE SCRIPT
        # -------------------------------
        result = execute_phase2_script(full_script)

        if result.get("status") != "ok":
            logger.error("Script error: %s", result)
            answer = None
        else:
            answer = result["json"]["answer"]

        logger.info("Phase-2 result: %s", {"answer": answer})

        # -------------------------------
        # PHASE-3: SUBMIT TO EVALUATOR
        # -------------------------------
        evaluator_resp = submit_to_evaluator(current_url, answer)

        next_url = evaluator_resp.get("url")
        if next_url:
            logger.info("Evaluator gave next URL: %s", next_url)
            current_url = next_url
            continue

        # No next URL — this really is the end
        logger.info("No next URL; finishing worker.")
        return


        current_url = next_url


# -----------------------------------------------------
# FastAPI Phase-1 endpoint
# -----------------------------------------------------
@app.post("/phase1")
def phase1(req: Phase1Request, background: BackgroundTasks):
    logger.info("Phase1 triggered for %s", req.url)
    background.add_task(run_worker, req.url)
    return {"status": "worker started", "initial_url": req.url}
