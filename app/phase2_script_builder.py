# app/phase2_script_builder.py
import json
import logging
import re

logger = logging.getLogger("phase2.builder")


class Phase2ScriptBuilder:

    @staticmethod
    def _make_prompt(facts: dict, start_url: str) -> str:
        return f"""
    You are an expert at solving multi-page automated quiz questions.

    You are given structured Phase-1 data with:
    - pages: list of pages
    * url: page URL
    * contents: visible extracted text
    * attachments: metadata for CSV / PDF / audio / images (local_path, size, content_type)

    Your job:
    1. Read ALL pages.
    2. Carefully inspect **all attachments first**.
    3. If attachments include CSV, PDF, image, audio:
    - Load them **using attachment["local_path"] ONLY**.
    - NEVER re-download from source_url.
    - For audio: you MAY use Whisper or torchaudio/librosa.
    - For PDFs: you MAY use PyPDF2 or pdfplumber.
    - For images: Pillow.
    4. Understand what the question is asking.
    5. Write RAW PYTHON CODE ONLY.
    6. Your code MUST set:

        final_answer = <value>

    STRICT RULES:
    - DO NOT print anything.
    - DO NOT output JSON.
    - DO NOT call print().
    - DO NOT return values.
    - DO NOT write markdown.
    - Your ONLY job is computing final_answer.
    - final_answer MUST be a plain Python scalar (int, float, str, bool).

    - Do not echo or dump CSV/PDF/text contents.
    - Do not hallucinate any columns, keys, fields.
    - Inspect actual CSV using pandas.read_csv(local_path).
    - Do not assume column names unless verified.
    - If task involves summation/filtering, use the first column explicitly.

    - If no question can be inferred:
        final_answer = "ok"

    You have access to these installed libraries:
    {json.dumps([
        "requests", "pandas", "numpy", "bs4", "PyPDF2",
        "pdfplumber", "openai_whisper", "torch", "torchaudio",
        "Pillow", "librosa", "soundfile",
        "matplotlib", "plotly", "networkx", "geopandas"
    ], indent=2)}

    Return only raw python code.

    Parsed facts:
    {json.dumps(facts, indent=2)}

    Start URL: {start_url}
    """


    # ------------------------------------
    # SCRIPT HEADER + FOOTER
    # ------------------------------------
    @staticmethod
    def build_script(facts: dict, llm_body: str, start_url: str) -> str:
        llm_body = Phase2ScriptBuilder._patch(llm_body)

        header = (
    "import json\n"
    "import requests\n"
    "import time\n"
    "import base64\n"
    "import tempfile\n"
    "from pathlib import Path\n"
    "from bs4 import BeautifulSoup\n"
    "import pandas as pd\n"
    "import numpy as np\n"
    "import PyPDF2\n"
    "import pdfplumber\n"
    "import torch\n"
    "import torchaudio\n"
    "import librosa\n"
    "import soundfile as sf\n"
    "from PIL import Image\n"
    "import sys, io\n\n"
    "old_stdout = sys.stdout\n"
    "sys.stdout = io.StringIO()\n\n"
    f"phase1_facts = {json.dumps(facts)}\n"
    f"current_url = {json.dumps(start_url)}\n\n"
    "# === BEGIN LLM CODE ===\n"
)

        footer = (
    "\n# === END LLM CODE ===\n\n"
    "captured = sys.stdout.getvalue()\n"
    "sys.stdout = old_stdout\n\n"
    "try:\n"
    "    final_answer\n"
    "except NameError:\n"
    "    raise RuntimeError('LLM did not set final_answer')\n\n"
    "# Convert numpy/pandas scalars\n"
    "import numpy as _np\n"
    "if isinstance(final_answer, _np.generic):\n"
    "    final_answer = final_answer.item()\n\n"
    "print(json.dumps({\"answer\": final_answer}))\n"
)


        return header + llm_body + footer

    # ------------------------------------
    # LLM patching
    # ------------------------------------
    @staticmethod
    def _patch(code: str) -> str:
        code = code.replace("\r", "")
        code = re.sub(r"pd\.compat\.StringIO", "io.StringIO", code)
        return code
