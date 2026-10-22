"""Pre-submission check of a filled-in matrix: what is still unanswered."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

from .render import COMPLIANCE_CHOICES, plural, read_matrix_xlsx


@dataclass
class CheckResult:
    path: Path
    considered: int = 0
    skipped_government: int = 0
    blank: Dict[str, List[Dict[str, str]]] = field(default_factory=dict)
    invalid: List[Dict[str, str]] = field(default_factory=list)
    exceptions: List[Dict[str, str]] = field(default_factory=list)
    partials: List[Dict[str, str]] = field(default_factory=list)
    new_rows: List[Dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(self.blank.values()) and not self.invalid


def check(path: Path, require: Sequence[str] = ("Compliance",), include_government: bool = False) -> CheckResult:
    data = read_matrix_xlsx(Path(path))
    header: List[str] = data["header"]  # type: ignore[assignment]
    missing = [c for c in require if c not in header]
    if missing:
        raise ValueError(f"{Path(path).name}: no column named {', '.join(repr(c) for c in missing)}")
    res = CheckResult(path=Path(path), blank={c: [] for c in require})
    choices = {c.lower(): c for c in COMPLIANCE_CHOICES}
    for rec in data["rows"]:  # type: ignore[union-attr]
        if rec.get("Actor") == "Government" and not include_government:
            res.skipped_government += 1
            continue
        res.considered += 1
        for c in require:
            if not rec.get(c, "").strip():
                res.blank[c].append(rec)
        comp = rec.get("Compliance", "").strip()
        if comp:
            canon = choices.get(comp.lower())
            if canon is None:
                res.invalid.append(rec)
            elif canon == "Exception":
                res.exceptions.append(rec)
            elif canon == "Partial":
                res.partials.append(rec)
        if rec.get("Change") in ("New", "Changed"):
            res.new_rows.append(rec)
    return res


def _short(rec: Dict[str, str], width: int = 78) -> str:
    text = rec.get("Requirement", "")
    if len(text) > width:
        text = text[: width - 3].rstrip() + "..."
    page = rec.get("Page", "")
    return f"  {rec.get('ID', ''):<12} p.{page:<5} {text}"


def report(res: CheckResult, limit: int = 15) -> str:
    lines = [f"amagi-federal-compliance-matrix check: {res.path.name}"]
    skipped = f" ({plural(res.skipped_government, 'Government row')} skipped)" if res.skipped_government else ""
    lines.append(f"  {plural(res.considered, 'row')} to answer{skipped}")
    for col, rows in res.blank.items():
        lines.append(f"  {res.considered - len(rows)} answered, {len(rows)} blank {col}")
    if res.invalid:
        lines.append(f"  {len(res.invalid)} Compliance values not in {'/'.join(COMPLIANCE_CHOICES)}")
    lines.append(f"  {len(res.exceptions)} Exception, {len(res.partials)} Partial")
    if res.new_rows:
        lines.append(f"  {len(res.new_rows)} rows marked New or Changed by an amendment")

    def block(title: str, rows: List[Dict[str, str]]) -> None:
        if not rows:
            return
        lines.append(f"{title}:")
        lines.extend(_short(r) for r in rows[:limit])
        if len(rows) > limit:
            lines.append(f"  ... and {len(rows) - limit} more")

    for col, rows in res.blank.items():
        block(f"blank {col}", rows)
    block("not a valid Compliance value", res.invalid)
    block("exceptions", res.exceptions)
    block("partial", res.partials)
    lines.append("PASS: every row has an answer" if res.ok else "FAIL: rows above still need an answer")
    return "\n".join(lines) + "\n"
