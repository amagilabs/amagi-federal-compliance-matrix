import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from minipdf import write_pdf  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def sample_pdf() -> Path:
    return EXAMPLES / "sample_solicitation.pdf"


@pytest.fixture
def amendment_pdf() -> Path:
    return EXAMPLES / "sample_solicitation_amd0001.pdf"


@pytest.fixture
def answered_xlsx() -> Path:
    return EXAMPLES / "sample_matrix_answered.xlsx"


@pytest.fixture
def make_pdf(tmp_path):
    """make_pdf([[page 1 lines], [page 2 lines]]) -> path to a real PDF."""
    def _make(pages, name="doc.pdf"):
        return write_pdf(tmp_path / name, pages)
    return _make


@pytest.fixture
def make_txt(tmp_path):
    """make_txt("text") -> path; use \f to separate pages."""
    def _make(text, name="doc.txt"):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path
    return _make


@pytest.fixture
def run_reqs(make_txt):
    """run_reqs("text", **options) -> list of Requirement from a text file."""
    from amagi_shall.detect import Options, detect
    from amagi_shall.extract import load
    from amagi_shall.segment import walk

    def _run(text, **opts):
        return detect(walk(load(make_txt(text))), Options(**opts))
    return _run
