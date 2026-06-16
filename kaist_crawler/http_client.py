from __future__ import annotations

from dataclasses import dataclass

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
    def __init__(self, timeout_seconds: int = 30, user_agent: str | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update(
            {
                "User-Agent": user_agent
                or "Mozilla/5.0 (compatible; KAIST-AI-RAG-Crawler/0.1; +local-research)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def get(self, url: str) -> FetchResult:
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
