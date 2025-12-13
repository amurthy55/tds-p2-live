# app/solver.py
import os
import json
import tempfile
import subprocess
import sys
import logging
from typing import Optional

logger = logging.getLogger("app.solver")


# -----------------------------------------------------
# CLEAN LLM PYTHON — Remove markdown/code fences
# -----------------------------------------------------
def sanitize_llm_python(raw: str) -> str:
    """
    Remove ```python ... ``` or ``` ... ``` blocks.
    Ensure only raw executable Python remains.
    """
    if "```" not in raw:
        return raw.strip()

    cleaned = []
    inside_block = False

    for line in raw.splitlines():
        if line.strip().startswith("```"):
            inside_block = not inside_block
            continue
        if not inside_block:
            cleaned.append(line)

    return "\n".join(cleaned).strip()


# -----------------------------------------------------
# RUN SCRIPT SAFELY
# -----------------------------------------------------
def run_script(python_body: str) -> Optional[dict]:
    """
    Executes python_body inside a temp .py file.
    Returns parsed JSON dict or None on failure.
    """
    python_body = sanitize_llm_python(python_body)

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        script_path = f.name
        f.write(python_body)

    logger.debug("Executing temp script: %s", script_path)

    # inherit full environment: PATH, PYTHONPATH, venv, etc.
    env = os.environ.copy()
    python_exe = sys.executable  # use same interpreter as FastAPI

    try:
        proc = subprocess.Popen(
            [python_exe, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )
        stdout, stderr = proc.communicate(timeout=40)

        if stderr.strip():
            logger.error("Script error:\n%s", stderr)

        stdout = stdout.strip()
        logger.debug("Raw script stdout: %s", stdout)

        # attempt to parse JSON
        try:
            return json.loads(stdout)
        except Exception:
            logger.error("Invalid script JSON output: %s", stdout)
            return None

    except Exception as e:
        logger.error("Execution failure: %s", e)
        return None

    finally:
        try:
            os.remove(script_path)
        except Exception:
            pass
