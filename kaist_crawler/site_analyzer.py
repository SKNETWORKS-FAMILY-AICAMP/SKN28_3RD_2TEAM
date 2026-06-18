from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import yaml
from bs4 import BeautifulSoup

from .crawl_planner import CrawlPlan, SiteProfile, build_crawl_plan, build_site_profile
from .extractors import extract_file_refs
from .http_client import FetchResult, HttpClient
from .link_discovery import FILE_EXTENSIONS, same_origin_file_links


GRADUATE_ROUTE_HINTS: tuple[str, ...] = (
    "about",
    "intro",
    "welcome",
    "department",
    "faculty",
    "people",
    "professor",
    "research",
    "admission",
    "graduate",
    "curriculum",
    "course",
    "education",
    "requirement",
    "scholarship",
    "tuition",
    "notice",
    "news",
    "event",
    "seminar",
    "입학",
    "대학원",
    "교수",
    "구성원",
    "교육",
    "교과",
    "졸업",
    "장학",
    "공지",
    "소식",
)

DEFAULT_SPA_ROUTES: tuple[str, ...] = (
    "/",
    "/about",
    "/faculty",
    "/people",
    "/admission",
    "/admissions",
    "/curriculum",
    "/course",
    "/notice",
)

GOOGLE_SHEET_RE = re.compile(r"https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)")
ROUTE_LIKE_RE = re.compile(r"""["'`](\/[A-Za-z0-9][A-Za-z0-9_./-]{1,80})["'`]""")
LOW_VALUE_ROUTE_PARTS = (
    "account",
    "login",
    "logout",
    "privacy",
    "sitemap",
    "giving_alumni",
)


@dataclass(frozen=True)
class SiteAnalysis:
    input_url: str
    final_url: str
    source_id: str
    name: str
    title: str
    site_type: str
    adapter: str
    confidence: float
    routes: list[str]
    known_files: list[str]
    robots_url: str
    robots_status: str
    sitemap_url: str
    sitemap_status: str
    google_sheets: dict[str, Any] = field(default_factory=dict)
    dynamic_routes: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    crawl_notes: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    site_profile: SiteProfile | None = None
    crawl_plan: CrawlPlan | None = None

    def recommended_source(self) -> dict[str, Any]:
        if self.crawl_plan:
            source = self.crawl_plan.to_source_config(
                robots_url=self.robots_url,
                sitemap_status=self.sitemap_status,
            )
            if self.dynamic_routes:
                source["dynamic_routes"] = self.dynamic_routes
            if self.google_sheets:
                source["google_sheets"] = self.google_sheets
            return source
        source: dict[str, Any] = {
            "id": self.source_id,
            "name": self.name,
            "base_url": config_base_url(self.final_url),
            "adapter": self.adapter,
            "robots_url": self.robots_url,
            "sitemap_status": self.sitemap_status,
            "routes": self.routes,
            "known_files": self.known_files,
            "crawl_notes": self.crawl_notes,
        }
        if self.dynamic_routes:
            source["dynamic_routes"] = self.dynamic_routes
        if self.google_sheets:
            source["google_sheets"] = self.google_sheets
        if self.raw:
            source["raw"] = self.raw
        return source

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["recommended_source"] = self.recommended_source()
        return payload


