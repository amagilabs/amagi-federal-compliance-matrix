"""Turn page lines into sentences that know their section and page.

The walk is line by line and keeps three pieces of state: the current
section number (``L.4.2``, ``C.3``, ``3.1``), the current Uniform Contract
Format section letter (``SECTION L`` -> ``L``), and whether we are inside a
list that hangs off a lead-in such as "The Contractor shall:". List items
come out as their own sentences with the lead-in attached, so each one gets
its own row in the matrix.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from .extract import Document


@dataclass
class Sentence:
    text: str
    page_start: int
    page_end: int
    section: str = ""
    section_title: str = ""
    ucf: str = ""
    leadin: str = ""
    marker: str = ""


# --- line classifiers -------------------------------------------------------

_DOT_LEADER = re.compile(r"(?:\.\s?){4,}\s*\d{1,4}\s*$|\s(?:_\s?){4,}\s*\d{1,4}\s*$")
_TOC_START = re.compile(r"^(?:table of contents|contents)$", re.IGNORECASE)
_ENDS_WITH_PAGE = re.compile(r"\s\d{1,4}$")

_UCF = re.compile(
    r"^SECTION\s+(?P<letter>[A-M])\b(?:\s*[-–—:.]\s*|\s+)?(?P<title>[A-Z][A-Z0-9 ,&/'()\-–—]*)?$"
    r"|^Section\s+(?P<letter2>[A-M])\s*[-–—:]\s*(?P<title2>[A-Z].{0,90})$"
)
_PART = re.compile(r"^PART\s+(?:[IVX]{1,4}|\d{1,2})\b(?:\s*[-–—:.]\s*.*)?$")
_ATTACH = re.compile(
    r"^(?P<kind>ATTACHMENT|EXHIBIT|APPENDIX|Attachment|Exhibit|Appendix)\s+(?P<id>[A-Z]|\d{1,3})\b"
    r"\s*(?:[-–—:.]\s*(?P<title>.{0,90}))?$"
)
_NUMBERED = re.compile(
    r"^(?P<num>(?:[A-M]\.)?\d{1,2}(?:\.\d{1,3}){0,5})(?P<dot>\.?)\s+(?P<rest>[A-Z(\"“].*)$"
)
_MARKER = re.compile(
    r"^(?P<m>\((?:[a-z]{1,2}|[ivx]{1,5}|\d{1,2})\)|(?:[a-z]|\d{1,2})[.)]|[•▪●◦‣⁃∙*\-–])\s+(?P<rest>\S.*)$"
)
_TERMINAL = re.compile(r"[.;:!?][\"'”)]*$|\band$|\bor$")

_MODAL = re.compile(r"(?<![-\w])(?:shall|must|will|required|should)\b", re.IGNORECASE)


def _is_title(text: str) -> bool:
    """A short heading such as 'Technical Volume' or 'SCOPE OF WORK'."""
    t = text.strip()
    if not t or len(t) > 90 or _MODAL.search(t):
        return False
    if t.endswith((".", ";", ",")) and not t.isupper():
        return len(t.split()) <= 6 and t[:-1].istitle()
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", t)
    if not words:
        return False
    if t.isupper():
        return True
    small = {"a", "an", "and", "the", "of", "for", "to", "in", "on", "or", "by", "with", "at"}
    caps = sum(1 for w in words if w[0].isupper() or w.lower() in small)
    return caps == len(words) and len(words) <= 12


# --- sentence splitting -----------------------------------------------------

_ABBREV = {
    "mr", "mrs", "ms", "dr", "no", "nos", "inc", "corp", "co", "ltd", "llc", "u.s", "u.s.c", "e.g",
    "i.e", "etc", "al", "a.m", "p.m", "sec", "secs", "para", "paras", "approx", "vs", "st", "fig",
    "vol", "vols", "rev", "att", "ref", "exh", "cf", "jan", "feb", "mar", "apr", "jun", "jul",
    "aug", "sep", "sept", "oct", "nov", "dec", "pt", "ch", "art", "subpt", "est", "min", "max",
}
_SPLIT = re.compile(r"[.!?][\"'”)\]]*\s+(?=[A-Z0-9(\"“‘'])")


def split_sentences(text: str) -> List[Tuple[int, str]]:
    """Split text into (offset, sentence) pairs, keeping abbreviations intact."""
    out: List[Tuple[int, str]] = []
    start = 0
    for m in _SPLIT.finditer(text):
        before = text[start:m.start() + 1]
        token = re.search(r"([A-Za-z.]+)\.$", before)
        if token:
            raw = token.group(1).rstrip(".")
            word = raw.lower()
            if word in _ABBREV or (len(raw) == 1 and raw.islower()):
                continue
        piece = text[start:m.end()].strip()
        if piece:
            out.append((start, piece))
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append((start, tail))
    return out


_INLINE_ITEM = re.compile(r"(?:(?<=\s)|^)\((?P<m>[a-z]|[ivx]{1,4}|\d{1,2})\)\s+")


def split_inline_list(sentence: str) -> Optional[Tuple[str, List[Tuple[str, str]]]]:
    """'The Contractor shall: (a) x; (b) y; and (c) z.' -> lead-in + items.

    Only splits when the markers run in sequence (a, b, c or 1, 2, 3 or
    i, ii, iii) after a colon, so a stray '(a)' cross reference is left alone.
    """
    colon = sentence.find(":")
    if colon < 0:
        return None
    head, body = sentence[: colon + 1].strip(), sentence[colon + 1:]
    marks = list(_INLINE_ITEM.finditer(body))
    if len(marks) < 2 or body[: marks[0].start()].strip():
        return None
    labels = [m.group("m") for m in marks]
    seqs = [
        [chr(ord("a") + i) for i in range(len(labels))],
        [str(i + 1) for i in range(len(labels))],
        ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"][: len(labels)],
    ]
    if labels not in seqs:
        return None
    items = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        items.append((f"({m.group('m')})", body[m.end():end].strip()))
    return head, items


# --- the walk ---------------------------------------------------------------


class _Buffer:
    def __init__(self) -> None:
        self.parts: List[Tuple[str, int]] = []

    def add(self, text: str, page: int) -> None:
        self.parts.append((text, page))

    def __bool__(self) -> bool:
        return bool(self.parts)

    def text(self) -> str:
        out = ""
        for text, _ in self.parts:
            if out.endswith("-") and not out.endswith(" -") and text[:1].islower():
                out = out[:-1] + text  # re-join a word hyphenated across lines
            else:
                out = f"{out} {text}" if out else text
        return out

    def page_at(self, offset: int) -> int:
        pos = 0
        page = self.parts[0][1]
        for text, p in self.parts:
            if pos > offset:
                break
            page = p
            pos += len(text) + 1
        return page

    def last_page(self) -> int:
        return self.parts[-1][1]

    def ends_terminal(self) -> bool:
        return bool(self.parts) and bool(_TERMINAL.search(self.parts[-1][0]))


def walk(doc: Document) -> List[Sentence]:
    out: List[Sentence] = []
    section = ""
    title = ""
    ucf = ""
    leadin = ""  # active list lead-in
    item_marker = ""  # marker of the list item in the buffer, if any
    in_toc = False
    buf = _Buffer()

    def emit(sentence_text: str, p0: int, p1: int, marker: str = "", lead: str = "") -> None:
        out.append(
            Sentence(
                text=sentence_text, page_start=p0, page_end=max(p0, p1), section=section,
                section_title=title, ucf=ucf, leadin=lead, marker=marker,
            )
        )

    def flush() -> None:
        """Emit what the buffer holds. Returns nothing; may set the lead-in."""
        nonlocal leadin, item_marker
        if not buf:
            return
        text = buf.text()
        pieces = split_sentences(text)
        if item_marker:
            for i, (off, s) in enumerate(pieces):
                emit(s, buf.page_at(off), buf.last_page(), item_marker if i == 0 else "", leadin)
            last = pieces[-1][1] if pieces else ""
            if last.endswith(":"):
                # nested lead-in such as "(b) for each server:" -> keep both levels
                leadin = f"{leadin} {item_marker} {last}".strip()
        else:
            for i, (off, s) in enumerate(pieces):
                is_last = i == len(pieces) - 1
                if is_last and s.endswith(":") and _MODAL.search(s):
                    leadin = s  # held back: the list items that follow carry it
                    out.append(Sentence(s, buf.page_at(off), buf.last_page(), section, title, ucf, "", "LEADIN"))
                else:
                    emit(s, buf.page_at(off), buf.last_page())
                    if is_last and s.endswith(":"):
                        leadin = s
                        out[-1].marker = "LEADIN-SOFT"
        buf.parts.clear()
        item_marker = ""

    def end_list() -> None:
        nonlocal leadin
        leadin = ""

    for page_no, lines in enumerate(doc.pages, start=1):
        for line in lines:
            if _DOT_LEADER.search(line):
                continue
            if _TOC_START.match(line):
                flush()
                in_toc = True
                continue
            if in_toc:
                if _ENDS_WITH_PAGE.search(line):
                    continue
                in_toc = False

            m = _UCF.match(line)
            if m:
                flush(); end_list()
                ucf = m.group("letter") or m.group("letter2")
                section = ucf
                title = (m.group("title") or m.group("title2") or "").strip(" -–—:.")
                continue
            if _PART.match(line):
                flush(); end_list()
                continue
            m = _ATTACH.match(line)
            if m and (m.group("title") is None or _is_title(m.group("title") or "")):
                flush(); end_list()
                section = f"{m.group('kind').title()} {m.group('id')}"
                title = (m.group("title") or "").strip()
                ucf = "J"
                continue

            m = _NUMBERED.match(line)
            if m:
                num, dot, rest = m.group("num"), m.group("dot"), m.group("rest")
                lettered = num[0].isalpha()
                structured = "." in num  # 3.1, L.4, C.3.2
                heading_like = _is_title(rest)
                mid_sentence = bool(buf) and not buf.ends_terminal()
                if (structured or (dot and heading_like)) and not (mid_sentence and not heading_like and not lettered):
                    flush(); end_list()
                    if lettered:
                        ucf = num[0]
                    section = num
                    if heading_like:
                        title = rest.rstrip(".")
                    else:
                        head = re.match(r"^([A-Z][^.:]{0,80})[.:]\s+(?=[A-Z])", rest)
                        title = head.group(1) if head and _is_title(head.group(1)) else ""
                        buf.add(rest, page_no)
                    continue

            m = _MARKER.match(line)
            if m and (leadin or item_marker or m.group("m")[0] in "(•▪●◦*-–"):
                flush()
                item_marker = m.group("m")
                buf.add(m.group("rest"), page_no)
                continue

            if item_marker and buf.ends_terminal() and line[:1].isupper():
                # the list item finished; this is a new paragraph
                flush(); end_list()
            buf.add(line, page_no)
        # page break: keep the buffer (sentences run across pages)
    flush()
    return _expand(out)


def _expand(sentences: Iterable[Sentence]) -> List[Sentence]:
    """Drop lead-ins that have items, split inline (a)/(b)/(c) lists."""
    sentences = list(sentences)
    result: List[Sentence] = []
    for i, s in enumerate(sentences):
        if s.marker in ("LEADIN", "LEADIN-SOFT"):
            has_items = i + 1 < len(sentences) and sentences[i + 1].leadin.startswith(s.text)
            if s.marker == "LEADIN" and not has_items:
                s.marker = ""
                result.append(s)
            elif s.marker == "LEADIN-SOFT":
                s.marker = ""
                result.append(s)
            continue
        if not s.leadin:
            split = split_inline_list(s.text)
            if split and _MODAL.search(split[0]):
                head, items = split
                for marker, body in items:
                    result.append(Sentence(body, s.page_start, s.page_end, s.section, s.section_title, s.ucf, head, marker))
                continue
        result.append(s)
    return result
