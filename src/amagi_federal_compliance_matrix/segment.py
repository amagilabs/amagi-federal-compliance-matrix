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
    role: str = ""  # "leadin" when list items follow and carry this sentence


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
    r"^(?P<kind>ATTACHMENT|EXHIBIT|APPENDIX|Attachment|Exhibit|Appendix)\s+(?P<id>[A-Z](?:-\d{1,3})?|\d{1,3})\b"
    r"\s*(?:[-–—:.]\s*(?P<title>.{0,90}))?$"
)
_NUMBERED = re.compile(
    r"^(?P<num>(?:[A-M]\.)?\d{1,2}(?:\.\d{1,3}){0,5})(?P<dot>\.?)\s+(?P<rest>[A-Z(\"“].*)$"
)
_MARKER = re.compile(
    r"^(?P<m>\((?:[a-z]{1,2}|[ivx]{1,5}|\d{1,2})\)|(?:[a-z]|\d{1,2})[.)]|[•▪●◦‣⁃∙*\-–])\s+(?P<rest>\S.*)$"
)
_TERMINAL = re.compile(r"[.;:!?][\"'”)]*$|[;,]\s*(?:and|or)$")

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


def _ends_leadin(s: str) -> bool:
    s = s.rstrip()
    return s.endswith(":") or (s.endswith(("-", "—", "–")) and not s.endswith("--") and len(s) > 20)


def _marker_types(marker: str) -> Tuple[str, ...]:
    """Possible list levels for a marker: '(a)' alpha, '(1)' num, '(ii)' roman, '•' bullet."""
    paren = marker.startswith("(")
    core = marker.strip("().")
    if not core or not core[0].isalnum():
        return ("bullet",)
    style = "p" if paren else "d"
    if core.isdigit():
        return (f"num{style}",)
    if re.fullmatch(r"[ivx]+", core):
        if len(core) == 1:
            return (f"roman{style}", f"alpha{style}") if core == "i" else (f"alpha{style}", f"roman{style}")
        return (f"roman{style}",)
    return (f"alpha{style}",)


class _Level:
    def __init__(self, text: str, own: Tuple[str, ...] = ()) -> None:
        self.text = text  # the lead-in that items at this level hang from
        self.own = own  # marker types of the list item that opened it, if any
        self.child: Optional[str] = None  # marker type of the items, once seen


def walk(doc: Document) -> List[Sentence]:
    out: List[Sentence] = []
    section = ""
    title = ""
    ucf = ""
    levels: List[_Level] = []  # open list lead-ins, outermost first
    item_marker = ""  # marker of the list item in the buffer, if any
    item_leadin = ""  # lead-in of that item
    item_types: Tuple[str, ...] = ()
    in_toc = False
    buf = _Buffer()

    def emit(text: str, p0: int, p1: int, marker: str = "", lead: str = "", role: str = "") -> None:
        out.append(
            Sentence(
                text=text, page_start=p0, page_end=max(p0, p1), section=section,
                section_title=title, ucf=ucf, leadin=lead, marker=marker, role=role,
            )
        )

    def flush() -> None:
        nonlocal item_marker, item_leadin, item_types
        if not buf:
            return
        pieces = split_sentences(buf.text())
        for i, (off, s) in enumerate(pieces):
            first = i == 0
            last = i == len(pieces) - 1
            marker = item_marker if first else ""
            lead = item_leadin if first else ""
            role = ""
            if last and _ends_leadin(s):
                role = "leadin" if _MODAL.search(s) or (lead and _MODAL.search(lead)) else "soft"
            emit(s, buf.page_at(off), buf.last_page(), marker, lead, role)
            if role:
                parent = f"{lead} {marker}".strip() if first else ""
                levels.append(_Level(f"{parent} {s}".strip(), item_types if first else ()))
        buf.parts.clear()
        item_marker, item_leadin, item_types = "", "", ()

    def end_list() -> None:
        levels.clear()

    def open_item(marker: str) -> str:
        """Find the lead-in a new list item belongs to, closing deeper levels."""
        types = _marker_types(marker)
        while levels:
            top = levels[-1]
            if top.child is None:
                if top.own and types[0] in top.own:
                    # "(a) ... as follows:" then "(b)": a sibling of the item that opened the level
                    levels.pop()
                    continue
                top.child = types[0]
                return top.text
            if top.child in types:
                return top.text
            levels.pop()
        return ""

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
            if m and (not buf or buf.ends_terminal()) and (
                    m.group("title") is None or _is_title(m.group("title") or "")):
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
                # "1. Section I - General Information" inside L.4.2.1 is a list item, not a new section
                nested = not structured and bool(re.match(r"^[A-M]\.\d", section or ""))
                if (structured or (dot and heading_like)) and not nested and not (
                        mid_sentence and not heading_like and not lettered):
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
            if m and (levels or item_marker or m.group("m")[0] in "(•▪●◦*-–"):
                flush()
                item_marker = m.group("m")
                item_types = _marker_types(item_marker)
                item_leadin = open_item(item_marker)
                buf.add(m.group("rest"), page_no)
                continue

            if (not buf or buf.ends_terminal()) and _is_title(line) and not _TERMINAL.search(line):
                # an unnumbered heading line such as "Notice to Offerors - Contents Review"
                flush()
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
        if s.role == "leadin":
            nxt = sentences[i + 1] if i + 1 < len(sentences) else None
            if nxt is not None and nxt.leadin and nxt.leadin.endswith(s.text):
                continue  # its items carry it
        if not s.leadin:
            split = split_inline_list(s.text)
            if split and _MODAL.search(split[0]):
                head, items = split
                lead = f"{s.marker} {head}".strip()
                for marker, body in items:
                    result.append(Sentence(body, s.page_start, s.page_end, s.section, s.section_title, s.ucf, lead, marker))
                continue
        result.append(s)
    return result
