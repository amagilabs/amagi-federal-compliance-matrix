"""Read a solicitation into pages of text lines.

PDFs go through pdfplumber's text layer. Plain .txt/.md files are accepted
too (form feed characters split pages), which is handy for text you already
pulled out of another tool. Running headers, footers and "Page X of Y" lines
are removed so they don't end up glued onto requirement sentences.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

SUPPORTED = (".pdf", ".txt", ".md")


class ExtractError(Exception):
    """The file could not be read (missing, wrong type, corrupt)."""


class NoTextError(ExtractError):
    """The PDF has no text layer (probably a scan)."""


@dataclass
class Document:
    path: Path
    pages: List[List[str]]
    sha256: str
    removed_lines: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)


_PAGE_NUM = re.compile(
    r"^\s*(?:page\s+)?\d{1,4}\s*(?:of\s+\d{1,4})?\s*$"
    r"|^\s*page\s+\d{1,4}(?:\s+of\s+\d{1,4})?\b.*$"
    r"|^.*\bpage\s+\d{1,4}\s+of\s+\d{1,4}\s*$"
    r"|^\s*-\s*\d{1,4}\s*-\s*$",
    re.IGNORECASE,
)


def _clean(line: str) -> str:
    line = line.replace(" ", " ").replace("\t", " ")
    # pdfplumber can emit (cid:NN) for glyphs with no unicode mapping.
    line = re.sub(r"\(cid:\d+\)", " ", line)
    return re.sub(r"\s{2,}", " ", line).strip()


def _strip_furniture(pages: List[List[str]]) -> tuple:
    """Drop page numbers and lines repeated at the top/bottom of many pages."""
    removed = 0
    if len(pages) >= 2:
        edge = Counter()
        for lines in pages:
            seen = set()
            for line in lines[:3] + lines[-3:]:
                key = re.sub(r"\d+", "#", line.lower())
                if key and key not in seen:
                    seen.add(key)
                    edge[key] += 1
        threshold = max(2, (len(pages) + 1) // 2)
        repeated = {k for k, n in edge.items() if n >= threshold}
    else:
        repeated = set()

    out = []
    for lines in pages:
        kept = []
        for i, line in enumerate(lines):
            at_edge = i < 3 or i >= len(lines) - 3
            key = re.sub(r"\d+", "#", line.lower())
            if at_edge and (key in repeated or _PAGE_NUM.match(line)):
                removed += 1
                continue
            kept.append(line)
        out.append(kept)
    return out, removed


def _read_pdf(path: Path) -> List[List[str]]:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ExtractError("pdfplumber is not installed") from exc
    pages: List[List[str]] = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append([_clean(l) for l in text.splitlines() if _clean(l)])
    except Exception as exc:  # pdfminer raises a zoo of exception types
        raise ExtractError(f"could not read PDF: {exc.__class__.__name__}: {exc}") from exc
    return pages


def _read_text(path: Path) -> List[List[str]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    chunks = raw.split("\f")
    return [[_clean(l) for l in chunk.splitlines() if _clean(l)] for chunk in chunks]


def load(path) -> Document:
    path = Path(path)
    if not path.exists():
        raise ExtractError(f"file not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ExtractError(
            f"unsupported file type '{suffix}' (use .pdf or .txt; save Word files as PDF first)"
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    pages = _read_pdf(path) if suffix == ".pdf" else _read_text(path)
    total_chars = sum(len(l) for p in pages for l in p)
    if suffix == ".pdf" and total_chars < 20 * max(1, len(pages)) and total_chars < 200:
        raise NoTextError(
            f"{path.name} has no usable text layer ({len(pages)} pages, {total_chars} characters). "
            "It is probably a scan: run OCR first (for example `ocrmypdf in.pdf out.pdf`)."
        )
    pages, removed = _strip_furniture(pages)
    doc = Document(path=path, pages=pages, sha256=digest, removed_lines=removed)
    empty = [i + 1 for i, p in enumerate(pages) if not p]
    if empty and suffix == ".pdf" and len(empty) < len(pages):
        doc.warnings.append(
            "no text on page(s) " + ", ".join(map(str, empty[:10]))
            + (" ..." if len(empty) > 10 else "") + " (scanned pages are skipped)"
        )
    return doc
