from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep

import requests


@dataclass
class FetchResult:
    url: str
    final_url: str
    content: bytes
    content_type: str
    status_code: int

    @property
    def text(self) -> str:
        encoding = requests.utils.get_encoding_from_headers({"content-type": self.content_type}) or "utf-8"
        return self.content.decode(encoding, errors="replace")


@dataclass
class HeadResult:
    url: str
    final_url: str
    content_type: str
    status_code: int
    content_length: int | None = None


class HttpClient:
    def __init__(
        self,
        timeout_seconds: int = 30,
        user_agent: str | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = max(0.0, float(delay_seconds))
        self._last_request_started_at: float | None = None
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update(
            {
                "User-Agent": user_agent
                or "Mozilla/5.0 (compatible; Graduate-RAG-Crawler/0.1; +local-research)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def get(self, url: str) -> FetchResult:
        self._wait_before_request()
        response = self.session.get(url, timeout=self.timeout_seconds, allow_redirects=True)
        response.raise_for_status()
        return FetchResult(
            url=url,
            final_url=response.url,
            content=response.content,
            content_type=response.headers.get("content-type", "application/octet-stream"),
            status_code=response.status_code,
        )

    def head(self, url: str) -> HeadResult:
        self._wait_before_request()
        response = self.session.head(url, timeout=self.timeout_seconds, allow_redirects=True)
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        return HeadResult(
            url=url,
            final_url=response.url,
            content_type=response.headers.get("content-type", "application/octet-stream"),
            status_code=response.status_code,
            content_length=int(content_length) if content_length and content_length.isdigit() else None,
        )

    def _wait_before_request(self) -> None:
        if self.delay_seconds <= 0:
            self._last_request_started_at = monotonic()
            return
        now = monotonic()
        if self._last_request_started_at is not None:
            elapsed = now - self._last_request_started_at
            remaining = self.delay_seconds - elapsed
            if remaining > 0:
                sleep(remaining)
                now = monotonic()
        self._last_request_started_at = now
