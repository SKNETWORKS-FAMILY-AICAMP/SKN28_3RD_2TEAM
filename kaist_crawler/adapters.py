from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup

from .extractors import extract_file_refs, html_to_text, js_literal_text, pdf_to_text
from .http_client import FetchResult, HttpClient
from .models import Document, SourceConfig
from .store import RawStore, safe_filename, stable_id


class BaseAdapter:
    def __init__(self, source: SourceConfig, client: HttpClient, store: RawStore) -> None:
        self.source = source
        self.client = client
        self.store = store
        self.documents: list[Document] = []
        self.errors: list[dict[str, object]] = []
        self._downloaded_urls: set[str] = set()
        self._fetched_urls: set[str] = set()

    @property
    def crawl_options(self) -> dict:
        options = self.source.raw.get("raw", {})
        return options if isinstance(options, dict) else {}

    def crawl(self) -> list[Document]:
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

    def add_document(
        self,
        *,
        source_url: str,
        title: str,
        text: str,
        raw_path: str | None,
        metadata: dict | None = None,
    ) -> None:
        text = text.strip()
        if not text:
            return
        doc_id = f"{self.source.id}:{stable_id(source_url, title, text[:200])}"
        self.documents.append(
            Document(
                doc_id=doc_id,
                site=self.source.id,
                source_url=source_url,
                title=title or self.source.name,
                text=text,
                raw_path=raw_path,
                metadata=metadata or {},
            )
        )

    def download_file(self, file_url: str, parent_source_id: str | None = None) -> None:
        absolute = urljoin(self.source.base_url, file_url)
        if absolute in self._downloaded_urls:
            return
        self._downloaded_urls.add(absolute)
        try:
            result = self.client.get(absolute)
        except Exception as exc:
            self.record_error(stage="download_file", url=absolute, error=exc)
            return
        if not self._is_download_response(result, absolute):
            self.record_error(
                stage="download_file_unexpected_content",
                url=absolute,
                error=ValueError(f"Unexpected content type for file download: {result.content_type}"),
                metadata={"final_url": result.final_url},
            )
            return
        record = self.store.save(
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
        raw_path = record.raw_path
        suffix = Path(urlparse(result.final_url).path or urlparse(absolute).path).suffix.lower()
        if suffix == ".pdf":
            text = pdf_to_text(raw_path)
            if text:
                self.add_document(
                    source_url=result.final_url,
                    title=safe_filename(urlparse(result.final_url).path, "pdf"),
                    text=text,
                    raw_path=raw_path,
                    metadata={"document_type": "pdf"},
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
    def crawl(self) -> list[Document]:
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
                result, raw_path = self.fetch_and_store(url, category="pages")
            except Exception as exc:
                self.record_error(stage="fetch_static_page", url=url, error=exc)
                continue
            title, text = html_to_text(result.text)
            self.add_document(
                source_url=result.final_url,
                title=title,
                text=text,
                raw_path=raw_path,
                metadata={"document_type": "html"},
            )
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
        return self.documents

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
    def crawl(self) -> list[Document]:
        root_result, root_path = self.fetch_and_store(self.source.base_url, category="pages", metadata={"route": "/"})
        title, text = html_to_text(root_result.text)
        self.add_document(
            source_url=root_result.final_url,
            title=title,
            text=text,
            raw_path=root_path,
            metadata={"document_type": "html_shell", "route": "/"},
        )

        bundle_texts: list[str] = []
        asset_urls = self._asset_urls(root_result.final_url, root_result.text)
        visited_assets: set[str] = set()
        while asset_urls:
            asset_url = asset_urls.pop(0)
            if asset_url in visited_assets:
                continue
            visited_assets.add(asset_url)
            result, raw_path = self.fetch_and_store(
                asset_url,
                category="assets",
                filename_hint=safe_filename(urlparse(asset_url).path, "asset.js"),
            )
            text = result.text
            extracted = js_literal_text(text)
            if extracted:
                bundle_texts.append(extracted)
            for file_ref in extract_file_refs(text):
                if self._is_bundle_file_ref(file_ref):
                    self.download_file(urljoin(self.source.base_url, file_ref))
            for nested_asset in self._nested_asset_urls(result.final_url, text):
                if nested_asset not in visited_assets and nested_asset not in asset_urls:
                    asset_urls.append(nested_asset)
        if bundle_texts:
            self.add_document(
                source_url=self.source.base_url,
                title=f"{self.source.name} SPA bundle text",
                text="\n\n".join(bundle_texts),
                raw_path=None,
                metadata={"document_type": "spa_bundle_text"},
            )

        for route in self.source.routes:
            route_url = urljoin(self.source.base_url, route)
            if route_url in self._fetched_urls:
                continue
            self._fetched_urls.add(route_url)
            try:
                self.fetch_and_store(route_url, category="pages", metadata={"route": route, "rendered": False})
            except Exception as exc:
                self.record_error(
                    stage="fetch_spa_route",
                    url=route_url,
                    error=exc,
                    metadata={"route": route, "rendered": False},
                )
                continue
        self.download_known_files()
        return self.documents

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


class FxSheetsSpaAdapter(ViteReactSpaAdapter):
    def crawl(self) -> list[Document]:
        super().crawl()
        rows_by_sheet = self._fetch_sheets()
        self._add_news_documents(rows_by_sheet.get("news", []))
        self._add_faculty_documents(rows_by_sheet.get("faculty", []))
        self._fetch_dynamic_routes(rows_by_sheet)
        return self.documents

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
                result, raw_path = self.fetch_and_store(
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
            self.add_document(
                source_url=result.final_url,
                title=f"{self.source.name} {sheet_name} sheet",
                text=sheet_rows_to_text(rows),
                raw_path=raw_path,
                metadata={"document_type": "google_sheet", "sheet": sheet_name},
            )
        return rows_by_sheet

    def _add_news_documents(self, rows: list[dict[str, str]]) -> None:
        for row in rows:
            slug = row.get("slug", "").strip()
            if not slug:
                continue
            title = row.get("title_ko") or row.get("title_en") or slug
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
            self.add_document(
                source_url=urljoin(self.source.base_url, f"/news/{slug}"),
                title=title,
                text=body,
                raw_path=None,
                metadata={"document_type": "news", "slug": slug, "category": row.get("category", "")},
            )
            for file_ref in extract_file_refs(body):
                self.download_file(file_ref)

    def _add_faculty_documents(self, rows: list[dict[str, str]]) -> None:
        for row in rows:
            name = row.get("name_ko") or row.get("name_en")
            if not name:
                continue
            slug = slugify(row.get("name_en") or name)
            text = "\n".join(f"{key}: {value}" for key, value in row.items() if value)
            self.add_document(
                source_url=urljoin(self.source.base_url, f"/faculty-card/{slug}"),
                title=name,
                text=text,
                raw_path=None,
                metadata={"document_type": "faculty", "slug": slug},
            )

    def _fetch_dynamic_routes(self, rows_by_sheet: dict[str, list[dict[str, str]]]) -> None:
        for row in rows_by_sheet.get("news", []):
            slug = row.get("slug", "").strip()
            if slug:
                self._fetch_route(f"/news/{slug}")
        for row in rows_by_sheet.get("faculty", []):
            name = row.get("name_en") or row.get("name_ko")
            if name:
                self._fetch_route(f"/faculty-card/{slugify(name)}")

    def _fetch_route(self, route: str) -> None:
        url = urljoin(self.source.base_url, route)
        if url in self._fetched_urls:
            return
        self._fetched_urls.add(url)
        try:
            self.fetch_and_store(url, category="pages", metadata={"route": route, "rendered": False})
        except Exception as exc:
            self.record_error(
                stage="fetch_dynamic_route",
                url=url,
                error=exc,
                metadata={"route": route, "rendered": False},
            )
            return


def parse_gviz(content: str) -> list[dict[str, str]]:
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end < 0:
        return []
    payload = json.loads(content[start : end + 1])
    table = payload.get("table", {})
    columns = [(column.get("label") or "").strip() for column in table.get("cols", [])]
    rows: list[dict[str, str]] = []
    for row in table.get("rows", []):
        item: dict[str, str] = {}
        cells = row.get("c") or []
        for index, column in enumerate(columns):
            if not column:
                continue
            cell = cells[index] if index < len(cells) else None
            if not cell or cell.get("v") is None:
                item[column] = ""
            else:
                item[column] = str(cell.get("f", cell.get("v")))
        rows.append(item)
    return rows


def sheet_rows_to_text(rows: list[dict[str, str]]) -> str:
    blocks = []
    for row in rows:
        lines = [f"{key}: {value}" for key, value in row.items() if value]
        if lines:
            blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def slugify(value: str) -> str:
    original = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", original)
    return slug.strip("-") or stable_id(original)[:12]


def create_adapter(source: SourceConfig, client: HttpClient, store: RawStore) -> BaseAdapter:
    if source.adapter == "static_html":
        return StaticHtmlAdapter(source, client, store)
    if source.adapter == "vite_react_spa_with_google_sheets":
        return FxSheetsSpaAdapter(source, client, store)
    if source.adapter == "vite_react_spa":
        return ViteReactSpaAdapter(source, client, store)
    raise ValueError(f"Unsupported adapter: {source.adapter}")
