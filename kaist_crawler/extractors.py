from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup

from .models import Chunk, Document
from .store import stable_id


FILE_REF_RE = re.compile(
    r"""(?P<url>(?:https?://[^"'`<>()\s]+|/[^"'`<>()\s]+|(?:\.{1,2}/)?[^"'`<>()\s]+)\.(?:pdf|hwp|hwpx|docx?|xlsx?|pptx?)(?:\?[^"'`<>()\s]*)?)""",
    re.IGNORECASE,
)
KOREAN_RE = re.compile(r"[\uac00-\ud7a3]")
NOISY_FILE_REF_PARTS = (
    "document.doc",
    "window.document",
    "ownerdocument",
)


def html_to_text(content: str) -> tuple[str, str]:
    soup = BeautifulSoup(content, "html.parser")
    title = " ".join(soup.title.stripped_strings) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = normalize_text(text)
    return title, text


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def extract_file_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in FILE_REF_RE.finditer(text):
        value = match.group("url").rstrip(".,);]")
        if not _is_probable_file_ref(value):
            continue
        if value not in refs:
            refs.append(value)
    return refs


def _is_probable_file_ref(value: str) -> bool:
    lower = value.lower()
    if any(part in lower for part in NOISY_FILE_REF_PARTS):
        return False
    if value.startswith(("http://", "https://", "/", "./", "../")):
        return True
    if "/" in value:
        return True
    suffix = Path(value.split("?", 1)[0]).suffix.lower()
    if suffix in {".pdf", ".hwp", ".hwpx", ".ppt", ".pptx", ".xls", ".xlsx"}:
        return True
    return suffix in {".doc", ".docx"} and len(value) > len("document.doc")


def js_literal_text(content: str) -> str:
    candidates: list[str] = []
    candidates.extend(re.findall(r"`([^`]{4,4000})`", content, flags=re.DOTALL))
    candidates.extend(_json_string_literals(content))
    useful = []
    seen = set()
    for candidate in candidates:
        candidate = candidate.replace("\\n", "\n").replace("\\r", "\n")
        candidate = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), candidate)
        candidate = normalize_text(candidate)
        if not _is_meaningful_literal(candidate):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        useful.append(candidate)
    return "\n\n".join(useful)


def _json_string_literals(content: str) -> Iterable[str]:
    for match in re.finditer(r'"((?:\\.|[^"\\]){4,2000})"', content, flags=re.DOTALL):
        raw = match.group(0)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, str):
            yield value


def _is_meaningful_literal(value: str) -> bool:
    if len(value) < 12:
        return False
    if KOREAN_RE.search(value):
        return True
    if len(value) >= 30 and re.search(r"[A-Za-z]{3,}\s+[A-Za-z]{3,}", value):
        noisy = ("function", "return", "className", "react", "document.", "window.")
        return not any(token in value for token in noisy)
    return False


def pdf_to_text(path: str | Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError:
            return ""
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return normalize_text("\n".join(parts))


def chunk_documents(
    documents: list[Document],
    *,
    chunk_size: int = 900,
    overlap: int = 120,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        text = document.text.strip()
        if not text:
            continue
        start = 0
        index = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            if end < len(text):
                boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
                if boundary > start + chunk_size // 2:
                    end = boundary + 1
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_id = f"{document.doc_id}:{index}:{stable_id(chunk_text)[:12]}"
                metadata = dict(document.metadata)
                metadata.update(
                    {
                        "title": document.title,
                        "raw_path": document.raw_path or "",
                    }
                )
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        doc_id=document.doc_id,
                        site=document.site,
                        source_url=document.source_url,
                        text=chunk_text,
                        chunk_index=index,
                        metadata=metadata,
                    )
                )
                index += 1
            if end >= len(text):
                break
            start = max(0, end - overlap)
    return chunks
