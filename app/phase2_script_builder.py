# app/phase2_script_builder.py
import json
import logging
import re

logger = logging.getLogger("phase2.builder")


class Phase2ScriptBuilder:

    @staticmethod
    def make_prompt(facts: dict, start_url: str) -> str:
        """
        Public prompt builder.
        """
        return Phase2ScriptBuilder._make_prompt(facts, start_url)

    # ------------------------------------
    # LLM PROMPT
    # ------------------------------------
    @staticmethod
    def _make_prompt(facts: dict, start_url: str) -> str:
        return f"""
You are an expert at solving multi-page quiz questions.

You are given Phase-1 scraped data that contains:
- pages: a list of pages, where each page has:
    * url: page URL
    * contents: readable text extracted from the page
    * attachments: metadata-only for CSV/PDF/audio/image files

Your task:
1. Read ALL pages.
2. Understand the question.
3. If attachments exist, load and process them using Python.
4. Write RAW PYTHON CODE ONLY (no markdown).
5. Your code must set:

    final_answer = <value>

Rules:
- Do NOT submit to evaluator.
- You may use: requests, pandas, bs4, base64, PyPDF2, audio loaders, pillow, numpy etc.
- To load attachments, iterate over phase1_facts["pages"][i]["attachments"].
- If no question is found, set: final_answer = "ok".


IMPORTANT STRICT RULES:
1. NEVER print, dump or return full CSV/PDF/TXT file contents.
   Only compute the final required number/string.

2. If a CSV is attached, load it only if needed and compute ONLY the required
   summary value (sum, count, max, lookup, etc.).

3. Do NOT set final_answer = df.to_string() or equivalent.
   final_answer must be a single scalar answer.

4. Output ONLY JSON:
   {{"answer": <value>}}
   No logs, no prints, no extra text.

5. Do NOT echo contents of attachments.
   Do NOT echo entire pages or large text.

6. Your script MUST strictly follow:
   final_answer = <scalar>
  
Return ONLY raw python code.
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
