# app/utils/url_tools.py
from urllib.parse import urljoin, urlparse
from typing import Optional


def normalize_url(base: str, link: str) -> Optional[str]:
    """
    Convert relative link to absolute using base.
    Returns None for unsupported schemes.
    """
    if not link:
        return None
    joined = urljoin(base, link)
    parsed = urlparse(joined)
    if parsed.scheme not in ("http", "https"):
        return None
    return joined.rstrip("#")


def same_domain(url_a: str, url_b: str) -> bool:
    pa = urlparse(url_a)
    pb = urlparse(url_b)
    return pa.netloc == pb.netloc
