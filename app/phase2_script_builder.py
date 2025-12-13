# app/phase2_script_builder.py
import re
import json
import logging
from app.config import STUDENT_EMAIL

logger = logging.getLogger("phase2.script_builder")


def _make_prompt(facts, current_url, previous_error=None, attempt_number=0):
    """
    Strict code-only prompt. Model MUST output:

    #PYTHON_START
    final_answer = ...
    #PYTHON_END
    """

    base_prompt = f"""
You produce ONLY Python code inside:
#PYTHON_START
#PYTHON_END

================= ABSOLUTE RULES (DO NOT BREAK) =================
1. Output ONLY Python — NO text, NO explanations, NO markdown, NO backticks.
2. Code MUST define: final_answer = <value>
3. NOTHING is allowed outside #PYTHON_START / #PYTHON_END.
4. Do NOT fetch network URLs.
5. Use ONLY provided facts & local attachments.
6. Do NOT print anything except the final JSON stub (already wrapped).

7. final_answer must NEVER be:
   - None
   - null
   - empty string
   - empty list
   - empty dict

   If you cannot determine a correct meaningful answer, set:
       final_answer = "pass"

================= FILE TYPE RULES (MANDATORY) =================

CSV FILES:
- ALWAYS load using pandas.read_csv(<local_path>).
- NEVER assume column names.
- ALWAYS inspect real columns first using:
      data.columns.tolist()
- Normalize column names ONLY by:
      data.columns = [str(c).strip().lower().replace(" ", "_") for c in data.columns]
- After normalization, REQUIRED logical fields are:
      id, name, joined, value
- If exact names do not exist, infer them by closest match
  (case, substring, or position-based).
- NEVER invent data.
- NEVER drop rows unless explicitly instructed.
- Sort ONLY after verifying the sort column exists.
- Output MUST be a JSON ARRAY (not wrapped in another object).

PDF FILES:
- Use PyPDF2.PdfReader ONLY.
- Extract all text, then parse numeric values using regex.
- Compute exact totals as instructed.

IMAGE FILES:
- Use PIL.Image.
- Convert to RGB before analysis.

AUDIO FILES:
- Use ONLY provided transcription in FACTS.
- Do NOT attempt re-transcription.

ZIP FILES:
- Use zipfile module only.
- Parse files exactly as instructed.

JSON / API RESPONSE FILES:
- If any page contents start with '{{' or '[' and are valid JSON,
  you MUST parse them using json.loads().
- NEVER assume data is missing if JSON is present in FACTS.
- For GitHub tree tasks:
    - Use the provided JSON data ONLY.
    - Treat it as an API response already fetched.
    - Count items by inspecting JSON fields (e.g., tree paths).
    - Apply pathPrefix and extension filters exactly as specified.
    - NEVER say data is unavailable if JSON is provided.

================= LOGIC RULES (MANDATORY) =================

- FIRST understand what the evaluator expects as the *exact answer format*.
- If the task asks to "submit the command string", "submit the exact command",
  or similar wording, then:
      final_answer MUST be a plain string.
      Do NOT wrap it in JSON, dicts, or lists.
- Do NOT return explanations.
- Do NOT repeat a previously incorrect approach.


- Difficulty awareness:
    - Difficulty 1–2: incorrect answers may still advance.
    - Difficulty 3+: next URL is revealed ONLY on correct answer.
      Do NOT use "pass" if sufficient data is available.

If PREVIOUS_ERROR is provided:
- It is evaluator feedback.
- You MUST change your logic to address it.
- NEVER repeat the same mistake.

================= FACTS PROVIDED =================
{json.dumps(facts, indent=2)}

================= CONTEXT =================
CURRENT_URL: {current_url}
STUDENT_EMAIL: {facts.get("student_email")}
EMAIL_LENGTH: {len(facts.get("student_email") or "")}
ATTEMPT_NUMBER: {attempt_number}
"""

    if previous_error:
        base_prompt += f"""
================= PREVIOUS_ERROR (Evaluator Feedback) =================
{previous_error}
"""

    base_prompt += """
Return ONLY the Python code between the markers.
ABSOLUTELY NOTHING ELSE.
"""

    return base_prompt




def extract_llm_code(raw: str) -> str:
    """
    Extracts the code inside #PYTHON_START ... #PYTHON_END
    """

    m = re.search(r"#PYTHON_START(.*?)#PYTHON_END", raw, re.DOTALL)
    if not m:
        raise ValueError("LLM did not return a #PYTHON_START/#PYTHON_END block.")

    body = m.group(1).strip()

    # Reject conversational spills
    banned = ["```", "Hello", "hi ", "assist", "message", "empty"]
    if any(b in body for b in banned):
        raise ValueError("LLM output contained conversational or invalid text.")

    return body


import re
import json
import logging
import pprint   # <--- add this

logger = logging.getLogger("phase2.script_builder")

# ... keep existing functions ...

def build_script(facts, llm_raw, start_url):
    """
    Wraps extracted safe LLM python block into full executable code.
    """

    code = extract_llm_code(llm_raw)

    # Use pprint.pformat to get a Python-valid representation (None/True/False, not null/true/false)
    facts_py = pprint.pformat(facts)

    wrapper = f"""
import json
import numpy as np
import pandas as pd

phase1_facts = {facts_py}
current_url = {json.dumps(start_url)}

# === LLM CODE ===
{code}
# === END LLM CODE ===

try:
    final_answer
except NameError:
    raise RuntimeError("LLM did not set final_answer")

# cast numpy/pandas scalars to python
try:
    if hasattr(final_answer, "item"):
        final_answer = final_answer.item()
except:
    pass

print(json.dumps({{"answer": final_answer}}))
"""
    return wrapper