def analyze_site(
    url: str,
    *,
    source_id: str | None = None,
    name: str | None = None,
    timeout_seconds: int = 30,
    max_routes: int = 24,
    max_assets: int = 5,
    fetch_assets: bool = True,
    client: HttpClient | None = None,
) -> SiteAnalysis:
    client = client or HttpClient(timeout_seconds=timeout_seconds)
    start_url = normalize_start_url(url)
    root_result = client.get(start_url)
    final_url = root_result.final_url
    base_url = config_base_url(final_url)
    soup = BeautifulSoup(root_result.text, "html.parser")
    page_title = html_title(soup)

    asset_urls = html_asset_urls(final_url, root_result.text)
    asset_results = fetch_analyzer_assets(client, asset_urls, max_assets=max_assets) if fetch_assets else []
    asset_texts = [result.text for result in asset_results]
    all_text = "\n".join([root_result.text, *asset_texts])
    links = same_origin_links(final_url, root_result.text)
    file_refs = known_file_refs(final_url, [root_result.text, *asset_texts])
    google_sheet_ids = sorted(set(GOOGLE_SHEET_RE.findall(all_text)))
    js_routes = javascript_route_hints(all_text)

    robots_url, robots_status, robot_sitemaps = analyze_robots(client, base_url)
    sitemap_url, sitemap_status = analyze_sitemap(client, base_url, robot_sitemaps)
    adapter, site_type, confidence, evidence = classify_site(
        soup=soup,
        root_text=root_result.text,
        asset_urls=asset_urls,
        asset_texts=asset_texts,
        google_sheet_ids=google_sheet_ids,
    )

    routes = recommend_routes(
        base_url=base_url,
        links=links,
        js_routes=js_routes,
        adapter=adapter,
        max_routes=max_routes,
    )
    raw = recommend_raw_options(adapter)
    google_sheets = recommend_google_sheet_config(google_sheet_ids)
    notes, risks = recommendation_notes(
        adapter=adapter,
        site_type=site_type,
        confidence=confidence,
        routes=routes,
        known_files=file_refs,
        robots_status=robots_status,
        sitemap_status=sitemap_status,
        google_sheet_ids=google_sheet_ids,
        fetched_asset_count=len(asset_results),
    )
    resolved_source_id = source_id or source_id_from_url(final_url)
    resolved_name = name or page_title or source_name_from_url(final_url)
    site_profile = build_site_profile(
        source_id=resolved_source_id,
        name=resolved_name,
        base_url=base_url,
        final_url=final_url,
        title=page_title,
        site_type=site_type,
        adapter=adapter,
        confidence=confidence,
        links=links,
        asset_urls=asset_urls,
        root_text=root_result.text,
        asset_texts=asset_texts,
        route_candidates=routes,
        file_candidates=file_refs,
        google_sheet_ids=google_sheet_ids,
        robots_status=robots_status,
        sitemap_status=sitemap_status,
        risks=risks,
        evidence=evidence,
    )
    crawl_plan = build_crawl_plan(site_profile)
    plan_source = crawl_plan.to_source_config(
        robots_url=robots_url,
        sitemap_status=sitemap_status,
    )

    return SiteAnalysis(
        input_url=url,
        final_url=final_url,
        source_id=resolved_source_id,
        name=resolved_name,
        title=page_title,
        site_type=site_type,
        adapter=adapter,
        confidence=confidence,
        routes=plan_source["routes"],
        known_files=plan_source["known_files"],
        robots_url=robots_url,
        robots_status=robots_status,
        sitemap_url=sitemap_url,
        sitemap_status=sitemap_status,
        google_sheets=google_sheets,
        raw=plan_source.get("raw", raw),
        crawl_notes=[*notes, *crawl_plan.notes],
        risks=risks,
        evidence=evidence,
        site_profile=site_profile,
        crawl_plan=crawl_plan,
    )


def normalize_start_url(url: str) -> str:
    value = url.strip()
    if not value:
        raise ValueError("url is required")
    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        value = f"https://{value}"
    return value


def config_base_url(final_url: str) -> str:
    parsed = urlparse(final_url)
    path = parsed.path or "/"
    if not path.endswith("/"):
        path = path.rsplit("/", 1)[0] + "/"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def source_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [parsed.netloc.replace("www.", ""), parsed.path.strip("/")]
    raw = "_".join(part for part in parts if part)
    raw = re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").lower()
    return raw or "graduate_site"


def source_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "") or "Graduate School"


def html_title(soup: BeautifulSoup) -> str:
    if soup.title:
        title = " ".join(soup.title.stripped_strings).strip()
        if title:
            return title
    heading = soup.find(["h1", "h2"])
    return " ".join(heading.stripped_strings).strip() if heading else ""


