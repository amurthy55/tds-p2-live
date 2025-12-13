# app/utils/file_tools.py
import base64
import mimetypes
import uuid
from typing import Dict, Optional
from requests import Response

DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB default cap for downloads


def generate_uuid() -> str:
    return str(uuid.uuid4())


def filename_from_url(url: str) -> str:
    # Best-effort filename extraction
    import os
    from urllib.parse import urlparse, unquote
    parsed = urlparse(url)
    name = os.path.basename(parsed.path) or "download"
    return unquote(name)


def mime_from_response(resp: Response, url: str) -> str:
    ctype = resp.headers.get("Content-Type")
    if ctype:
        return ctype.split(";")[0].strip()
    guessed, _ = mimetypes.guess_type(url)
    return guessed or "application/octet-stream"


def safe_download_bytes(resp: Response, max_bytes: int = DEFAULT_MAX_BYTES) -> bytes:
    # Stream and limit size to avoid OOM and malicious huge downloads
    resp.raise_for_status()
    chunks = []
    total = 0
    for chunk in resp.iter_content(chunk_size=8192):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"Download exceeds max size {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def build_attachment(resp: Response, url: str, max_bytes: int = DEFAULT_MAX_BYTES) -> Dict:
    data = safe_download_bytes(resp, max_bytes=max_bytes)
    encoded = base64.b64encode(data).decode("ascii")
    return {
        "id": generate_uuid(),
        "filename": filename_from_url(url),
        "content_type": mime_from_response(resp, url),
        "data": encoded,
        "size_bytes": len(data),
        "source_url": url
    }
