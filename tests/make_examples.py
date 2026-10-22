"""Regenerate the example files in examples/.

- sample_solicitation.pdf          a fictional federal RFP in Uniform Contract Format
- sample_solicitation_amd0001.pdf  the same RFP after a fictional Amendment 0001
- sample_matrix_answered.xlsx      the base matrix with demo answers typed in

The agency, solicitation number and every requirement are made up. Clause
numbers are real FAR/DFARS numbers so the Clauses sheet has something to
find; check acquisition.gov for current titles and dates before relying on
them. Run from the repo root after `pip install -e .`:

    python tests/make_examples.py
"""

from __future__ import annotations

import contextlib
import io
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from minipdf import write_pdf  # noqa: E402

SOL = "OER-26-R-0042"
WIDTH = 88
BODY_LINES = 28

BASE = [
    ("h", "OFFICE OF EXAMPLE RECORDS (FICTIONAL)"),
    ("h", f"SOLICITATION NO. {SOL}"),
    ("h", "HELP DESK AND END-USER SUPPORT SERVICES"),
    ("p", "This is a sample solicitation written to demonstrate amagi-federal-compliance-matrix. The agency, the "
          "requirements and the dates are fictional."),
    ("h", "TABLE OF CONTENTS"),
    ("toc", "SECTION B - SUPPLIES OR SERVICES AND PRICES .......... 1"),
    ("toc", "SECTION C - PERFORMANCE WORK STATEMENT .......... 2"),
    ("toc", "SECTION L - INSTRUCTIONS TO OFFERORS .......... 4"),
    ("toc", "SECTION M - EVALUATION FACTORS FOR AWARD .......... 5"),
    ("h", "PART I - THE SCHEDULE"),
    ("h", "SECTION B - SUPPLIES OR SERVICES AND PRICES"),
    ("p", "B.1 Pricing. Offerors shall price each contract line item (CLIN) on a firm-fixed-price "
          "basis. CLIN 0001 covers the base year and CLINs 1001 through 4001 cover four option years."),
    ("p", "Prices shall include all labor, travel, tools and overhead needed to perform Section C."),
    ("h", "SECTION C - PERFORMANCE WORK STATEMENT"),
    ("h", "C.1 Background"),
    ("p", "The Office of Example Records supports about 1,200 employees at three sites. The "
          "Government will furnish workspace, telephones and network access for on-site staff."),
    ("p", "\"Business day\" shall mean Monday through Friday, excluding Federal holidays."),
    ("h", "C.2 Scope"),
    ("p", "The Contractor shall provide Tier 1 and Tier 2 help desk support, desk-side support and "
          "asset management for all Office of Example Records users."),
    ("h", "C.3 Tasks"),
    ("p", "C.3.1 Help Desk. The Contractor shall staff the help desk from 7:00 a.m. to 7:00 p.m. "
          "Eastern Time on every business day. The Contractor shall:"),
    ("li", "(a)", "answer 90 percent of calls within 60 seconds;"),
    ("li", "(b)", "resolve 70 percent of Tier 1 tickets on first contact; and"),
    ("li", "(c)", "log every contact in the Government ticketing system."),
    ("p", "C.3.2 Asset Management. The Contractor shall maintain: (a) an inventory of all end-user "
          "devices; (b) a knowledge base of known fixes; and (c) a monthly asset report."),
    ("p", "C.3.3 Security. Contractor personnel shall not install software that is not on the "
          "approved list. The Contractor must report a suspected security incident to the "
          "Contracting Officer's Representative within one hour of discovery."),
    ("h", "C.4 Key Personnel"),
    ("p", "The Program Manager shall have at least five years of experience managing help desk "
          "contracts of similar size. Key personnel must hold an active Secret clearance at "
          "contract start."),
    ("h", "C.5 Deliverables"),
    ("p", "A monthly status report is required by the fifth business day of each month. All "
          "deliverables shall be submitted in Microsoft Word or PDF format."),
    ("h", "PART II - CONTRACT CLAUSES"),
    ("h", "SECTION I - CONTRACT CLAUSES"),
    ("p", "The following clauses are incorporated by reference:"),
    ("row", "52.204-21 Basic Safeguarding of Covered Contractor Information Systems (NOV 2021)"),
    ("row", "52.217-9 Option to Extend the Term of the Contract (MAR 2000)"),
    ("row", "52.222-41 Service Contract Labor Standards (AUG 2018)"),
    ("row", "52.232-33 Payment by Electronic Funds Transfer - System for Award Management (OCT 2018)"),
    ("h", "PART IV - REPRESENTATIONS AND INSTRUCTIONS"),
    ("h", "SECTION L - INSTRUCTIONS TO OFFERORS"),
    ("h", "L.1 General Instructions"),
    ("p", "Offerors shall submit proposals by e-mail to the Contracting Officer no later than "
          "2:00 p.m. Eastern Time on November 20, 2026. Late proposals will not be considered."),
    ("p", "Questions must be submitted in writing no later than November 2, 2026. The Government "
          "will post answers as an amendment to this solicitation."),
    ("h", "L.2 Proposal Volumes"),
    ("p", "Each proposal shall consist of the following volumes:"),
    ("li", "(a)", "Volume I, Technical, limited to 25 pages;"),
    ("li", "(b)", "Volume II, Past Performance, limited to 10 pages; and"),
    ("li", "(c)", "Volume III, Price, with no page limit."),
    ("h", "L.3 Format"),
    ("p", "Pages shall be 8.5 by 11 inches with one-inch margins. Text must be 12 point or "
          "larger; tables may use 10 point. Pages beyond the limit will not be evaluated."),
    ("h", "L.4 Technical Volume"),
    ("p", "The offeror shall describe its approach to each task in Section C. The technical volume "
          "should include a staffing matrix. Resumes are required for the Program Manager and the "
          "Help Desk Lead."),
    ("h", "L.5 Past Performance Volume"),
    ("p", "Offerors shall provide no more than three (3) references for contracts performed within "
          "the last five (5) years. Each reference must include a point of contact and the contract "
          "value. See FAR 52.212-1 for general instructions."),
    ("h", "SECTION M - EVALUATION FACTORS FOR AWARD"),
    ("h", "M.1 Basis for Award"),
    ("p", "The Government will award a contract to the offeror whose proposal represents the best "
          "value. Technical and past performance, combined, are more important than price."),
    ("h", "M.2 Evaluation Factors"),
    ("p", "Proposals will be evaluated on Factor 1, Technical Approach; Factor 2, Past Performance; "
          "and Factor 3, Price. The offeror must receive an Acceptable rating on Factor 1 to be "
          "eligible for award."),
]


