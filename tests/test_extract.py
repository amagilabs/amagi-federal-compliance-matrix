import pytest

from amagi_shall.extract import ExtractError, NoTextError, load


def test_pdf_pages_and_hash(make_pdf):
    doc = load(make_pdf([["The Contractor shall do one thing."], ["The Offeror shall do another."]]))
    assert doc.page_count == 2
    assert len(doc.sha256) == 64
    assert doc.pages[0] == ["The Contractor shall do one thing."]


def test_running_header_and_page_footer_removed(make_pdf):
    pages = [
        ["Agency X - Solicitation 123", body, f"Page {n} of 3"]
        for n, body in enumerate(["The first page shall stay.", "Second body text.", "Third and last."], 1)
    ]
    doc = load(make_pdf(pages))
    assert doc.pages == [["The first page shall stay."], ["Second body text."], ["Third and last."]]
    assert doc.removed_lines == 6


def test_two_page_header_removed(make_pdf):
    doc = load(make_pdf([["Header Co - RFP 9", "First body line."], ["Header Co - RFP 9", "Second body line."]]))
    assert doc.pages == [["First body line."], ["Second body line."]]


def test_text_file_form_feed_splits_pages(make_txt):
    doc = load(make_txt("page one\fpage two\fpage three"))
    assert doc.page_count == 3
    assert doc.pages[2] == ["page three"]


def test_missing_file(tmp_path):
    with pytest.raises(ExtractError, match="not found"):
        load(tmp_path / "nope.pdf")


def test_unsupported_type_mentions_word(tmp_path):
    p = tmp_path / "rfp.docx"
    p.write_bytes(b"PK\x03\x04")
    with pytest.raises(ExtractError, match="save Word files as PDF"):
        load(p)


def test_no_text_layer_raises(make_pdf):
    with pytest.raises(NoTextError, match="OCR"):
        load(make_pdf([[], []]))


def test_corrupt_pdf(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"%PDF-1.4 this is not really a pdf")
    with pytest.raises(ExtractError):
        load(p)


def test_empty_page_warning(make_pdf):
    doc = load(make_pdf([
        ["The Contractor shall keep a log of every request it receives from users."],
        [],
        ["The Offeror shall submit three references for similar work in the last five years."],
    ]))
    assert any("page(s) 2" in w for w in doc.warnings)