def html_asset_urls(base_url: str, content: str) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    urls: list[str] = []
    for tag in soup.find_all("script", src=True):
        src = str(tag["src"])
        if src.startswith(("data:", "javascript:")):
            continue
        if src.endswith((".js", ".mjs")) or "/assets/" in src:
            append_unique(urls, urljoin(base_url, src))
    for tag in soup.find_all("link", href=True):
        href = str(tag["href"])
        if href.startswith(("data:", "javascript:")):
            continue
        if href.endswith((".js", ".css")) or "/assets/" in href:
            append_unique(urls, urljoin(base_url, href))
    return same_origin_only(base_url, urls)


def fetch_analyzer_assets(client: HttpClient, urls: list[str], *, max_assets: int) -> list[FetchResult]:
    results: list[FetchResult] = []
    for url in urls[:max_assets]:
        try:
            result = client.get(url)
        except Exception:
            continue
        content_type = result.content_type.lower()
        if "javascript" in content_type or "text/css" in content_type or result.final_url.endswith((".js", ".css")):
            results.append(result)
    return results


def same_origin_links(base_url: str, content: str) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    ranked: list[tuple[int, int, str]] = []
    for tag in soup.find_all("a", href=True):
        href = str(tag["href"]).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        text = " ".join(tag.stripped_strings)
        ranked.append((-link_relevance_score(href=href, text=text), len(ranked), urljoin(base_url, href)))
    ranked.sort()
    urls: list[str] = []
    for _, _, url in ranked:
        append_unique(urls, url)
    return same_origin_only(base_url, urls, preserve_query=True)


def link_relevance_score(*, href: str, text: str) -> int:
    haystack = f"{href} {text}".lower()
    score = 0
    for hint in GRADUATE_ROUTE_HINTS:
        if hint.lower() in haystack:
            score += 2
    if "document_srl=" in haystack:
        score += 1
    if any(part in haystack for part in LOW_VALUE_ROUTE_PARTS):
        score -= 10
    return score


def same_origin_only(base_url: str, urls: list[str], *, preserve_query: bool = False) -> list[str]:
    origin = urlparse(base_url).netloc
    results: list[str] = []
    for url in urls:
        parsed = urlparse(url)
        if parsed.netloc != origin:
            continue
        clean = parsed._replace(fragment="", query=parsed.query if preserve_query else "").geturl()
        append_unique(results, clean)
    return results


def known_file_refs(base_url: str, texts: list[str]) -> list[str]:
    refs: list[str] = []
    for text in texts:
        for url in same_origin_file_links(base_url=base_url, content=text, source_base_url=base_url):
            append_unique(refs, url)
        for ref in extract_file_refs(text):
            url = urljoin(base_url, ref)
            if is_probable_download_url(url):
                append_unique(refs, url)
    return same_origin_only(base_url, refs, preserve_query=True)


def is_probable_download_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path
    suffix = f".{path.rsplit('.', 1)[-1].lower()}" if "." in path else ""
    if suffix not in FILE_EXTENSIONS:
        return False
    lower_path = path.lower()
    noisy_tokens = (
        "!==",
        "&&",
        "||",
        "=",
        "{",
        "}",
        ";",
        ",",
        "(",
        ")",
        "[",
        "]",
        "window.",
        "document.",
        "this.doc",
        "contentwindow.doc",
    )
    return not any(token in lower_path for token in noisy_tokens)


def javascript_route_hints(text: str) -> list[str]:
    routes: list[str] = []
    for match in ROUTE_LIKE_RE.finditer(text):
        route = match.group(1)
        if "." in route.rsplit("/", 1)[-1]:
            continue
        if is_relevant_route(route):
            append_unique(routes, route)
    return routes


