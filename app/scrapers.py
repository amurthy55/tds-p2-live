# app/scrapers.py
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import mimetypes
import os
import tempfile

logger = logging.getLogger("app.scrapers")

# Attachment content-type families we treat as attachments (don't dump as page contents)
_ATTACHMENT_CONTENT_TYPES = (
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/pdf",
    "application/zip",
    "audio/ogg",
    "audio/opus",
    "audio/wav",
    "audio/mpeg",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
)

# Common file extensions we treat as attachments (fallback)
_ATTACHMENT_EXTS = (".csv", ".pdf", ".zip", ".opus", ".ogg", ".wav", ".mp3", ".png", ".jpg", ".jpeg", ".gif")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _static_fetch_raw(url: str, timeout: int = 10):
    """
    Try to fetch the URL and return (status_code, content, content_type, headers).
    content is bytes (raw). Caller can decode if needed.
    """
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        return resp.status_code, resp.content, resp.headers.get("Content-Type", ""), resp.headers
    except Exception as e:
        logger.warning("Static fetch failed for %s: %s", url, e)
        return None, None, None, {}


def _playwright_fetch(url: str):
    """
    JS render using Playwright (synchronous API).
    Returns HTML text (str) or None.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        logger.error("Playwright failed for %s: %s", url, e)
        return None


def _download_attachment(url: str, content_bytes: bytes = None) -> dict:
    """
    Download a file and return metadata (NOT content).
    If content_bytes is provided, write it to disk (no re-download).
    """
    try:
        if content_bytes is None:
            resp = requests.get(url, timeout=15, allow_redirects=True)
            if resp.status_code != 200:
                logger.warning("Attachment fetch returned %s for %s", resp.status_code, url)
                return None
            content_bytes = resp.content
            ctype = resp.headers.get("Content-Type", None)
        else:
            # guess content-type from url if not provided
            ctype = None

        # filename
        fname = url.split("/")[-1] or "file.bin"

        # try Content-Disposition (not exhaustive)
        # but keep fname fallback simple
        tmpdir = tempfile.gettempdir()
        # sanitize fname a bit
        fname_safe = fname.replace("/", "_").replace("\\", "_")
        local_path = os.path.join(tmpdir, f"tds_phase1_{fname_safe}")

        # write
        with open(local_path, "wb") as f:
            f.write(content_bytes)

        # guess content_type if not provided
        if not ctype:
            ctype = mimetypes.guess_type(local_path)[0] or "application/octet-stream"

        return {
            "id": os.path.basename(local_path),
            "filename": fname_safe,
            "content_type": ctype,
            "size_bytes": len(content_bytes),
            "source_url": url,
            "local_path": local_path,
        }
    except Exception as e:
        logger.error("Attachment download failed for %s: %s", url, e)
        return None


# ------------------------------------------------------------
# Extract single page (static + JS fallback)
# ------------------------------------------------------------
def extract_single_page(url: str) -> dict:
    """
    Return:
    {
      url, html, text, links, attachments
    }
    Notes:
      - If URL itself is an attachment (CSV/PDF/audio/image/zip) we will download
        it and return empty html/text and attachments metadata.
      - Links list excludes attachment links (they are placed in `attachments`).
    """
    logger.info("Fetching page %s", url)

    # 1) static fetch raw bytes (to inspect headers)
    status, raw_bytes, content_type_header, headers = _static_fetch_raw(url)

    html = ""
    text = ""
    links = []
    attachments = []

    # Normalize content type
    content_type = (content_type_header or "").split(";")[0].strip().lower()

    # If content-type is a known attachment, write file and return minimal page
    if status == 200 and content_type in _ATTACHMENT_CONTENT_TYPES:
        logger.info("URL %s appears to be attachment content-type=%s; saving as attachment", url, content_type)
        meta = _download_attachment(url, content_bytes=raw_bytes)
        if meta:
            attachments.append(meta)
        return {
            "url": url,
            "html": "",
            "text": "",
            "links": [],
            "attachments": attachments,
        }

    # Otherwise, try to decode content to text (html)
    if status == 200 and raw_bytes is not None:
        try:
            html_text = raw_bytes.decode("utf-8", errors="replace")
        except Exception:
            html_text = ""
    else:
        html_text = ""

    # Heuristic: if html is tiny or has dynamic JS, use Playwright
    needs_js = False
    if not html_text or len(html_text.strip()) < 200:
        needs_js = True
    if "<script" in html_text.lower() and "innerhtml" in html_text.lower():
        needs_js = True

    if needs_js:
        logger.info("Static too small -> attempting Playwright for %s", url)
        pw_html = _playwright_fetch(url)
        if pw_html:
            html_text = pw_html

    if not html_text:
        html_text = ""

    soup = BeautifulSoup(html_text, "html.parser")

    # Visible text (strip excessive whitespace)
    text = soup.get_text("\n", strip=True) or ""

    # Collect links but skip attachment links
    for a in soup.find_all("a", href=True):
        abs_url = urljoin(url, a["href"])
        lower = abs_url.lower()
        if any(lower.endswith(ext) for ext in _ATTACHMENT_EXTS):
            # treat as attachment (will be handled below)
            continue
        links.append(abs_url)

    # Also check for src on audio / img / source tags and treat them as attachments
    media_sources = set()
    for tag in soup.find_all(["audio", "source", "img", "link"]):
        src = None
        if tag.name == "link" and tag.get("href"):
            src = urljoin(url, tag.get("href"))
        elif tag.get("src"):
            src = urljoin(url, tag.get("src"))

        if src:
            lower = src.lower()
            if any(lower.endswith(ext) for ext in _ATTACHMENT_EXTS) or any(ct in lower for ct in ("/audio", "/image", ".csv", ".pdf", ".zip")):
                media_sources.add(src)

    # Find attachment links from <a> tags as well (we skipped adding to links)
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        lower = href.lower()
        if any(lower.endswith(ext) for ext in _ATTACHMENT_EXTS) or any(ct in lower for ct in ("/audio", "/image", ".csv", ".pdf", ".zip")):
            media_sources.add(href)

    # Download (or write) attachments (but do not re-download duplicates)
    seen_att_urls = set()
    for att_url in media_sources:
        if att_url in seen_att_urls:
            continue
        seen_att_urls.add(att_url)
        # Try a light HEAD or GET to fetch bytes (so we don't rely on subsequent crawler to fetch as page)
        try:
            st, content_bytes, ctype_header, hdrs = _static_fetch_raw(att_url)
            # if got bytes and it looks like attachment, write it using _download_attachment (pass bytes)
            meta = _download_attachment(att_url, content_bytes=content_bytes) if content_bytes else _download_attachment(att_url)
            if meta:
                attachments.append(meta)
        except Exception as e:
            logger.warning("Failed to fetch attachment %s : %s", att_url, e)

    return {
        "url": url,
        "html": html_text,
        "text": text,
        "links": links,
        "attachments": attachments,
    }
import re
import json
import logging
import httpx

logger = logging.getLogger("app.scrapers")

GHTREE_REGEX = re.compile(r'"owner":\s*"([^"]+)"\s*,\s*"repo":\s*"([^"]+)"\s*,\s*"sha":\s*"([^"]+)"')

def _maybe_fetch_github_tree(page_html_or_json, collected_pages):
    """
    Detect GitHub tree specification, fetch recursive tree,
    and compute deterministic stats for downstream use.
    """
    # Try to parse JSON - handle whitespace and cleanup
    page_text = str(page_html_or_json).strip()
    
    try:
        data = json.loads(page_text)
    except Exception as e:
        # Silent return if not valid JSON (most pages aren't)
        return

    owner = data.get("owner")
    repo = data.get("repo")
    sha = data.get("sha")
    path_prefix = data.get("pathPrefix", "")
    extension = data.get("extension", "")

    if not (owner and repo and sha):
        return

    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{sha}?recursive=1"
    logger.info(f"[GH-TREE] Detected tree params - fetching: {api_url}")

    try:
        with httpx.Client(timeout=15) as client:
            r = client.get(api_url)
            r.raise_for_status()
            tree_json = r.json()
    except Exception as e:
        logger.error(f"[GH-TREE] Could not fetch tree: {e}")
        return

    # ----------------------------
    # COMPUTE STATS (KEY FIX)
    # ----------------------------
    count = 0
    for item in tree_json.get("tree", []):
        path = item.get("path", "")
        if not isinstance(path, str):
            continue
        if path_prefix and not path.startswith(path_prefix):
            continue
        if extension and not path.endswith(extension):
            continue
        count += 1

    github_tree_stats = {
        "owner": owner,
        "repo": repo,
        "sha": sha,
        "path_prefix": path_prefix,
        "extension": extension,
        "md_count": count,
    }

    # Attach BOTH raw tree + computed stats
    collected_pages.append({
        "url": api_url,
        "contents": json.dumps(tree_json),
        "attachments": [],
        "github_tree_stats": github_tree_stats,
    })



def parse_github_tree_and_count(tree_json_text, path_prefix, extension):
    """
    Deterministically counts files in a GitHub tree JSON.
    """
    try:
        data = json.loads(tree_json_text)
    except Exception:
        return None

    tree = data.get("tree", [])
    if not isinstance(tree, list):
        return None

    count = 0
    for item in tree:
        path = item.get("path")
        if isinstance(path, str) and path.startswith(path_prefix) and path.endswith(extension):
            count += 1

    return count

# ------------------------------------------------------------
# Recursive extraction (depth 1)
# ------------------------------------------------------------
# ------------------------------------------------------------
# Recursive extraction (depth up to max_depth)
# ------------------------------------------------------------
def extract_webpage_recursive(url: str, max_depth=4):
    """
    Returns:
    {
       "pages": [ {single page}, ... ]
    }

    Notes:
      - attachments discovered on pages are downloaded into page['attachments'].
      - attachment links are NEVER added to 'links', so recursion skips them.
      - GitHub tree JSON configs automatically trigger fetching the
        recursive tree API, which is appended as an additional page.
    """

    seen = set()
    pages = []

    def _crawl(u: str, depth=0):
        if u in seen:
            return
        seen.add(u)

        # Fetch the page normally
        p = extract_single_page(u)
        pages.append(p)

        # Pass the ACTUAL JSON/text content
        page_text = p.get("contents") or ""
        _maybe_fetch_github_tree(page_text, pages)

        # ----------------------------------------------
        # Recursion stop
        if depth >= max_depth:
            return

        # Crawl next-level links
        for link in p["links"]:
            _crawl(link, depth + 1)

    _crawl(url, 0)
    return {"pages": pages}
