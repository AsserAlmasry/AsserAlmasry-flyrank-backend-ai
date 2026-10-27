"""Polite fetching: honest user-agent, timeout, status check, delay between real requests, and a disk cache."""
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

USER_AGENT = "ShelfWatch/1.0 (FlyRank capstone; +https://github.com/AsserAlmasry/flyrank-backend-ai)"
TIMEOUT_S = 10
MIN_DELAY_S = 1.0  # brief says >= 0.5 s; we go slower to be extra polite
RETRY_WAIT_S = 3.0  # one retry, only for timeouts / network errors / 5xx


class FetchError(Exception):
    def __init__(self, url: str, reason: str, status: int | None = None):
        super().__init__(f"{reason} ({url})")
        self.url, self.reason, self.status = url, reason, status


@dataclass
class Page:
    url: str
    html: str
    fetched_at: str  # when the network fetch happened (kept even when served from cache: provenance)
    from_cache: bool


@dataclass
class Fetcher:
    cache_dir: Path
    max_age_hours: float | None = None  # None = cache forever (dev); a number = refetch pages older than that
    stats: dict = field(default_factory=lambda: {"pages_fetched": 0, "cache_hits": 0})
    _last_request: float = 0.0

    def __post_init__(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def cache_path(self, url: str, name: str | None = None) -> Path:
        if name is None:  # stable file name derived from the URL path
            slug = urlparse(url).path.strip("/").replace("/", "__") or "index"
            name = f"{slug[:80]}-{hashlib.sha1(url.encode()).hexdigest()[:8]}.html"
        return self.cache_dir / name

    def get(self, url: str, cache_name: str | None = None) -> Page:
        path = self.cache_path(url, cache_name)
        meta = path.with_suffix(".meta.json")
        if path.exists() and meta.exists() and self._fresh(meta):
            self.stats["cache_hits"] += 1
            return Page(url, path.read_text("utf-8"), json.loads(meta.read_text())["fetched_at"], True)
        try:
            return self._fetch(url, path, meta)
        except FetchError as exc:
            # Retry ONCE, and only when asking again could help: a timeout, a network blip, or a 5xx.
            # Never retry 404 (the page does not exist) or 403 (the site said no).
            retryable = exc.status is None or exc.status >= 500
            if not retryable:
                raise
            self.stats["retries"] = self.stats.get("retries", 0) + 1
            time.sleep(RETRY_WAIT_S)
            return self._fetch(url, path, meta)

    def _fresh(self, meta: Path) -> bool:
        if self.max_age_hours is None:
            return True
        fetched = datetime.fromisoformat(json.loads(meta.read_text())["fetched_at"].replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - fetched).total_seconds() < self.max_age_hours * 3600

    def _fetch(self, url: str, path: Path, meta: Path) -> Page:
        wait = MIN_DELAY_S - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)  # only real requests wait: cached pages never leave the computer
        try:
            resp = self.session.get(url, timeout=TIMEOUT_S)
        except requests.Timeout:
            raise FetchError(url, "timeout")
        except requests.RequestException as exc:
            raise FetchError(url, f"network error: {exc.__class__.__name__}")
        finally:
            self._last_request = time.monotonic()
        self.stats["pages_fetched"] += 1

        if resp.status_code != 200:  # only 200 means "here is your page"
            raise FetchError(url, f"HTTP {resp.status_code}", resp.status_code)

        resp.encoding = "utf-8"  # the site is UTF-8; without this requests guesses latin-1 and "£" becomes "Â£"
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        path.write_text(resp.text, "utf-8")
        meta.write_text(json.dumps({"url": url, "status": resp.status_code, "fetched_at": fetched_at}))
        return Page(url, resp.text, fetched_at, False)