def amendment_0001(blocks):
    """Fictional Amendment 0001: a later due date, a tighter answer time, a new
    certification requirement, a bigger page limit, resumes no longer required."""
    out = []
    for block in blocks:
        kind = block[0]
        text = block[-1]
        if kind == "h" and text.startswith("SOLICITATION NO."):
            out.append(block)
            out.append(("h", "AMENDMENT 0001"))
            continue
        if kind == "p" and text.startswith("Offerors shall submit proposals by e-mail"):
            text = text.replace("November 20, 2026", "December 4, 2026")
        if kind == "li" and text.startswith("answer 90 percent"):
            text = text.replace("within 60 seconds", "within 45 seconds")
        if kind == "li" and text.startswith("Volume I, Technical"):
            text = text.replace("25 pages", "30 pages")
        if kind == "p" and text.startswith("The offeror shall describe its approach"):
            text = text.replace(" Resumes are required for the Program Manager and the Help Desk Lead.", "")
        if kind == "p" and text.startswith("The Program Manager shall have"):
            out.append((kind, text))
            out.append(("p", "Help desk staff must hold a current CompTIA A+ certification within 90 days "
                             "of starting work on the contract."))
            continue
        out.append(block[:-1] + (text,))
    return out


def layout(blocks, title):
    lines = []
    for block in blocks:
        kind = block[0]
        if kind == "h":
            lines.append(block[1])
        elif kind in ("toc", "row"):
            lines.append(block[1])
        elif kind == "p":
            lines.extend(textwrap.wrap(block[1], WIDTH))
        elif kind == "li":
            wrapped = textwrap.wrap(block[2], WIDTH - 6)
            lines.append(f"{block[1]} {wrapped[0]}")
            lines.extend(f"    {w}" for w in wrapped[1:])
    pages = [lines[i:i + BODY_LINES] for i in range(0, len(lines), BODY_LINES)]
    total = len(pages)
    return [[f"{title} - Solicitation {SOL}"] + p + [f"Page {n} of {total}"] for n, p in enumerate(pages, 1)]


def answered_matrix(base_pdf: Path, target: Path) -> None:
    """Build the base matrix with the real tool, then type in demo answers."""
    from openpyxl import load_workbook

    from amagi_federal_compliance_matrix.cli import main

    tmp = target.parent / "_tmp_matrix"
    with contextlib.redirect_stdout(io.StringIO()):
        main([str(base_pdf), "-o", str(tmp), "--name", "base", "--format", "xlsx", "-q"])
    wb = load_workbook(str(tmp / "base_matrix.xlsx"))
    ws = wb["Matrix"]
    header = [c.value for c in ws[1]]
    col = {h: i + 1 for i, h in enumerate(header)}
    for row in range(2, ws.max_row + 1):
        actor = ws.cell(row=row, column=col["Actor"]).value
        text = ws.cell(row=row, column=col["Requirement"]).value or ""
        if actor == "Government":
            continue
        if "Secret clearance" in text:
            ws.cell(row=row, column=col["Compliance"], value="Exception")
            ws.cell(row=row, column=col["Response / Notes"], value="One proposed lead holds Top Secret, the other is pending.")
        elif "monthly asset report" in text:
            continue  # left blank on purpose so `check` has something to report
        else:
            ws.cell(row=row, column=col["Compliance"], value="Comply")
            ws.cell(row=row, column=col["Proposal Reference"], value=f"Vol I, {ws.cell(row=row, column=col['Section']).value}")
        ws.cell(row=row, column=col["Owner"], value="Capture lead")
    wb.save(str(target))
    for p in tmp.iterdir():
        p.unlink()
    tmp.rmdir()


def main() -> None:
    ex = ROOT / "examples"
    ex.mkdir(exist_ok=True)
    base = write_pdf(ex / "sample_solicitation.pdf", layout(BASE, "Office of Example Records"))
    write_pdf(ex / "sample_solicitation_amd0001.pdf", layout(amendment_0001(BASE), "Office of Example Records - Amendment 0001"))
    answered_matrix(base, ex / "sample_matrix_answered.xlsx")
    print("wrote", ", ".join(p.name for p in sorted(ex.iterdir()) if p.suffix in (".pdf", ".xlsx")))


if __name__ == "__main__":
    main()
