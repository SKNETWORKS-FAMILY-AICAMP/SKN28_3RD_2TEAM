from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


COMMON_FILE_EXCLUDE_PATTERNS = (
    r"(?i)newsletter",
    r"(?i)magazine",
    r"(?i)annual",
    r"(?i)report",
)

LOW_VALUE_PDF_PATTERNS = (
    r"(?i)/oldexam/",
    r"(?i)old[-_]?exam",
    r"(?i)past[-_]?exam",
    r"(?i)\bexam\b",
    r"(?i)viewer\.php",
    r"(?i)pdfjs-viewer",
    "기출",
)


@dataclass(frozen=True)
class SiteProfile:
    source_id: str
    name: str
    base_url: str
    final_url: str
    title: str
    site_type: str
    adapter: str
    confidence: float
    cms_type: str
    url_patterns: list[str]
    route_candidates: list[str]
    file_candidates: list[str]
    google_sheet_ids: list[str]
    robots_status: str
    sitemap_status: str
    risks: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CrawlPlan:
    source_id: str
    name: str
    base_url: str
    adapter: str
    routes: list[str]
    known_files: list[str]
    raw_options: dict[str, Any]
    processing_options: dict[str, Any]
    route_policy: dict[str, Any]
    file_policy: dict[str, Any]
    priority_sections: list[str]
    notes: list[str]
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_source_config(self, *, robots_url: str = "", sitemap_status: str = "") -> dict[str, Any]:
        source: dict[str, Any] = {
            "id": self.source_id,
            "name": self.name,
            "base_url": self.base_url,
            "adapter": self.adapter,
            "routes": self.routes,
            "known_files": self.known_files,
            "crawl_notes": self.notes,
            "raw": self.raw_options,
        }
        if robots_url:
            source["robots_url"] = robots_url
        if sitemap_status:
            source["sitemap_status"] = sitemap_status
        if self.processing_options:
            source["processing"] = self.processing_options
        return source


def build_site_profile(
    *,
    source_id: str,
    name: str,
    base_url: str,
    final_url: str,
    title: str,
    site_type: str,
    adapter: str,
    confidence: float,
    links: list[str],
    asset_urls: list[str],
    root_text: str,
    asset_texts: list[str],
    route_candidates: list[str],
    file_candidates: list[str],
    google_sheet_ids: list[str],
    robots_status: str,
    sitemap_status: str,
    risks: list[str],
    evidence: dict[str, Any],
) -> SiteProfile:
    combined_text = "\n".join([root_text, *asset_texts])
    url_patterns = detect_url_patterns(links=links, asset_urls=asset_urls, text=combined_text)
    return SiteProfile(
        source_id=source_id,
        name=name,
        base_url=base_url,
        final_url=final_url,
        title=title,
        site_type=site_type,
        adapter=adapter,
        confidence=confidence,
        cms_type=detect_cms_type(links=links, asset_urls=asset_urls, text=combined_text),
        url_patterns=url_patterns,
        route_candidates=route_candidates,
        file_candidates=file_candidates,
        google_sheet_ids=google_sheet_ids,
        robots_status=robots_status,
        sitemap_status=sitemap_status,
        risks=risks,
        evidence=evidence,
    )


def build_crawl_plan(profile: SiteProfile) -> CrawlPlan:
    route_policy = build_route_policy(profile)
    file_policy = build_file_policy(profile)
    raw_options = build_raw_options(profile, route_policy=route_policy, file_policy=file_policy)
    processing_options = build_processing_options(file_policy)
    notes = build_plan_notes(profile, route_policy=route_policy, file_policy=file_policy)
    return CrawlPlan(
        source_id=profile.source_id,
        name=profile.name,
        base_url=profile.base_url,
        adapter=profile.adapter,
        routes=profile.route_candidates,
        known_files=profile.file_candidates,
        raw_options=raw_options,
        processing_options=processing_options,
        route_policy=route_policy,
        file_policy=file_policy,
        priority_sections=[
            "faculty",
            "admission",
            "curriculum",
            "degree_requirement",
            "scholarship",
            "notice",
            "seminar",
            "research_highlight",
        ],
        notes=notes,
        risks=profile.risks,
    )


