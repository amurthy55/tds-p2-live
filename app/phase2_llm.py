# app/phase2_llm.py
import logging
from openai import OpenAI
from app.config import OPENAI_API_KEY

logger = logging.getLogger("phase2.llm")

client = OpenAI(api_key=OPENAI_API_KEY)
# def phase2_llm(prompt: str) -> str:
#     """
#     Calls OpenAI Responses API with strict settings.
#     Retries prompt 3 times if the LLM output violates the required format.
#     """

#     for attempt in range(1, 4):
#         logger.info(f"Phase2: calling LLM (prompt attempt {attempt}/3)")

#         resp = client.responses.create(
#             model="gpt-4o-mini",
#             input=prompt,
#             max_output_tokens=800
#         )

#         output = resp.output_text

#         if output and "#PYTHON_START" in output and "#PYTHON_END" in output:
#             return output

#         logger.warning("LLM returned invalid content — retrying.")

#     raise RuntimeError("LLM failed to produce valid #PYTHON_START/#PYTHON_END output after 3 attempts.")
BAD_PATTERNS = [
    "read_html",     # Cannot parse PDFs
    "html5lib",      # HTML parser hallucination
    "lxml",          # HTML parser
    "camelot",       # Not installed
    "tabula",        # Requires Java
    "pdfplumber",    # Not installed
    "fitz", "PyMuPDF"  # Not installed
]

def phase2_llm(prompt: str) -> str:
    """
    Calls OpenAI API with guardrails:
    - Ensures #PYTHON_START / #PYTHON_END exist
    - Rejects code using unsupported PDF/HTML libraries
    - Retries automatically up to 3 times
    """
    for attempt in range(1, 4):
        logger.info(f"Phase2: calling LLM (prompt attempt {attempt}/3)")

        try:
            resp = client.responses.create(
                model="gpt-4o-mini",
                input=prompt,
                max_output_tokens=1000,
            )
        except Exception as e:
            logger.warning(f"OpenAI call failed attempt {attempt}/3: {e}")
            continue

        output = resp.output_text or ""

        # Check for correct markers
        if "#PYTHON_START" not in output or "#PYTHON_END" not in output:
            logger.warning("LLM output missing python markers — retrying.")
            continue

        # Reject bad libraries / wrong PDF logic
        if any(bad in output for bad in BAD_PATTERNS):
            logger.warning("LLM generated invalid PDF/HTML code — retrying.")
            continue

        return output

    raise RuntimeError("LLM failed to produce valid Python block after 3 attempts.")

