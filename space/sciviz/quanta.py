"""Random recent article from Quanta's public RSS feed; no GPU or AI call."""

import asyncio
import re
import secrets
import time
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import httpx
import safehttpx

from .article import fetch_article, normalize_url
from .contracts import SciVizError

FEED_URL = "https://www.quantamagazine.org/feed/"
MAX_FEED_BYTES = 512 * 1024
_cached_articles = []
_expires_at = 0.0


def parse_feed(data: bytes) -> list[dict]:
    if len(data) > MAX_FEED_BYTES or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Unsupported feed size or declarations")
    root = ET.fromstring(data)
    articles = {}
    for item in root.findall("./channel/item")[:100]:
        categories = {(category.text or "").strip().lower() for category in item.findall("category")}
        if categories.intersection({"multimedia", "interactive", "podcasts"}):
            continue
        try:
            url = normalize_url(item.findtext("link") or "")
        except SciVizError:
            continue
        if urlsplit(url).hostname not in ("www.quantamagazine.org", "quantamagazine.org"):
            continue
        if not re.fullmatch(r"/[a-z0-9-]+-\d{8}/?", urlsplit(url).path):
            continue
        title = " ".join((item.findtext("title") or "").split())[:200]
        if title:
            articles[url] = {"title": title, "url": url}
    if not articles:
        raise ValueError("No usable articles in feed")
    return list(articles.values())


def choose_article(articles: list[dict], previous: str) -> dict:
    candidates = [article for article in articles if article["url"] != previous] or articles
    return secrets.choice(candidates)


async def random_article(previous="") -> dict:
    global _cached_articles, _expires_at
    try:
        if not _cached_articles or time.monotonic() >= _expires_at:
            async with asyncio.timeout(15):
                ip = await safehttpx.async_validate_url("www.quantamagazine.org")
                transport = safehttpx.AsyncSecureTransport(ip)
                async with httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False, timeout=10) as client:
                    async with client.stream("GET", FEED_URL, headers={"User-Agent": "SciViz/1.0 (+https://www.matiasbrandt.com)"}) as response:
                        response.raise_for_status()
                        data = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            data.extend(chunk)
                            if len(data) > MAX_FEED_BYTES:
                                raise ValueError("Feed exceeds size limit")
                articles = parse_feed(bytes(data))
            _cached_articles = articles
            _expires_at = time.monotonic() + 900
        # A valid feed link is not proof that its page contains readable text.
        # Validate at most three candidates, without invoking any models or GPU.
        for _ in range(min(3, len(_cached_articles))):
            selected = choose_article(_cached_articles, previous[:2048])
            try:
                await fetch_article(selected["url"])
            except SciVizError:
                _cached_articles = [article for article in _cached_articles if article["url"] != selected["url"]]
                continue
            return {"status": "ready", **selected, "source": "Quanta Magazine's recent RSS articles"}
        raise SciVizError("feed_unavailable", "We couldn't find a readable Quanta article right now. Paste another article URL or a public abstract instead.")
    except (httpx.HTTPError, TimeoutError, OSError, ValueError, ET.ParseError) as error:
        raise SciVizError("feed_unavailable", "We couldn't get a Quanta article right now. Paste an article URL or abstract instead.") from error
