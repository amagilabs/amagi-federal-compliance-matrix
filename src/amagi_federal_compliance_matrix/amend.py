"""Carry answers from an old matrix onto the matrix of an amended solicitation.

Each new requirement is matched to a row of the old workbook by its text:
an exact match after normalising case, spacing and punctuation is
"Unchanged"; the closest remaining row at or above the similarity threshold
is "Changed" (the old wording goes in Previous Text so you can see what
moved); anything else is "New". Old rows that match nothing are listed as
"Removed", with whatever answer they had.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple

from .detect import Requirement
from .render import BASE_COLUMNS, RESPONSE_COLUMNS, Matrix, read_matrix_xlsx

KNOWN = set(BASE_COLUMNS) | set(RESPONSE_COLUMNS) | {"Change", "Previous Text"}


def normalize(text: str) -> str:
    t = text.lower()
    t = re.sub(r"\((?:[a-z]{1,2}|[ivx]{1,5}|\d{1,2})\)", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _tokens(text: str) -> set:
    return set(text.split())


def _old_requirement(rec: Dict[str, str], response_cols: List[str]) -> Requirement:
    page = rec.get("Page", "")
    p0 = int(page.split("-")[0]) if page.split("-")[0].isdigit() else 0
    p1 = int(page.split("-")[-1]) if page.split("-")[-1].isdigit() else p0
    return Requirement(
        id=rec.get("ID", ""), section=rec.get("Section", ""), section_title=rec.get("Section Title", ""),
        ucf=rec.get("UCF", ""), page_start=p0, page_end=p1, keyword=rec.get("Keyword", ""),
        kind=rec.get("Kind", ""), actor=rec.get("Actor", ""), text=rec.get("Requirement", ""),
        refs=[x.strip() for x in rec.get("Refs", "").split(",") if x.strip()],
        responses={c: rec.get(c, "") for c in response_cols},
    )


def carry_forward(new: Matrix, old_path: Path, threshold: float = 0.8) -> Matrix:
    old = read_matrix_xlsx(Path(old_path))
    header: List[str] = old["header"]  # type: ignore[assignment]
    records: List[Dict[str, str]] = old["rows"]  # type: ignore[assignment]
    extra = [h for h in header if h and h not in KNOWN]
    response_cols = list(RESPONSE_COLUMNS) + extra

    old_norm = [normalize(r["Requirement"]) for r in records]
    by_text: Dict[str, List[int]] = {}
    for j, t in enumerate(old_norm):
        by_text.setdefault(t, []).append(j)

    used = set()
    match: Dict[int, Tuple[int, float]] = {}
    for i, req in enumerate(new.requirements):
        hits = [j for j in by_text.get(normalize(req.text), []) if j not in used]
        if hits:
            used.add(hits[0])
            match[i] = (hits[0], 1.0)

    pairs: List[Tuple[float, int, int]] = []
    old_tokens = [_tokens(t) for t in old_norm]
    for i, req in enumerate(new.requirements):
        if i in match:
            continue
        a = normalize(req.text)
        ta = _tokens(a)
        scored = []
        for j, tb in enumerate(old_tokens):
            if j in used or not ta or not tb:
                continue
            jac = len(ta & tb) / len(ta | tb)
            if jac >= threshold * 0.5:
                scored.append((jac, j))
        for _, j in sorted(scored, reverse=True)[:5]:
            ratio = SequenceMatcher(None, a, old_norm[j], autojunk=False).ratio()
            if ratio >= threshold:
                pairs.append((ratio, i, j))
    for ratio, i, j in sorted(pairs, reverse=True):
        if i in match or j in used:
            continue
        used.add(j)
        match[i] = (j, ratio)

    for i, req in enumerate(new.requirements):
        if i in match:
            j, ratio = match[i]
            rec = records[j]
            req.responses = {c: rec.get(c, "") for c in response_cols}
            if ratio == 1.0:
                req.change = "Unchanged"
            else:
                req.change = "Changed"
                req.previous_text = rec["Requirement"]
        else:
            req.change = "New"
            req.responses = {c: "" for c in response_cols}

    new.removed = [_old_requirement(records[j], response_cols) for j in range(len(records)) if j not in used]
    new.previous_source = Path(old_path).name
    new.extra_columns = extra
    return new
