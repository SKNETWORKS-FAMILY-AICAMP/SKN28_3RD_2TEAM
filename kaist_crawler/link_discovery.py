from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


FILE_EXTENSIONS = {
    ".pdf",
    ".hwp",
    ".hwpx",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
}


@dataclass(frozen=True)
class FileLinkRef:
    url: str
    context: str = ""

    def to_metadata(self) -> dict[str, str]:
        return {"context": self.context} if self.context else {}


def same_origin_file_link_refs(
    *,
    base_url: str,
    content: str,
    source_base_url: str,
    domain_aliases: list[str] | tuple[str, ...] = (),
) -> list[FileLinkRef]:
    soup = BeautifulSoup(content, "html.parser")
    origin = urlparse(source_base_url).netloc
    allowed_netlocs = {origin, *domain_aliases}
    links: list[FileLinkRef] = []
    seen_urls: set[str] = set()
    file_tags = soup.find_all(["a", "link", "script"], href=True)
    file_tags.extend(soup.find_all(["a", "link", "script"], src=True))
    for tag in file_tags:
        href = str(tag.get("href") or tag.get("src") or "").strip()
        if not href:
            continue
        url = urljoin(base_url, href)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc not in allowed_netlocs:
            continue
        if Path(parsed.path).suffix.lower() not in FILE_EXTENSIONS:
            continue
        clean = parsed._replace(fragment="").geturl()
        if clean in seen_urls:
            continue
        seen_urls.add(clean)
        links.append(FileLinkRef(url=clean, context=link_context(tag)))
    return links


def same_origin_file_links(
    *,
    base_url: str,
    content: str,
    source_base_url: str,
    domain_aliases: list[str] | tuple[str, ...] = (),
) -> list[str]:
    return [
        item.url
        for item in same_origin_file_link_refs(
            base_url=base_url,
            content=content,
            source_base_url=source_base_url,
            domain_aliases=domain_aliases,
        )
    ]


def same_origin_html_links(
    *,
    base_url: str,
    content: str,
    source_base_url: str,
    domain_aliases: list[str] | tuple[str, ...] = (),
    include_path_prefixes: list[str] | tuple[str, ...] = (),
    exclude_path_prefixes: list[str] | tuple[str, ...] = (),
    exclude_paths: list[str] | tuple[str, ...] = (),
    exclude_calendar_archive_paths: bool = True,
) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    origin = urlparse(source_base_url).netloc
    allowed_netlocs = {origin, *domain_aliases}
    excluded_paths = set(exclude_paths)
    links: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = str(tag["href"]).strip()
        lowered_href = href.lower()
        if (
            not href
            or href.startswith("#")
            or lowered_href.startswith(("mailto:", "tel:", "javascript"))
            or lowered_href in {"void(0)", "void(0);"}
        ):
            continue
        url = urljoin(base_url, href)
        parsed = urlparse(url)
        if parsed.netloc not in allowed_netlocs:
            continue
        last_segment = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        if last_segment.startswith(("@", "~")):
            continue
        if is_download_endpoint(parsed.path):
            continue
        if include_path_prefixes and not parsed.path.startswith(tuple(include_path_prefixes)):
            continue
        if parsed.path in excluded_paths:
            continue
        if exclude_path_prefixes and parsed.path.startswith(tuple(exclude_path_prefixes)):
            continue
        if exclude_calendar_archive_paths and is_calendar_archive_path(parsed.path):
            continue
        suffix = Path(parsed.path).suffix.lower()
        is_query_page = suffix == ".php" and any(key in parsed.query for key in ("mid=", "document_srl="))
        if suffix in {"", ".html", ".htm"} or parsed.path in ("", "/") or is_query_page:
            clean = parsed._replace(fragment="", query=parsed.query if is_query_page else "").geturl()
            if clean not in links:
                links.append(clean)
    return links


def link_context(tag) -> str:
    parts = [
        tag.get_text(" ", strip=True),
        str(tag.get("title") or ""),
        str(tag.get("aria-label") or ""),
    ]
    parent = tag.find_parent(["li", "p", "td", "tr", "article", "section"])
    if parent is not None:
        parts.append(parent.get_text(" ", strip=True))
    context = " ".join(part for part in parts if part).strip()
    return re.sub(r"\s+", " ", context)[:500]


def is_calendar_archive_path(path: str) -> bool:
    segment = path.rstrip("/").rsplit("/", 1)[-1]
    return bool(re.fullmatch(r"20\d{4}", segment))


def is_download_endpoint(path: str) -> bool:
    lowered = path.lower()
    return any(part in lowered for part in ("/file_down/", "/download/", "/downloads/", "/attachment/"))
