---
name: amagi-shall
description: Build a federal-style compliance matrix from an RFP or solicitation PDF with the local amagi-shall CLI. Every shall, must, will and required sentence becomes a row with section, UCF letter, page, who it binds (Offeror, Contractor, Government) and blank Compliance / Proposal Reference / Owner / Response columns, exported as XLSX and markdown. Also carries answers forward onto an amended solicitation (update) and lists unanswered rows before submission (check). Use when asked for a compliance matrix, the shall statements in Section L or C, what changed in an amendment, or which matrix rows are still blank. Runs offline, no API key.
---

# amagi-shall

A CLI that reads a solicitation and writes a compliance matrix you fill in:

- `<name>_matrix.xlsx`: a "Matrix" sheet with ID, Section, Section Title, UCF, Page, Keyword,
  Kind, Actor, Requirement and Refs, then empty Compliance (Comply / Partial / Exception / N/A
  dropdown), Proposal Reference, Owner and Response / Notes columns. Plus "Clauses" (every
  FAR/DFARS clause number cited, with title and date when the document gives them), "Summary"
  and "About" sheets.
- `<name>_matrix.md`: the same rows as a markdown table.

## When to use this skill

- "Build a compliance matrix for this solicitation."
- "List every shall in Section L" or "what does Section C require of the contractor?"
- "Amendment 0001 came out. What changed, and can you keep my answers?"
- "Which rows of my matrix are still blank?"
- "Which FAR clauses does this RFP cite?"

## How to use it

1. Check it is installed: `amagi-shall --version`. If not: `pipx install amagi-shall` (or
   `pipx install .` from a clone of the repo).
2. Build the matrix: `amagi-shall solicitation.pdf -o <dir>`. Useful options:
   - `--stdout json` prints the rows as JSON and writes nothing, when you want to reason over them.
   - `--offeror-only` keeps rows that bind the offeror (Section L/K work) plus Unclear rows.
   - `--skip-ucf I,J` drops full-text clauses and attachments.
   - `--no-will` drops "will" sentences. `--include-should` adds "should" rows as Desirable.
   - `--government NAME` adds a buyer name the tool should treat as Government (repeatable).
     Abbreviations the document defines, like "Department of Energy (DOE)", are picked up already.
3. Read the summary back: requirement count, the Offeror / Contractor / Government split, the
   count per UCF section, and the clause count.
4. When an amendment drops: `amagi-shall update old_matrix.xlsx amendment.pdf -o <dir>`. Each row
   is marked Unchanged, Changed (old wording kept in Previous Text) or New, and removed rows are
   listed with their old answers. Tell the user to re-check every Changed and New row; answers on
   Changed rows are carried over but may no longer be right.
5. Before submission: `amagi-shall check matrix.xlsx`. Exit code 3 means rows still need an
   answer; the report lists them and any Exception or Partial answers.

## Review pass for Claude

The rules are deterministic and do not call a model. After a run, it is worth a quick review:

- Rows with Actor "Unclear" or a subject that is only a noun ("The plan shall...") are guesses.
  Read them in context and suggest the right actor.
- In Section L, "will" sentences are often information ("A site visit will be held") rather than
  a task. Point these out so the user can mark them N/A.
- A sentence with two obligations stays one row. Offer to split it if the user wants one row per
  obligation.

Suggest edits; do not rewrite the requirement text, which is copied from the PDF on purpose.

## Exit codes

- 0: success (check: every required row answered).
- 1: file missing, unsupported type or unreadable.
- 2: no text layer (scanned PDF). Suggest `ocrmypdf input.pdf output.pdf`, then run again.
- 3: check found unanswered rows.

## Limits to mention when relevant

- Section and UCF letters come from the headings in the text. A solicitation that is not in the
  federal A to M format still works, with sections from its own numbering.
- Actor is a heuristic from the subject of the sentence and the UCF section it sits in.
- Scanned PDFs need OCR first. Multi-column pages and tables can come out in odd order.
- Text is copied from the PDF text layer as-is, so a broken character can appear where the PDF
  has one (for example a curly apostrophe stored without a unicode mapping).
- The tool is a first draft. The user must check the matrix against the solicitation.
