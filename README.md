# amagi-federal-compliance-matrix

Turn a federal RFP or solicitation PDF into a compliance matrix you can start answering today.
Every "shall", "must", "will" and "required" sentence becomes a row with its section, UCF
letter, page, and who it binds, followed by blank Compliance, Proposal Reference, Owner and
Response columns. You get an Excel workbook and a markdown copy. When Amendment 0001 drops,
amagi-federal-compliance-matrix rebuilds the matrix and keeps the answers you already wrote.

Built for small government contractors and subcontractors who write their own proposals. It runs
on your machine with no account and no API key, and the solicitation stays on your computer.

![demo](https://raw.githubusercontent.com/amagilabs/amagi-federal-compliance-matrix/master/assets/demo.gif)

## Install

```
pipx install amagi-federal-compliance-matrix
```

Python 3.9 or newer.

## Usage

```
$ amagi-federal-compliance-matrix sample_solicitation.pdf -o out
amagi-federal-compliance-matrix 0.1.0  sample_solicitation.pdf (3 pages)
  33 requirements: 15 offeror, 14 contractor, 4 government
  by UCF section: B 1, C 15, L 14, M 3
  5 FAR/DFARS clauses referenced (4 with titles)
wrote out\sample_solicitation_matrix.xlsx
wrote out\sample_solicitation_matrix.md
```

That run used `examples/sample_solicitation.pdf`, a made-up help desk RFP in the federal Uniform
Contract Format that ships with the repo. Run the commands on this page from the `examples`
folder to see the same output.

Each row keeps the sentence exactly as the PDF has it. List items carry the sentence that
introduced them, so a row still makes sense on its own:

```
| ID | Section | Page | Actor | Requirement | Compliance | Proposal Reference | Response / Notes |
|---|---|---|---|---|---|---|---|
| C.1-01 | C.1 | 1 | Government | The Government will furnish workspace, telephones and network access for on-site staff. |  |  |  |
| C.3.1-02 | C.3.1 | 1 | Contractor | The Contractor shall: (a) answer 90 percent of calls within 60 seconds; |  |  |  |
| C.3.1-03 | C.3.1 | 2 | Contractor | The Contractor shall: (b) resolve 70 percent of Tier 1 tickets on first contact; and |  |  |  |
| L.1-03 | L.1 | 2 | Offeror | Questions must be submitted in writing no later than November 2, 2026. |  |  |  |
```

The Actor column splits the work three ways:

- **Offeror** rows tell you what to put in the proposal (mostly Sections L and K).
- **Contractor** rows are what you promise to do after award (Sections C through J).
- **Government** rows are what the agency says it will do. They're in the matrix so you can see
  them, and `check` skips them.

The workbook has four sheets. "Matrix" holds the rows, with a Comply / Partial / Exception / N/A
dropdown in the Compliance column, frozen headers and filters. "Clauses" lists every FAR and
DFARS clause number the document cites, with the title and date when the text gives them.
"Summary" and "About" record the counts, the source file and its SHA-256.

### When an amendment comes out

```
$ amagi-federal-compliance-matrix update sample_matrix_answered.xlsx sample_solicitation_amd0001.pdf -o out
amagi-federal-compliance-matrix 0.1.0  sample_solicitation_amd0001.pdf (3 pages)
  33 requirements: 14 offeror, 15 contractor, 4 government
  by UCF section: B 1, C 16, L 13, M 3
  5 FAR/DFARS clauses referenced (4 with titles)
  vs sample_matrix_answered.xlsx: 29 unchanged, 3 changed, 1 new, 1 removed; responses carried to 27 rows
wrote out\sample_solicitation_amd0001_matrix.xlsx
wrote out\sample_solicitation_amd0001_matrix.md
```

`update` reads the matrix you've been filling in and matches each row of the amended solicitation
to it by wording. A row with the same text is Unchanged and keeps your answer. A reworded row is
Changed: your answer comes along, and the old wording goes in a Previous Text column, so you can
see that 60 seconds became 45. Anything with no match is New and starts blank. Rows that were
dropped from the solicitation go to a "Removed" sheet with the answers you had given them. Any
columns you added to the workbook yourself carry over too.

### Before you submit

```
$ amagi-federal-compliance-matrix check sample_matrix_answered.xlsx
amagi-federal-compliance-matrix check: sample_matrix_answered.xlsx
  29 rows to answer (4 Government rows skipped)
  28 answered, 1 blank Compliance
  1 Exception, 0 Partial
blank Compliance:
  C.3.2-03     p.2     The Contractor shall maintain: (c) a monthly asset report.
exceptions:
  C.4-02       p.2     Key personnel must hold an active Secret clearance at contract start.
FAIL: rows above still need an answer
```

`check` exits with code 3 while any row is unanswered, so it also works as the last step of a
script. `--require Compliance,Owner` makes more columns mandatory.

### Options

```
amagi-federal-compliance-matrix FILE                       write FILE_matrix.xlsx and FILE_matrix.md here
amagi-federal-compliance-matrix FILE -o out/               write them to out/
amagi-federal-compliance-matrix FILE --format xlsx,md,csv,json
amagi-federal-compliance-matrix FILE --stdout json         print the rows, write no files
amagi-federal-compliance-matrix FILE --offeror-only        only what goes in the proposal (plus Unclear rows)
amagi-federal-compliance-matrix FILE --skip-ucf I,J        leave out full-text clauses and attachments
amagi-federal-compliance-matrix FILE --no-will             drop sentences whose only keyword is "will"
amagi-federal-compliance-matrix FILE --include-should      add "should" sentences as Desirable rows
amagi-federal-compliance-matrix FILE --government NASA     treat another name as the buyer (repeatable)
amagi-federal-compliance-matrix update OLD.xlsx NEW.pdf    rebuild after an amendment, keep your answers
amagi-federal-compliance-matrix check MATRIX.xlsx          list rows that still need an answer
```

FILE can be a `.pdf` or a `.txt`. Exit codes: 0 success, 1 the file can't be read, 2 the PDF has
no text layer (a scan), 3 `check` found unanswered rows.

## On real solicitations

The rules were tuned on two public draft solicitations, which aren't in this repo:

- A Department of Energy draft RFP Section L for the Strategic Petroleum Reserve management and
  operating contract, 51 pages: 230 requirements (180 offeror, 26 contractor, 24 government)
  and 15 FAR/DFARS clauses.
- A Navy draft Sections L and M for a multiple-award IDIQ, 52 pages: 347 requirements (252
  offeror, 9 contractor, 86 government) and 14 clauses.

Each took about 10 seconds on a Windows desktop.

Abbreviations the solicitation defines, such as "Department of Energy (DOE)", are read as the
Government. Running headers, footers, page lines such as "Section L, Page iii" and table of
contents lines are removed before sentences are split.

## Limits

amagi-federal-compliance-matrix gives you a first draft of the matrix. Read the solicitation and check each row
before you rely on it.

- Scanned PDFs have no text to read. Run them through OCR first, for example
  `ocrmypdf scanned.pdf searchable.pdf`.
- Actor is a guess from the subject of the sentence and the section it sits in. In Section L,
  plain "will" sentences such as "A site visit will be held" come out as Offeror rows. Mark them
  N/A, or use `--no-will`.
- A sentence with two obligations stays one row.
- No model is involved. The rules are plain code, so the same PDF always gives the same matrix.
  For a second opinion, the [SKILL.md](SKILL.md) asks Claude to review the rows the rules are
  least sure of.
- Multi-column pages and tables can come out of a PDF in a strange order. Check
  those sections by hand.
- Text is copied from the PDF's text layer. If the PDF stores a curly apostrophe with no character
  mapping, the row shows a replacement character where the apostrophe was.

## Use it from Claude Code

The repo ships a [SKILL.md](SKILL.md). Copy it to `~/.claude/skills/amagi-federal-compliance-matrix/SKILL.md` and
Claude Code will run amagi-federal-compliance-matrix when you ask for a compliance matrix, the shall statements in a
section, or what changed in an amendment. It also has Claude review the rows the rules are least
sure of.

## Star it if it saved you a weekend

If amagi-federal-compliance-matrix spared you a weekend of pasting shall statements into a spreadsheet, a star helps
other small contractors find it. The most useful bug report is a link to a public solicitation
that trips it up.

## Other AmagiLabs projects

- [amagilabs on GitHub](https://github.com/amagilabs): all of the small open-source tools from
  AmagiLabs (Amagisolutionsgroup, Inc.).
- [amagi-legal-review-skills](https://github.com/amagilabs/amagi-legal-review-skills): Claude Code skills
  for a first-pass review of contracts and leases.

## Development

```
pip install -e ".[dev]"
pytest
python tests/make_examples.py   # rebuild the files in examples/
```

## License

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 Amagisolutionsgroup, Inc. (AmagiLabs).
