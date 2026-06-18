from __future__ import annotations

import html
from dataclasses import dataclass
from time import sleep


@dataclass(frozen=True)
class RenderedPage:
    url: str
    title: str
    html: str
    text: str


class PlaywrightRenderer:
    def __init__(
        self,
        *,
        timeout_ms: int = 30000,
        wait_until: str = "domcontentloaded",
        wait_after_ms: int = 1000,
        extract_text: bool = True,
    ) -> None:
        self.timeout_ms = timeout_ms
        self.wait_until = wait_until
        self.wait_after_ms = wait_after_ms
        self.extract_text = extract_text
        self._playwright = None
        self._browser = None
        self._context = None

    def __enter__(self) -> "PlaywrightRenderer":
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Playwright is not installed. Install it with: python -m pip install playwright") from exc
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=True)
            self._context = self._browser.new_context(ignore_https_errors=True)
        except Exception as exc:
            if self._browser is not None:
                self._browser.close()
                self._browser = None
            self._playwright.stop()
            self._playwright = None
            raise RuntimeError(
                "Playwright Chromium could not start. Install it with: python -m playwright install chromium"
            ) from exc
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def render(self, url: str) -> RenderedPage:
        if self._context is None:
            raise RuntimeError("Renderer is not started")
        page = self._context.new_page()
        try:
            page.goto(url, wait_until=self.wait_until, timeout=self.timeout_ms)
            page.wait_for_timeout(self.wait_after_ms)
            if page.url.startswith("chrome-error://"):
                raise RuntimeError(f"Chromium failed to load page: {url}")
            html = self._page_content(page)
            text = ""
            if self.extract_text:
                try:
                    text = page.locator("body").inner_text(timeout=5000)
                except Exception:
                    text = ""
            return RenderedPage(url=page.url, title=self._page_title(page), html=html, text=text)
        finally:
            page.close()

    def _page_content(self, page) -> str:
        last_error: Exception | None = None
        for _ in range(3):
            try:
                return page.content()
            except Exception as exc:
                last_error = exc
                sleep(0.5)
        try:
            text = page.locator("body").inner_text(timeout=5000)
        except Exception:
            text = ""
        if text.strip():
            return f"<html><body><pre>{html.escape(text)}</pre></body></html>"
        if last_error is not None:
            raise last_error
        return ""

    def _page_title(self, page) -> str:
        try:
            return page.title()
        except Exception:
            return ""
