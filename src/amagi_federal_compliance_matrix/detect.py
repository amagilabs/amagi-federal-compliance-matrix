"""Decide which sentences are requirements, and who each one binds.

A sentence is a requirement when it carries an obligation keyword (shall,
must, will, is/are required, required to; optionally should). Each one gets
the keyword, a kind (Requirement, Prohibition, Desirable, Government) and an
actor (Offeror, Contractor, Government, Unclear). The actor comes from the
nearest subject noun before the keyword; when there isn't one, the Uniform
Contract Format section decides (Section L binds the offeror, Section C the
contractor, "will" in Section M is the Government describing evaluation).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from .segment import Sentence

_KEYWORD = re.compile(
    r"(?<![-\w])(?P<kw>shall\s+not|shall|must\s+not|must|will\s+not|will|should\s+not|should"
    r"|(?:is|are|be|been|was|were|not|also|hereby)\s+(?:\w+\s+)?required\b(?:\s+to)?"
    r"|required\s+to)\b",
    re.IGNORECASE,
)
_DEFINITION = re.compile(
    r"^[\"'“‘]?[\w\s\-'’]{1,60}[\"'”’]?\s*(?:,\s*as used [^,]+,\s*)?"
    r"(?:shall|will)\s+(?:mean|refer to|be defined as|include)\b",
    re.IGNORECASE,
)
CLAUSE_RE = re.compile(r"\b(?:\d{0,2}52)\.\d{3}-\d{1,4}\b")
_CLAUSE_TITLE = re.compile(
    r"(?P<num>\b(?:\d{0,2}52)\.\d{3}-\d{1,4})\b,?\s+(?P<title>[A-Z][^()]{3,160}?)\s*"
    r"\((?P<date>[A-Z][A-Za-z]{2,4}\.?\s*\d{4})\)"
)

GOVERNMENT = [
    "government", "contracting officer", "contracting officer's representative", "cor", "cotr",
    "co", "ko", "agency", "department", "buyer", "purchaser", "owner", "county", "city", "state",
    "commonwealth", "university", "district", "authority", "commission", "board", "purchasing",
    "procurement office", "issuing office", "evaluation team", "evaluation board", "evaluators",
    "source selection authority", "ssa", "sseb", "pco", "aco", "we", "us",
]
OFFEROR = [
    "offeror", "offerors", "offeror's", "quoter", "quoters", "bidder", "bidders", "proposer",
    "proposers", "respondent", "respondents", "applicant", "applicants", "proposal", "proposals",
    "quote", "quotes", "quotation", "quotations", "bid", "bids", "submission", "submissions",
    "response", "responses", "offer", "offers", "volume", "volumes", "you", "your", "resume",
    "resumes", "cover letter", "narrative", "page limit", "competitor", "competitors",
    "prospective contractor",
]
CONTRACTOR = [
    "contractor", "contractors", "contractor's", "awardee", "subcontractor", "subcontractors",
    "prime", "provider", "service provider", "personnel", "staff", "employee", "employees",
    "key personnel", "program manager", "project manager", "team", "deliverable", "deliverables",
    "report", "reports", "invoice", "invoices", "system", "solution", "software", "services",
    "work", "transition", "help desk",
]
# Nouns that bind whoever is writing the document part: offeror in L, contractor elsewhere.
AMBIGUOUS = [
    "vendor", "vendors", "supplier", "suppliers", "consultant", "consultants", "firm", "firms",
    "plan", "plans", "approach", "past performance",
]
_GOV_PASSIVE = re.compile(
    r"^\s*(?:\w+\s+)?be\s+(?:evaluated|assessed|rated|scored|reviewed|considered|awarded|made|"
    r"issued|posted|notified|determined|selected|used|conducted|ranked|compared)\b",
    re.IGNORECASE,
)

UCF_OFFEROR = {"K", "L"}
UCF_CONTRACTOR = {"B", "C", "D", "E", "F", "G", "H", "I", "J"}


@dataclass
class Requirement:
    id: str
    section: str
    section_title: str
    ucf: str
    page_start: int
    page_end: int
    keyword: str
    kind: str
    actor: str
    text: str
    refs: List[str] = field(default_factory=list)
    responses: Dict[str, str] = field(default_factory=dict)
    change: str = ""
    previous_text: str = ""

    @property
    def page(self) -> str:
        if self.page_end and self.page_end != self.page_start:
            return f"{self.page_start}-{self.page_end}"
        return str(self.page_start)

    def as_dict(self) -> dict:
        d = {
            "id": self.id, "section": self.section, "section_title": self.section_title,
            "ucf": self.ucf, "page": self.page, "keyword": self.keyword, "kind": self.kind,
            "actor": self.actor, "requirement": self.text, "refs": self.refs,
        }
        if self.responses:
            d["responses"] = dict(self.responses)
        if self.change:
            d["change"] = self.change
            d["previous_text"] = self.previous_text
        return d


@dataclass
class Clause:
    number: str
    title: str = ""
    date: str = ""
    pages: List[int] = field(default_factory=list)


@dataclass
class Options:
    include_will: bool = True
    include_should: bool = False
    offeror_only: bool = False
    skip_ucf: Sequence[str] = ()
    government_names: Sequence[str] = ()


def _phrase_regex(words: Iterable[str]) -> re.Pattern:
    alts = sorted({re.escape(w) for w in words}, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b", re.IGNORECASE)


# a preposition, then an optional article and capitalised name words: "filed with the Government
# Accountability Office (" is the object of "with", so "GAO" after it is not the subject either
_OBJECT_OF = re.compile(
    r"\b(?:to|for|with|from|by|on|upon|of|at|into|through|via|To|For|With|From|By|On|Upon|At)\s+"
    r"(?:the\s+|a\s+|an\s+|any\s+|each\s+|The\s+)?(?:[A-Z][\w'’&\-]*\s+(?:of\s+|and\s+|for\s+)?)*\(?$"
)


def _nearest(text: str, patterns: Dict[str, re.Pattern]) -> Optional[str]:
    """Label of the last subject-like mention in text.

    A Government mention right after a preposition ("filed with the GAO",
    "submit to the Contracting Officer") is an object, not the subject.
    """
    best, where = None, -1
    for label, pat in patterns.items():
        for m in pat.finditer(text):
            if label == "Government" and _OBJECT_OF.search(text[: m.start()]):
                continue
            if m.end() > where:
                best, where = label, m.end()
    return best


def classify_actor(subject: str, keyword: str, ucf: str, gov_extra: Sequence[str] = (), after: str = "") -> str:
    """Pick the actor from the words in front of the keyword."""
    kw = keyword.lower()
    if kw == "will" and _GOV_PASSIVE.match(after) and not re.search(
        r"\b(?:contractor|offeror|vendor|bidder|quoter)s?\b", " ".join(subject.split()[-6:]), re.IGNORECASE
    ) or (kw == "will" and _GOV_PASSIVE.match(after) and ucf == "M"):
        return "Government"
    pats = {
        "Government": _phrase_regex(list(GOVERNMENT) + list(gov_extra)),
        "Offeror": _phrase_regex(OFFEROR),
        "Contractor": _phrase_regex(CONTRACTOR),
        "Ambiguous": _phrase_regex(AMBIGUOUS),
    }
    # Only the clause that owns the keyword: text after the last comma/semicolon/colon
    # unless that leaves nothing (e.g. "If awarded, the contractor shall").
    tail = re.split(r"[;:]|,\s(?=(?:and|or|but|which|unless|except)\b)", subject)[-1]
    if tail.strip():
        subject = tail
    words = subject.split()
    window = " ".join(words[-10:])
    actor = _nearest(window, pats)
    if ucf == "M" and kw.startswith("will") and actor in ("Contractor", "Ambiguous"):
        # Section M describes the evaluation: "the team will verify", "the approach will be"
        return "Government"
    if actor == "Ambiguous":
        actor = "Offeror" if ucf in UCF_OFFEROR or ucf == "M" else "Contractor"
    if actor:
        return actor
    if ucf in UCF_OFFEROR:
        return "Offeror"
    if ucf == "M":
        return "Government" if kw.startswith("will") else "Offeror"
    if ucf in UCF_CONTRACTOR:
        return "Contractor"
    return "Unclear"


def _kind(keyword: str, actor: str) -> str:
    kw = keyword.lower()
    if actor == "Government":
        return "Government"
    if kw.startswith("should"):
        return "Desirable"
    if kw.endswith(" not") or kw.startswith("not "):
        return "Prohibition"
    return "Requirement"


def _norm_kw(raw: str) -> str:
    kw = re.sub(r"\s+", " ", raw.lower()).strip()
    if "required" in kw:
        return "not required" if re.search(r"(?:^|\s)not\s", kw) else "required"
    return kw


def detect(sentences: Iterable[Sentence], opts: Optional[Options] = None) -> List[Requirement]:
    opts = opts or Options()
    skip = {u.upper() for u in opts.skip_ucf}
    reqs: List[Requirement] = []
    counters: Dict[str, int] = {}
    for s in sentences:
        if s.ucf and s.ucf.upper() in skip:
            continue
        body = s.text
        found = _KEYWORD.search(body)
        subject_text = body[: found.start()] if found else ""
        if not found and s.leadin:
            found = _KEYWORD.search(s.leadin)
            subject_text = s.leadin[: found.start()] if found else ""
        if not found:
            continue
        if _DEFINITION.match(body):
            continue
        keyword = _norm_kw(found.group("kw"))
        if keyword.startswith("should") and not opts.include_should:
            # a later shall/must in the same sentence still counts
            later = [m for m in _KEYWORD.finditer(body) if not m.group("kw").lower().startswith("should")]
            if not later:
                continue
            found = later[0]
            keyword = _norm_kw(found.group("kw"))
            subject_text = body[: found.start()]
        if keyword.startswith("will") and not opts.include_will:
            later = [m for m in _KEYWORD.finditer(body) if not m.group("kw").lower().startswith(("will", "should"))]
            if not later:
                continue
            found = later[0]
            keyword = _norm_kw(found.group("kw"))
            subject_text = body[: found.start()]
        if keyword == "not required":
            continue
        after = (body if body.startswith(subject_text) else s.leadin)[len(subject_text) + len(found.group(0)):][:60]
        actor = classify_actor(subject_text, keyword, s.ucf, opts.government_names, after)
        if opts.offeror_only and actor not in ("Offeror", "Unclear"):
            continue
        text = f"{s.leadin} {s.marker} {body}".strip() if s.leadin else (f"{s.marker} {body}".strip() if s.marker else body)
        text = re.sub(r"\s{2,}", " ", text)
        refs = sorted(set(CLAUSE_RE.findall(text)), key=_clause_key)
        sec = s.section or "Doc"
        counters[sec] = counters.get(sec, 0) + 1
        reqs.append(
            Requirement(
                id=f"{sec}-{counters[sec]:02d}", section=s.section, section_title=s.section_title,
                ucf=s.ucf, page_start=s.page_start, page_end=s.page_end, keyword=keyword,
                kind=_kind(keyword, actor), actor=actor, text=text, refs=refs,
            )
        )
    return reqs


def _clause_key(num: str):
    head, tail = num.split("-", 1)
    a, b = head.split(".", 1)
    return (int(a), int(b), int(tail))


_ABBR = re.compile(r"((?:\b(?:of|for|on|and|the|[A-Z][\w&\-]*)\s+){1,8})\((?P<abbr>[A-Z][A-Za-z]{1,7})\)")
_AGENCY_WORDS = {
    "department", "office", "agency", "administration", "bureau", "service", "command", "commission",
    "corps", "authority", "directorate", "division", "ministry", "secretary",
}
_SMALL = {"of", "for", "on", "and", "the"}


def government_names(pages: Sequence[Sequence[str]]) -> List[str]:
    """Abbreviations a solicitation defines for government bodies, e.g. "Department of Energy (DOE)".

    The name must start or end with an agency word and its initials must spell
    the abbreviation, so "Product and Service Code (PSC)" is not picked up.
    """
    text = " ".join(line for lines in pages for line in lines)
    names: List[str] = []
    for m in _ABBR.finditer(text):
        abbr = m.group("abbr")
        if sum(c.isupper() for c in abbr) < 2:
            continue
        words = m.group(1).split()
        while words and words[0] in _SMALL:
            words.pop(0)
        for start in range(len(words)):
            name = words[start:]
            if name[0] in _SMALL:
                continue
            if name[0].lower() not in _AGENCY_WORDS and name[-1].lower() not in _AGENCY_WORDS:
                continue
            caps = "".join(w[0] for w in name if w not in _SMALL)
            full = "".join(w[0] for w in name if w != "the")
            if abbr.upper() in (caps.upper(), full.upper()):
                if abbr not in names:
                    names.append(abbr)
                break
    return names


def find_clauses(pages: Sequence[Sequence[str]]) -> List[Clause]:
    """Every FAR/DFARS/agency-supplement clause number mentioned, with its title when listed."""
    found: Dict[str, Clause] = {}
    for page_no, lines in enumerate(pages, start=1):
        text_lines = list(lines)
        for i, line in enumerate(text_lines):
            joined = line if i + 1 >= len(text_lines) else f"{line} {text_lines[i + 1]}"
            for m in CLAUSE_RE.finditer(line):
                c = found.setdefault(m.group(0), Clause(m.group(0)))
                if page_no not in c.pages:
                    c.pages.append(page_no)
            for m in _CLAUSE_TITLE.finditer(joined):
                if m.start() >= len(line):
                    continue
                c = found.setdefault(m.group("num"), Clause(m.group("num")))
                if not c.title:
                    title = re.sub(r"\s+", " ", m.group("title")).strip(" ,.-")
                    if not _KEYWORD.search(title) and len(title.split()) <= 20:
                        c.title = title
                        c.date = re.sub(r"\s+", " ", m.group("date")).upper()
    return sorted(found.values(), key=lambda c: _clause_key(c.number))
