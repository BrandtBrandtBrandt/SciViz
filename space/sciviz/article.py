"""Fetch a bounded public article through a DNS-pinned transport."""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
import safehttpx
import trafilatura

from .contracts import Article, SciVizError

MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_TEXT_CHARS = 12000
SUPPORTED_HOSTS = {"quantamagazine.org", "www.quantamagazine.org", "arxiv.org", "www.arxiv.org"}


def normalize_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise SciVizError("invalid_url", "Enter an article URL, up to 2,048 characters.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise SciVizError("invalid_url", "Enter the URL on a single line.")
    try:
        parsed = urlsplit(value.strip())
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise ValueError("HTTPS without credentials or custom ports is required")
    except ValueError as error:
        raise SciVizError("invalid_url", "Use a public HTTPS article URL without login details.") from error
    if host not in SUPPORTED_HOSTS:
        raise SciVizError("unsupported_source", "Try a Quanta Magazine article or arXiv abstract, or paste an abstract instead.")
    path = parsed.path
    if "arxiv.org" in host:
        host = "arxiv.org"
        if path.startswith("/pdf/"):
            path = "/abs/" + path[5:].removesuffix(".pdf")
        if not re.fullmatch(r"/abs/(?:[A-Za-z.-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?/?", path):
            raise SciVizError("invalid_url", "Use an arXiv abstract or paper URL.")
    elif not path.strip("/"):
        raise SciVizError("invalid_url", "Link to an article rather than the publication's homepage.")
    return urlunsplit(("https", host, path, "", ""))


def pasted_abstract(text: str) -> Article:
    text = text.strip()
    if not 80 <= len(text) <= MAX_TEXT_CHARS:
        raise SciVizError("invalid_abstract", "Paste between 80 and 12,000 characters of abstract text.")
    if "\x00" in text:
        raise SciVizError("invalid_abstract", "The abstract contains an unsupported character.")
    return Article("Pasted abstract", text, None, "abstract")


def extract_article(html: str, url: str) -> Article:
    # Quanta also publishes interactive features in this same URL/feed format.
    # Their text lives in an embedded application, not the outer article HTML.
    # Do not mistake navigation or a short promotional summary for the article.
    if re.search(r"<iframe\b[^>]*\bfull-size-interactive\b", html, re.IGNORECASE):
        raise SciVizError("interactive_article", "This is an interactive feature rather than a readable article. Choose another article or paste a public abstract.")
    text = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True)
    if not text or len(text.strip()) < 80:
        raise SciVizError("unreadable_article", "We couldn't read the article text. Try pasting its abstract instead.")
    metadata = trafilatura.extract_metadata(html)
    title = (metadata.title if metadata else None) or "Scientific article"
    title = " ".join(title.split())[:200]
    return Article(title, text[:MAX_TEXT_CHARS], url, "article", len(text) > MAX_TEXT_CHARS)


async def fetch_article(value: str) -> Article:
    url = normalize_url(value)
    try:
        async with asyncio.timeout(15):
            for hop in range(4):
                # Pin the verified public IP for this exact hop; never let redirects
                # reuse a prior hostname's validation. Ignore environment proxies.
                verified_ip = await safehttpx.async_validate_url(urlsplit(url).hostname)
                transport = safehttpx.AsyncSecureTransport(verified_ip)
                async with httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False, timeout=10) as client:
                    async with client.stream("GET", url, headers={"User-Agent": "SciViz/1.0 (+https://www.matiasbrandt.com/projects/from-text-to-visuals)"}) as response:
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location or hop == 3:
                                raise SciVizError("article_redirect", "This article redirects too many times. Paste an abstract instead.")
                            url = normalize_url(urljoin(url, location))
                            continue
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "").lower()
                        if not content_type.startswith(("text/html", "application/xhtml+xml")):
                            raise SciVizError("unsupported_document", "Use an HTML article or arXiv abstract rather than a file download.")
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            chunks.extend(chunk)
                            if len(chunks) > MAX_HTML_BYTES:
                                raise SciVizError("article_too_large", "This page is too large to process. Paste its abstract instead.")
                        encoding = response.encoding or "utf-8"
                        return extract_article(chunks.decode(encoding, errors="replace"), url)
    except SciVizError:
        raise
    except (httpx.HTTPError, TimeoutError, OSError, ValueError) as error:
        raise SciVizError("article_unavailable", "We couldn't access that article. You can paste an abstract instead.") from error
    raise SciVizError("article_unavailable", "We couldn't read this article.")
