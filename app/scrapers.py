# app/scrapers.py
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import mimetypes
import os
import tempfile

logger = logging.getLogger("app.scrapers")

# -------------------------------------------------------------------
# Static Fetch
# -------------------------------------------------------------------
def _static_fetch(url: str):
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        return resp.text or ""
    except Exception as e:
        logger.warning("Static fetch failed for %s: %s", url, e)
        return None


# -------------------------------------------------------------------
# Playwright Fetch
# -------------------------------------------------------------------
def _playwright_fetch(url: str):
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


# -------------------------------------------------------------------
# Attachment Downloader
# -------------------------------------------------------------------
def _download_attachment(url: str) -> dict:
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return None

        fname = url.split("/")[-1] or "file.bin"
        ctype = resp.headers.get("Content-Type") or mimetypes.guess_type(fname)[0]

        tmpdir = tempfile.gettempdir()
        local_path = os.path.join(tmpdir, f"tds_phase1_{fname}")

        with open(local_path, "wb") as f:
            f.write(resp.content)

        return {
            "id": os.path.basename(local_path),
            "filename": fname,
            "content_type": ctype,
            "size_bytes": len(resp.content),
            "source_url": url,
            "local_path": local_path,
        }
    except Exception as e:
        logger.error("Attachment download failed for %s: %s", url, e)
        return None


# -------------------------------------------------------------------
# Extract a single page
# -------------------------------------------------------------------
def extract_single_page(url: str) -> dict:
    logger.info("Fetching page %s", url)

    html = _static_fetch(url)

    needs_js = False
    if html is None:
        needs_js = True
    else:
        if len(html.strip()) < 200:
            needs_js = True
        if "<script" in html.lower() and "innerHTML" in html:
            needs_js = True

    if needs_js:
        logger.info("Static too small → JS fallback for %s", url)
        html = _playwright_fetch(url)

    html = html or ""
    soup = BeautifulSoup(html, "html.parser")

    # Clean visible text
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    visible_text = soup.get_text(" ", strip=True)

    # Extract links
    links = []
    for a in soup.find_all("a", href=True):
        abs_url = urljoin(url, a["href"])
        links.append(abs_url)

    # Extract attachments: CSV, PDF, audio, images
    attachment_exts = (".csv", ".pdf", ".txt", ".json",
                       ".opus", ".wav", ".mp3", ".ogg", ".m4a",
                       ".png", ".jpg", ".jpeg")

    attachments = []

    # A-tags pointing to attachments
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"]).lower()
        if any(href.endswith(ext) for ext in attachment_exts):
            meta = _download_attachment(href)
            if meta:
                attachments.append(meta)

    # AUDIO tags with src
    for audio in soup.find_all("audio"):
        src = audio.get("src")
        if src:
            href = urljoin(url, src).lower()
            if any(href.endswith(ext) for ext in attachment_exts):
                meta = _download_attachment(href)
                if meta:
                    attachments.append(meta)

    return {
        "url": url,
        "html": html,
        "text": visible_text,
        "links": links,
        "attachments": attachments,
    }


# -------------------------------------------------------------------
# Recursive crawler (depth 1)
# -------------------------------------------------------------------
def extract_webpage_recursive(url: str, max_depth=1):
    seen = set()
    pages = []

    def _crawl(u: str, depth: int):
        if u in seen:
            return
        seen.add(u)

        p = extract_single_page(u)
        pages.append(p)

        if depth >= max_depth:
            return

        for link in p["links"]:
            _crawl(link, depth + 1)

    _crawl(url, 0)
    return {"pages": pages}
