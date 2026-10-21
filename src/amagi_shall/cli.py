"""Command line: amagi-shall [matrix] FILE | update OLD.xlsx NEW.pdf | check MATRIX.xlsx"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .amend import carry_forward
from .check import check, report
from .detect import Options, detect, find_clauses, government_names
from .extract import ExtractError, NoTextError, load
from .render import Matrix, stdout_text, summary_lines, write_outputs

COMMANDS = ("matrix", "update", "check")
FORMATS = ("xlsx", "md", "csv", "json")


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def _formats(value: str) -> List[str]:
    fmts = [f.strip().lower() for f in value.split(",") if f.strip()]
    bad = [f for f in fmts if f not in FORMATS]
    if bad or not fmts:
        raise argparse.ArgumentTypeError(f"formats must be from {', '.join(FORMATS)} (got {value!r})")
    return fmts


def _add_matrix_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-o", "--out", default=".", help="output folder (default: current folder)")
    p.add_argument("--name", help="output file stem (default: the input file name)")
    p.add_argument("--format", type=_formats, default=["xlsx", "md"],
                   help="comma list of xlsx, md, csv, json (default: xlsx,md)")
    p.add_argument("--stdout", choices=("md", "csv", "json"),
                   help="print the matrix to stdout in this format and write no files")
    p.add_argument("--no-will", action="store_true", help="skip sentences whose only keyword is 'will'")
    p.add_argument("--include-should", action="store_true", help="also list 'should' sentences (Desirable)")
    p.add_argument("--offeror-only", action="store_true",
                   help="keep only rows that bind the offeror (plus Unclear ones)")
    p.add_argument("--skip-ucf", default="", metavar="LETTERS",
                   help="skip UCF sections, e.g. I or I,J (full-text clauses, attachments)")
    p.add_argument("--government", action="append", default=[], metavar="NAME",
                   help="extra name for the buyer, e.g. --government NASA (repeatable)")
    p.add_argument("-q", "--quiet", action="store_true", help="print only the paths written")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="amagi-shall",
        description="Turn an RFP or solicitation PDF into a compliance matrix: every shall, must, will "
                    "and required sentence with section, page and blank response columns.",
        epilog="Examples:\n  amagi-shall solicitation.pdf\n"
               "  amagi-shall update old_matrix.xlsx amendment_0001.pdf\n"
               "  amagi-shall check old_matrix.xlsx",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"amagi-shall {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="{matrix,update,check}")

    pm = sub.add_parser("matrix", help="build a matrix from a solicitation (the default command)")
    pm.add_argument("file", help="solicitation .pdf (or .txt)")
    _add_matrix_options(pm)

    pu = sub.add_parser("update", help="rebuild the matrix from an amended solicitation, keeping your answers")
    pu.add_argument("old", help="the matrix .xlsx you have been filling in")
    pu.add_argument("file", help="the amended solicitation .pdf (or .txt)")
    pu.add_argument("--threshold", type=float, default=0.8,
                    help="similarity (0-1) for a reworded row to count as Changed rather than New (default 0.8)")
    _add_matrix_options(pu)

    pc = sub.add_parser("check", help="list rows of a filled matrix that still have no answer")
    pc.add_argument("matrix", help="matrix .xlsx")
    pc.add_argument("--require", default="Compliance",
                    help="comma list of columns that must be filled (default: Compliance)")
    pc.add_argument("--include-government", action="store_true",
                    help="also require answers on Government rows")
    pc.add_argument("--limit", type=int, default=15, help="rows to list per group (default 15)")
    return parser


def _normalize_argv(argv: List[str]) -> List[str]:
    if argv and argv[0] not in COMMANDS and not argv[0].startswith("-"):
        return ["matrix"] + argv
    if argv and argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version"):
        # options before the file: amagi-shall -o out solicitation.pdf
        return ["matrix"] + argv
    return argv


def _build(args: argparse.Namespace) -> Matrix:
    doc = load(args.file)
    opts = Options(
        include_will=not args.no_will, include_should=args.include_should,
        offeror_only=args.offeror_only,
        skip_ucf=[x.strip() for x in args.skip_ucf.split(",") if x.strip()],
        government_names=list(args.government) + government_names(doc.pages),
    )
    from .segment import walk

    reqs = detect(walk(doc), opts)
    warnings = list(doc.warnings)
    if not reqs:
        warnings.append("no shall/must/will/required sentences found")
    return Matrix(
        source=doc.path.name, pages=doc.page_count, sha256=doc.sha256, requirements=reqs,
        clauses=find_clauses(doc.pages), warnings=warnings,
    )


def _emit(m: Matrix, args: argparse.Namespace) -> int:
    if args.stdout:
        sys.stdout.write(stdout_text(m, args.stdout) or "")
        return 0
    stem = args.name or Path(args.file).stem
    written = write_outputs(m, Path(args.out), stem, args.format)
    if args.quiet:
        for p in written:
            print(p)
        return 0
    print(f"amagi-shall {__version__}  {m.source} ({m.pages} page{'' if m.pages == 1 else 's'})")
    for line in summary_lines(m):
        print(f"  {line}")
    for w in m.warnings:
        print(f"  warning: {w}")
    for p in written:
        print(f"wrote {p}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    _utf8_stdout()
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv:
        parser.print_help()
        return 1
    args = parser.parse_args(_normalize_argv(argv))
    try:
        if args.command == "check":
            require = [c.strip() for c in args.require.split(",") if c.strip()]
            res = check(Path(args.matrix), require=require, include_government=args.include_government)
            sys.stdout.write(report(res, limit=args.limit))
            return 0 if res.ok else 3
        m = _build(args)
        if args.command == "update":
            if not Path(args.old).exists():
                raise ExtractError(f"file not found: {args.old}")
            m = carry_forward(m, Path(args.old), threshold=args.threshold)
        return _emit(m, args)
    except NoTextError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (ExtractError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