def classify_site(
    *,
    soup: BeautifulSoup,
    root_text: str,
    asset_urls: list[str],
    asset_texts: list[str],
    google_sheet_ids: list[str],
) -> tuple[str, str, float, dict[str, Any]]:
    visible_text = soup.get_text(" ", strip=True)
    module_scripts = soup.find_all("script", attrs={"type": "module"})
    root_nodes = soup.select("#root, #app, [data-reactroot]")
    asset_text = "\n".join(asset_texts[:3]).lower()
    asset_url_text = " ".join(asset_urls).lower()

    spa_score = 0
    if module_scripts:
        spa_score += 2
    if root_nodes:
        spa_score += 1
    if "/assets/" in asset_url_text or "vite" in root_text.lower():
        spa_score += 2
    if any(token in asset_text for token in ("react", "vue", "createelement", "jsx", "useeffect")):
        spa_score += 2
    if len(visible_text) < 1200 and len(asset_urls) >= 1:
        spa_score += 1
    if google_sheet_ids:
        spa_score += 1

    static_score = 0
    if len(visible_text) >= 1200:
        static_score += 2
    if len(soup.find_all("a", href=True)) >= 8:
        static_score += 1
    if not module_scripts and not root_nodes:
        static_score += 1

    evidence = {
        "visible_text_chars": len(visible_text),
        "asset_count": len(asset_urls),
        "fetched_asset_text_count": len(asset_texts),
        "module_script_count": len(module_scripts),
        "app_root_count": len(root_nodes),
        "google_sheet_count": len(google_sheet_ids),
        "spa_score": spa_score,
        "static_score": static_score,
    }

    if google_sheet_ids and spa_score >= static_score:
        return "vite_react_spa_with_google_sheets", "spa_with_google_sheets", confidence(spa_score, static_score), evidence
    if spa_score > static_score:
        return "vite_react_spa", "spa", confidence(spa_score, static_score), evidence
    return "static_html", "static_html", confidence(static_score, spa_score), evidence


def confidence(primary_score: int, secondary_score: int) -> float:
    gap = max(0, primary_score - secondary_score)
    return min(0.95, round(0.55 + gap * 0.1 + primary_score * 0.03, 2))


def recommend_routes(
    *,
    base_url: str,
    links: list[str],
    js_routes: list[str],
    adapter: str,
    max_routes: int,
) -> list[str]:
    routes: list[str] = []
    append_unique(routes, "/" if urlparse(base_url).path in ("", "/") else "./")

    for url in links:
        route = route_for_config(base_url, url)
        if route and is_relevant_route(route):
            append_unique(routes, route)
        if len(routes) >= max_routes:
            return routes

    for route in js_routes:
        append_unique(routes, route)
        if len(routes) >= max_routes:
            return routes

    if adapter.startswith("vite_react_spa") and len(routes) <= 1:
        for route in DEFAULT_SPA_ROUTES:
            append_unique(routes, route)
            if len(routes) >= max_routes:
                break
    return routes


def route_for_config(base_url: str, page_url: str) -> str:
    base = urlparse(base_url)
    page = urlparse(page_url)
    if page.netloc != base.netloc:
        return ""
    base_path = base.path if base.path.endswith("/") else f"{base.path}/"
    page_path = page.path or "/"
    query = f"?{page.query}" if page.query else ""
    if base_path in ("", "/"):
        return f"{page_path}{query}"
    if page_path == base_path.rstrip("/"):
        return query or ""
    if page_path.startswith(base_path):
        return f"{page_path.removeprefix(base_path)}{query}"
    return f"{page_path}{query}"


def is_relevant_route(route: str) -> bool:
    lowered = route.lower()
    if any(part in lowered for part in LOW_VALUE_ROUTE_PARTS):
        return False
    if "mid=" in lowered or "document_srl=" in lowered:
        return True
    if any(part in lowered for part in ("/wp-json", "/api/", "/assets/", "/static/", "/css/", "/js/")):
        return False
    if lowered.endswith(
        (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".ico",
            ".css",
            ".js",
            ".pdf",
            ".hwp",
            ".hwpx",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
        )
    ):
        return False
    return any(hint.lower() in lowered for hint in GRADUATE_ROUTE_HINTS) or route in {"", "/"}


