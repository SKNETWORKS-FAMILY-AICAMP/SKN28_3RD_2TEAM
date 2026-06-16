from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup

from .extractors import extract_file_refs, parse_gviz, slugify
from .http_client import FetchResult, HttpClient
from .models import SourceConfig
from .policies import FilePolicy
from .rendering import PlaywrightRenderer
from .store import RawStore, safe_filename


class BaseAdapter:
    def __init__(self, source: SourceConfig, client: HttpClient, store: RawStore) -> None:
        self.source = source
        self.client = client
        self.store = store
        self.errors: list[dict[str, object]] = []
        self._downloaded_urls: set[str] = set()
        self._fetched_urls: set[str] = set()
        self._collected_route_urls: set[str] = set()

    @property
    def crawl_options(self) -> dict:
        return self.source.raw_options

    @property
    def file_policy(self) -> FilePolicy:
        return FilePolicy.from_options(self.crawl_options.get("file_policy", {}))

    def crawl(self) -> None:
        raise NotImplementedError

    def fetch_and_store(
        self,
        url: str,
        *,
        category: str,
        filename_hint: str | None = None,
        parent_source_id: str | None = None,
        metadata: dict | None = None,
    ) -> tuple[FetchResult, str]:
        result = self.client.get(url)
        record = self.store.save(
            site=self.source.id,
            adapter=self.source.adapter,
            category=category,
            source_url=url,
            canonical_url=result.final_url,
            content=result.content,
            content_type=result.content_type,
            filename_hint=filename_hint,
            parent_source_id=parent_source_id,
            metadata=metadata,
        )
        return result, record.raw_path

    def store_bytes(
        self,
        *,
        url: str,
        content: bytes,
        content_type: str,
        category: str,
        filename_hint: str | None = None,
        parent_source_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        record = self.store.save(
            site=self.source.id,
            adapter=self.source.adapter,
            category=category,
            source_url=url,
            canonical_url=url,
            content=content,
            content_type=content_type,
            filename_hint=filename_hint,
            parent_source_id=parent_source_id,
            metadata=metadata,
        )
        return record.raw_path

    def download_file(self, file_url: str, parent_source_id: str | None = None) -> None:
        absolute = urljoin(self.source.base_url, file_url)
        if absolute in self._downloaded_urls:
            return
        self._downloaded_urls.add(absolute)

        policy = self.file_policy
        try:
            head_result = self.client.head(absolute)
            decision = policy.evaluate(
                requested_url=absolute,
                final_url=head_result.final_url,
                content_length=head_result.content_length,
                content_type=head_result.content_type,
            )
            if decision.skip:
                self._record_skipped_file(
                    url=absolute,
                    final_url=head_result.final_url,
                    reason=decision.reason,
                    metadata=decision.metadata,
                )
                return
        except Exception:
            head_result = None

        try:
            result = self.client.get(absolute)
        except Exception as exc:
            self.record_error(stage="download_file", url=absolute, error=exc)
            return
        decision = policy.evaluate(
            requested_url=absolute,
            final_url=result.final_url,
            content_length=len(result.content),
            content_type=result.content_type,
        )
        if decision.skip:
            self._record_skipped_file(
                url=absolute,
                final_url=result.final_url,
                reason=decision.reason,
                metadata=decision.metadata,
            )
            return
        if not self._is_download_response(result, absolute):
            self.record_error(
                stage="download_file_unexpected_content",
                url=absolute,
                error=ValueError(f"Unexpected content type for file download: {result.content_type}"),
                metadata={"final_url": result.final_url},
            )
            return
        self.store.save(
            site=self.source.id,
            adapter=self.source.adapter,
            category="files",
            source_url=absolute,
            canonical_url=result.final_url,
            content=result.content,
            content_type=result.content_type,
            filename_hint=safe_filename(urlparse(result.final_url).path or urlparse(absolute).path, "file"),
            parent_source_id=parent_source_id,
            metadata={"download_url": absolute},
        )

    def _record_skipped_file(
        self,
        *,
        url: str,
        final_url: str | None,
        reason: str,
        metadata: dict | None = None,
    ) -> None:
        self.store.record_skipped_file(
            site=self.source.id,
            adapter=self.source.adapter,
            source_url=url,
            final_url=final_url,
            reason=reason,
            metadata=metadata,
        )

    def _is_download_response(self, result: FetchResult, requested_url: str) -> bool:
        content_type = result.content_type.lower()
        suffix = (
            Path(urlparse(result.final_url).path).suffix.lower()
            or Path(urlparse(requested_url).path).suffix.lower()
        )
        if suffix == ".pdf":
            return "pdf" in content_type or result.content.startswith(b"%PDF")
        if suffix in {".hwp", ".hwpx", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}:
            return "text/html" not in content_type
        return "text/html" not in content_type

    def download_known_files(self) -> None:
        for file_ref in self.source.known_files:
            self.download_file(file_ref)

    def record_error(self, *, stage: str, url: str, error: Exception, metadata: dict | None = None) -> None:
        self.errors.append(
            {
                "site": self.source.id,
                "stage": stage,
                "url": url,
                "error_type": type(error).__name__,
                "error": str(error),
                "metadata": metadata or {},
            }
        )


class StaticHtmlAdapter(BaseAdapter):
    def crawl(self) -> None:
        routes = self.source.routes or ["/"]
        page_urls = [urljoin(self.source.base_url, route) for route in routes]
        options = self.crawl_options
        max_pages = int(options.get("max_pages", len(page_urls) or 1))
        index = 0
        while index < len(page_urls) and len(self._fetched_urls) < max_pages:
            url = page_urls[index]
            index += 1
            if url in self._fetched_urls:
                continue
            self._fetched_urls.add(url)
            try:
                result, _ = self.fetch_and_store(url, category="pages")
            except Exception as exc:
                self.record_error(stage="fetch_static_page", url=url, error=exc)
                continue
            if options.get("follow_html_links", True):
                linked_pages = self._same_origin_html_links(result.final_url, result.text)
            else:
                linked_pages = []
            for linked_page in linked_pages:
                if linked_page not in page_urls:
                    page_urls.append(linked_page)
            for file_ref in extract_file_refs(result.text):
                self.download_file(urljoin(result.final_url, file_ref))
        self.download_known_files()

    def _same_origin_html_links(self, base_url: str, content: str) -> list[str]:
        soup = BeautifulSoup(content, "html.parser")
        origin = urlparse(self.source.base_url).netloc
        options = self.crawl_options
        allowed_netlocs = {origin, *options.get("domain_aliases", [])}
        include_prefixes = tuple(options.get("include_path_prefixes", []))
        exclude_prefixes = tuple(options.get("exclude_path_prefixes", []))
        exclude_paths = set(options.get("exclude_paths", []))
        links = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            url = urljoin(base_url, href)
            parsed = urlparse(url)
            if parsed.netloc not in allowed_netlocs:
                continue
            if include_prefixes and not parsed.path.startswith(include_prefixes):
                continue
            if parsed.path in exclude_paths:
                continue
            if exclude_prefixes and parsed.path.startswith(exclude_prefixes):
                continue
            if parsed.path.endswith(".html") or parsed.path in ("", "/"):
                clean = parsed._replace(fragment="").geturl()
                if clean not in links:
                    links.append(clean)
        return links


class ViteReactSpaAdapter(BaseAdapter):
    def crawl(self) -> None:
        root_result, _ = self.fetch_and_store(self.source.base_url, category="pages", metadata={"route": "/"})

        asset_urls = self._asset_urls(root_result.final_url, root_result.text)
        visited_assets: set[str] = set()
        while asset_urls:
            asset_url = asset_urls.pop(0)
            if asset_url in visited_assets:
                continue
            visited_assets.add(asset_url)
            result, _ = self.fetch_and_store(
                asset_url,
                category="assets",
                filename_hint=safe_filename(urlparse(asset_url).path, "asset.js"),
            )
            text = result.text
            for file_ref in extract_file_refs(text):
                if self._is_bundle_file_ref(file_ref):
                    self.download_file(urljoin(self.source.base_url, file_ref))
            for nested_asset in self._nested_asset_urls(result.final_url, text):
                if nested_asset not in visited_assets and nested_asset not in asset_urls:
                    asset_urls.append(nested_asset)

        self._collect_routes(self.source.routes, stage="fetch_spa_route")
        self.download_known_files()

    def _asset_urls(self, base_url: str, content: str) -> list[str]:
        soup = BeautifulSoup(content, "html.parser")
        urls: list[str] = []
        for tag in soup.find_all("script", src=True):
            src = tag["src"]
            if src.startswith("http") and urlparse(src).netloc != urlparse(self.source.base_url).netloc:
                continue
            if src.endswith(".js") or "/assets/" in src:
                urls.append(urljoin(base_url, src))
        for tag in soup.find_all("link", href=True):
            href = tag["href"]
            if href.startswith("http") and urlparse(href).netloc != urlparse(self.source.base_url).netloc:
                continue
            if "/assets/" in href and href.endswith((".js", ".css")):
                urls.append(urljoin(base_url, href))
        return urls

    def _nested_asset_urls(self, base_url: str, content: str) -> list[str]:
        urls = []
        for match in re.finditer(r"""assets/[A-Za-z0-9_.-]+\.js""", content):
            urls.append(urljoin(self.source.base_url, match.group(0)))
        return urls

    def _is_bundle_file_ref(self, file_ref: str) -> bool:
        lower = file_ref.lower()
        if file_ref.startswith(("http://", "https://", "/", "./", "../")):
            return True
        return lower.startswith(("files/", "attachments/", "assets/", "public/"))

    def _collect_routes(self, routes: list[str], *, stage: str) -> None:
        if not routes:
            return
        options = self.crawl_options
        render_routes = options.get("render_routes", True)
        if render_routes:
            try:
                with PlaywrightRenderer(
                    timeout_ms=int(options.get("render_timeout_ms", 30000)),
                    wait_until=str(options.get("render_wait_until", "domcontentloaded")),
                    wait_after_ms=int(options.get("render_wait_after_ms", 1000)),
                    extract_text=False,
                ) as renderer:
                    for index, route in enumerate(routes):
                        rendered = self._render_route(route, renderer=renderer, stage=stage)
                        if (
                            not rendered
                            and index == 0
                            and options.get("render_stop_after_first_failure", True)
                        ):
                            for fallback_route in routes[index + 1 :]:
                                self._fetch_route_shell(fallback_route, stage=stage)
                            break
                return
            except Exception as exc:
                self.record_error(
                    stage="render_routes_unavailable",
                    url=self.source.base_url,
                    error=exc,
                    metadata={"routes": routes},
                )
        for route in routes:
            self._fetch_route_shell(route, stage=stage)

    def _render_route(self, route: str, *, renderer: PlaywrightRenderer, stage: str) -> bool:
        route_url = urljoin(self.source.base_url, route)
        if route_url in self._collected_route_urls:
            return True
        try:
            rendered = renderer.render(route_url)
            self.store_bytes(
                url=rendered.url,
                content=rendered.html.encode("utf-8"),
                content_type="text/html; charset=utf-8",
                category="pages",
                filename_hint=f"{route_to_filename(route)}_rendered.html",
                metadata={"route": route, "rendered": True, "renderer": "playwright"},
            )
            for file_ref in extract_file_refs(rendered.html):
                self.download_file(urljoin(rendered.url, file_ref))
            self._collected_route_urls.add(route_url)
            return True
        except Exception as exc:
            self.record_error(
                stage=stage,
                url=route_url,
                error=exc,
                metadata={"route": route, "rendered": True},
            )
            self._fetch_route_shell(route, stage=stage)
            return False

    def _fetch_route_shell(self, route: str, *, stage: str) -> None:
        route_url = urljoin(self.source.base_url, route)
        if route_url in self._collected_route_urls:
            return
        try:
            self.fetch_and_store(route_url, category="pages", metadata={"route": route, "rendered": False})
            self._collected_route_urls.add(route_url)
        except Exception as exc:
            self.record_error(
                stage=stage,
                url=route_url,
                error=exc,
                metadata={"route": route, "rendered": False},
            )


class FxSheetsSpaAdapter(ViteReactSpaAdapter):
    def crawl(self) -> None:
        super().crawl()
        rows_by_sheet = self._fetch_sheets()
        self._download_news_files(rows_by_sheet.get("news", []))
        self._fetch_dynamic_routes(rows_by_sheet)

    def _fetch_sheets(self) -> dict[str, list[dict[str, str]]]:
        sheet_config = self.source.google_sheets
        spreadsheet_id = sheet_config.get("spreadsheet_id")
        template = sheet_config.get("gviz_url_template")
        rows_by_sheet: dict[str, list[dict[str, str]]] = {}
        if not spreadsheet_id or not template:
            return rows_by_sheet
        for sheet_name in sheet_config.get("sheets", []):
            url = template.format(spreadsheet_id=spreadsheet_id, sheet=quote(sheet_name))
            try:
                result, _ = self.fetch_and_store(
                    url,
                    category="sheets",
                    filename_hint=f"{sheet_name}.json",
                    metadata={"spreadsheet_id": spreadsheet_id, "sheet": sheet_name},
                )
            except Exception as exc:
                self.record_error(
                    stage="fetch_google_sheet",
                    url=url,
                    error=exc,
                    metadata={"spreadsheet_id": spreadsheet_id, "sheet": sheet_name},
                )
                continue
            rows = parse_gviz(result.text)
            rows_by_sheet[sheet_name] = rows
        return rows_by_sheet

    def _download_news_files(self, rows: list[dict[str, str]]) -> None:
        for row in rows:
            body = "\n\n".join(
                part
                for part in [
                    row.get("title_ko", ""),
                    row.get("title_en", ""),
                    row.get("body_ko", ""),
                    row.get("body_en", ""),
                ]
                if part
            )
            for file_ref in extract_file_refs(body):
                self.download_file(file_ref)

    def _fetch_dynamic_routes(self, rows_by_sheet: dict[str, list[dict[str, str]]]) -> None:
        routes = []
        for row in rows_by_sheet.get("news", []):
            slug = row.get("slug", "").strip()
            if slug:
                routes.append(f"/news/{slug}")
        for row in rows_by_sheet.get("faculty", []):
            name = row.get("name_en") or row.get("name_ko")
            if name:
                routes.append(f"/faculty-card/{slugify(name)}")
        self._collect_routes(routes, stage="fetch_dynamic_route")


def route_to_filename(route: str) -> str:
    route = route.strip("/") or "index"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", route).strip("._") or "route"


def create_adapter(
    source: SourceConfig,
    client: HttpClient,
    store: RawStore,
) -> BaseAdapter:
    if source.adapter == "static_html":
        return StaticHtmlAdapter(source, client, store)
    if source.adapter == "vite_react_spa_with_google_sheets":
        return FxSheetsSpaAdapter(source, client, store)
    if source.adapter == "vite_react_spa":
        return ViteReactSpaAdapter(source, client, store)
    raise ValueError(f"Unsupported adapter: {source.adapter}")
