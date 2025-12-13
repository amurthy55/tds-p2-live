# app/phase1_extractor.py
import logging
import re
import os
import whisper

logger = logging.getLogger("phase1.extractor")

# Load whisper once (if available)
try:
    _whisper_model = whisper.load_model("base")
except Exception:
    logger.warning("Whisper could not be loaded; audio transcription disabled.")
    _whisper_model = None


def _transcribe_audio(local_path: str) -> str:
    """
    Transcribe audio file using Whisper, but if Whisper cannot load,
    return empty string so LLM handles transcription itself.
    """
    if not local_path or not os.path.exists(local_path):
        return ""

    if _whisper_model is None:
        return ""

    try:
        result = _whisper_model.transcribe(local_path)
        return result.get("text", "").strip()
    except Exception as e:
        logger.error(f"Audio transcription failed for {local_path}: {e}")
        return ""


def _clean_contents(text: str) -> str:
    """
    Clean extracted HTML text:
    - Remove huge digit blocks
    - Collapse whitespace
    - Truncate long text
    """
    if not text:
        return ""

    text = re.sub(r"(?:\d+\s*){50,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > 3000:
        text = text[:3000] + " ...[truncated]..."

    return text


def _extract_inline_js(page_html: str) -> str:
    """
    Extract inline <script> code while ignoring external scripts.
    """
    if not page_html:
        return ""

    try:
        from bs4 import BeautifulSoup
    except Exception:
        return ""

    soup = BeautifulSoup(page_html, "html.parser")
    scripts = []

    for tag in soup.find_all("script"):
        if tag.get("src"):  # skip external JS
            continue
        code = tag.string
        if code and code.strip():
            scripts.append(code.strip())

    return "\n\n".join(scripts) if scripts else ""


def identify_quiz_components(raw_pages: list) -> dict:
    """
    SAFE FIXED VERSION:
    - Clean text
    - Extract inline JS
    - Transcribe audio (but do NOT pass entire audio files)
    - Preserve all required metadata fields for Phase 2
    - Correctly surface github_tree_stats (once, top-level)
    """
    structured_pages = []
    attachments_all = []
    referenced_urls = set()
    found_numbers = set()
    detected_emails = set()

    student_email = None
    github_tree_stats = None  # <-- FIX: collect once

    # ----------------------------
    # First pass: detect GH stats
    # ----------------------------
    for p in raw_pages:
        if "github_tree_stats" in p and p["github_tree_stats"]:
            github_tree_stats = p["github_tree_stats"]
            break

    # ----------------------------
    # Main per-page processing
    # ----------------------------
    for p in raw_pages:
        url = p.get("url", "")
        contents_raw = p.get("text", "") or p.get("contents", "") or ""
        html_raw = p.get("html", "") or ""
        attachments = p.get("attachments", [])

        cleaned_text = _clean_contents(contents_raw)

        # Inline JS
        inline_js = _extract_inline_js(html_raw)
        if inline_js:
            cleaned_text += f"\n\n[Javascript Extracted]:\n{inline_js}\n"

        # Audio transcription
        for att in attachments:
            ctype = att.get("content_type", "")
            if ctype.startswith("audio/"):
                transcript = _transcribe_audio(att.get("local_path"))
                if transcript:
                    cleaned_text += (
                        f"\n\n[Audio transcription ({att.get('filename')})]:\n"
                        f"{transcript}\n"
                    )

        # Numbers
        for n in re.findall(r"\d+", cleaned_text):
            try:
                found_numbers.add(int(n))
            except Exception:
                pass

        # Emails
        for email in re.findall(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            cleaned_text + " " + url,
        ):
            detected_emails.add(email)
            if "iitm.ac.in" in email:
                student_email = email

        # URLs
        for u in re.findall(r"https?://\S+", cleaned_text):
            referenced_urls.add(u)

        attachments_all.extend(attachments)

        structured_pages.append({
            "url": url,
            "contents": cleaned_text,
            "attachments": attachments,
        })

    # ----------------------------
    # Final facts object
    # ----------------------------
    return {
        "pages": structured_pages,
        "attachments": attachments_all,
        "found_numbers": sorted(found_numbers),
        "referenced_urls": sorted(referenced_urls),
        "detected_emails": sorted(detected_emails),
        "student_email": student_email,
        "github_tree_stats": github_tree_stats,  # ✅ FIXED placement
        # evaluator_feedback injected later by main.py
    }