def recommend_raw_options(adapter: str) -> dict[str, Any]:
    if adapter == "static_html":
        return {
            "max_pages": 80,
            "follow_html_links": True,
        }
    return {
        "render_routes": True,
        "render_timeout_ms": 10000,
        "render_wait_until": "domcontentloaded",
        "render_wait_after_ms": 1000,
        "render_stop_after_first_failure": True,
    }


def recommend_google_sheet_config(sheet_ids: list[str]) -> dict[str, Any]:
    if not sheet_ids:
        return {}
    return {
        "spreadsheet_id": sheet_ids[0],
        "sheets": [],
        "gviz_url_template": (
            "https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/"
            "tq?tqx=out:json&headers=1&sheet={sheet}"
        ),
        "document_mappings": {},
    }


def analyze_robots(client: HttpClient, base_url: str) -> tuple[str, str, list[str]]:
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        result = client.get(robots_url)
    except Exception:
        return robots_url, "missing_or_unreachable", []
    text = result.text
    if "text/html" in result.content_type.lower() and "<html" in text[:500].lower():
        return robots_url, "html_fallback", []
    sitemaps = []
    for line in text.splitlines():
        if line.lower().startswith("sitemap:"):
            sitemaps.append(line.split(":", 1)[1].strip())
    status = "valid" if "user-agent" in text.lower() or sitemaps else "unknown_text"
    return result.final_url, status, sitemaps


def analyze_sitemap(client: HttpClient, base_url: str, robot_sitemaps: list[str]) -> tuple[str, str]:
    candidates = robot_sitemaps or [urljoin(base_url, "/sitemap.xml")]
    last_url = candidates[0]
    for sitemap_url in candidates:
        last_url = sitemap_url
        try:
            result = client.get(sitemap_url)
        except Exception:
            continue
        text_start = result.text[:1000].lower()
        content_type = result.content_type.lower()
        if "text/html" in content_type and "<html" in text_start:
            return result.final_url, "html_fallback"
        if "<urlset" in text_start or "<sitemapindex" in text_start or "xml" in content_type:
            return result.final_url, "valid_xml"
        return result.final_url, "unknown_text"
    return last_url, "missing_or_unreachable"


def recommendation_notes(
    *,
    adapter: str,
    site_type: str,
    confidence: float,
    routes: list[str],
    known_files: list[str],
    robots_status: str,
    sitemap_status: str,
    google_sheet_ids: list[str],
    fetched_asset_count: int,
) -> tuple[list[str], list[str]]:
    notes = [
        f"Detected site_type={site_type}, adapter={adapter}, confidence={confidence}.",
        f"Recommended {len(routes)} initial route(s) and {len(known_files)} known file(s).",
    ]
    risks: list[str] = []
    if adapter.startswith("vite_react_spa"):
        notes.append("Use Playwright rendering for route pages; keep shell fallback enabled.")
        if fetched_asset_count == 0:
            risks.append("SPA assets were not fetched during analysis, so route/content detection is weak.")
    else:
        notes.append("Use static HTML crawling with bounded same-origin link following.")
    if google_sheet_ids:
        notes.append("Detected public Google Sheets references; sheet names and row mappings must be filled manually.")
    if robots_status != "valid":
        risks.append(f"robots.txt status is {robots_status}; verify crawling policy before large crawls.")
    if sitemap_status != "valid_xml":
        risks.append(f"sitemap status is {sitemap_status}; do not rely on sitemap-only crawling.")
    if len(routes) <= 1:
        risks.append("Few relevant routes were discovered; inspect menus or add routes manually before crawling.")
    return notes, risks


def append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def analysis_to_yaml(analysis: SiteAnalysis) -> str:
    return yaml.safe_dump(analysis.to_dict(), allow_unicode=True, sort_keys=False)


def analysis_to_json(analysis: SiteAnalysis) -> str:
    return json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2)