def detect_cms_type(*, links: list[str], asset_urls: list[str], text: str) -> str:
    haystack = "\n".join([text, *links, *asset_urls]).lower()
    if "wp-content" in haystack or "wp-includes" in haystack:
        return "wordpress"
    if "document_srl=" in haystack or "mid=" in haystack:
        return "xe_php_board"
    if "gnuboard" in haystack or "bo_table=" in haystack:
        return "gnuboard"
    if "pdfjs-viewer" in haystack or "viewer.php?file=" in haystack:
        return "pdf_viewer_site"
    if "docs.google.com/spreadsheets" in haystack:
        return "google_sheet_backed"
    return "generic"


def detect_url_patterns(*, links: list[str], asset_urls: list[str], text: str) -> list[str]:
    patterns: list[str] = []
    if any(not Path(urlparse(url).path).suffix for url in links):
        patterns.append("extensionless_routes")
    if any(urlparse(url).query for url in links):
        patterns.append("query_routes")
    if any("mid=" in urlparse(url).query or "document_srl=" in urlparse(url).query for url in links):
        patterns.append("xe_php_board_query")
    if any("file_down" in urlparse(url).path.lower() or "download" in urlparse(url).path.lower() for url in links):
        patterns.append("file_download_endpoints")
    if "viewer.php?file=" in text.lower() or "pdfjs-viewer" in text.lower():
        patterns.append("pdf_viewer_urls")
    if any("/wp-content/uploads/" in urlparse(url).path.lower() for url in links):
        patterns.append("wordpress_uploads")
    if asset_urls:
        patterns.append("asset_linked")
    return patterns


def build_route_policy(profile: SiteProfile) -> dict[str, Any]:
    policy: dict[str, Any] = {
        "follow_html_links": profile.adapter == "static_html",
        "preserve_query_for": [],
        "exclude_path_prefixes": [],
        "exclude_path_suffixes": [
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".ico",
            ".css",
            ".js",
        ],
    }
    if "xe_php_board_query" in profile.url_patterns:
        policy["preserve_query_for"] = ["mid", "document_srl"]
    if "pdf_viewer_urls" in profile.url_patterns:
        policy["exclude_path_prefixes"].append("/cms/wp-content/plugins/pdfjs-viewer-shortcode/")
    return policy


def build_file_policy(profile: SiteProfile) -> dict[str, Any]:
    exclude_patterns = list(COMMON_FILE_EXCLUDE_PATTERNS)
    if "pdf_viewer_urls" in profile.url_patterns or profile.cms_type == "wordpress":
        exclude_patterns.extend(LOW_VALUE_PDF_PATTERNS)
    return {
        "max_file_size_mb": 30,
        "exclude_url_patterns": dedupe(exclude_patterns),
        "include_url_patterns": [],
        "skip_unknown_size": False,
    }


def build_raw_options(
    profile: SiteProfile,
    *,
    route_policy: dict[str, Any],
    file_policy: dict[str, Any],
) -> dict[str, Any]:
    if profile.adapter == "static_html":
        return {
            "max_pages": 80,
            "follow_html_links": True,
            "file_policy": file_policy,
        }
    return {
        "render_routes": True,
        "render_timeout_ms": 10000,
        "render_wait_until": "domcontentloaded",
        "render_wait_after_ms": 1000,
        "render_stop_after_first_failure": True,
        "file_policy": file_policy,
    }


def build_processing_options(file_policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "filter_policy": {
            "exclude_pdf_url_patterns": file_policy.get("exclude_url_patterns", []),
        }
    }


def build_plan_notes(
    profile: SiteProfile,
    *,
    route_policy: dict[str, Any],
    file_policy: dict[str, Any],
) -> list[str]:
    notes = [
        f"SiteProfile cms_type={profile.cms_type}, url_patterns={', '.join(profile.url_patterns) or 'none'}.",
        f"CrawlPlan prioritizes {len(profile.route_candidates)} seed route(s) and {len(profile.file_candidates)} file candidate(s).",
    ]
    if route_policy.get("preserve_query_for"):
        notes.append(f"Preserve query params for {', '.join(route_policy['preserve_query_for'])} board routes.")
    if file_policy.get("exclude_url_patterns"):
        notes.append("Apply low-value file filters before PDF/text processing.")
    return notes


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        results.append(value)
    return results
