# app/phase2_executor.py
import subprocess
import tempfile
import json
import sys
import traceback
import logging
import time
from pathlib import Path

logger = logging.getLogger("phase2.executor")

MAX_EXEC_RETRIES = 3


def _run_once(script: str):
    """Execute script once and return (ok, result, error_msg)."""

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "solution.py"
            script_path.write_text(script, encoding="utf-8")

            proc = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            out, err = proc.communicate(timeout=40)

            if proc.returncode != 0:
                return False, None, err

            out = out.strip().split("\n")[-1]

            try:
                parsed = json.loads(out)
            except Exception as e:
                return False, None, f"JSON decode failed: {e}\nRAW:\n{out}"

            return True, parsed, None

    except Exception as e:
        return False, None, traceback.format_exc()


def execute_phase2_script(script: str):
    """
    Run the script with retry logic.
    """
    logger.info("*"*20)
    logger.info("SCript:\n%s", script)
    logger.info("*"*20)
    for attempt in range(1, MAX_EXEC_RETRIES + 1):
        ok, result, error = _run_once(script)

        if ok:
            return {"status": "ok", "json": result}

        logger.warning(f"[executor] Script attempt {attempt}/{MAX_EXEC_RETRIES} failed: {error}")
        

        time.sleep(1)

    return {"status": "error", "error": error, "script": script}
