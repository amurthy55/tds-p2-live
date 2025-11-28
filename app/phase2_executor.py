# app/phase2_executor.py
import subprocess
import tempfile
import json
import os
import uuid
import sys
import logging
from pathlib import Path

logger = logging.getLogger("phase2.executor")


def execute_phase2_script(code: str, timeout_sec: int = 25):
    """
    Executes the generated script in isolation.
    Captures stdout/stderr, returns:
        { "status": "ok", "raw_stdout": "...", "json": {...} }
        or
        { "status": "error", "error": "...", "stderr": "...", "raw_stdout": "..." }
    """

    temp_dir = Path(tempfile.gettempdir()) / f"phase2exec_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    script_path = temp_dir / "solution.py"

    script_path.write_text(code, encoding="utf-8")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout_sec
        )
    except subprocess.TimeoutExpired:
        logger.warning("Phase-2 script timed out")
        return {"status": "error", "error": f"timeout {timeout_sec}s"}

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode != 0:
        logger.warning("Script returned non-zero: %s", stderr)
        return {
            "status": "error",
            "error": stderr,
            "raw_stdout": stdout,
            "script": code
        }

    # Try JSON decode
    try:
        parsed = json.loads(stdout)
        return {
            "status": "ok",
            "raw_stdout": stdout,
            "json": parsed,
            "script": code
        }
    except Exception:
        return {
            "status": "error",
            "error": "stdout_not_json",
            "raw_stdout": stdout,
            "stderr": stderr,
            "script": code
        }
