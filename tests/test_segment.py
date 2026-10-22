from amagi_federal_compliance_matrix.extract import load
from amagi_federal_compliance_matrix.segment import split_inline_list, split_sentences, walk


def texts(pairs):
    return [s for _, s in pairs]


def test_split_keeps_abbreviations():
    out = texts(split_sentences("Submit by 2:00 p.m. Eastern Time. See FAR 52.212-1 e.g. the U.S. rules. Done."))
    assert out == ["Submit by 2:00 p.m. Eastern Time.", "See FAR 52.212-1 e.g. the U.S. rules.", "Done."]


def test_split_after_section_letter():
    out = texts(split_sentences("Describe each task in Section C. The volume should be short."))
    assert out == ["Describe each task in Section C.", "The volume should be short."]


def test_split_keeps_no_abbreviation():
    assert len(split_sentences("Use contract No. 12 for this work.")) == 1


def test_inline_list():
    head, items = split_inline_list("The Contractor shall maintain: (a) an inventory; (b) a log; and (c) a report.")
    assert head == "The Contractor shall maintain:"
    assert [m for m, _ in items] == ["(a)", "(b)", "(c)"]
    assert items[2][1] == "a report."


def test_inline_list_needs_sequence():
    assert split_inline_list("See note: (b) only and (d) later.") is None
    assert split_inline_list("No colon (a) here (b) there.") is None


def _walk(make_txt, text):
    return walk(load(make_txt(text)))


def test_ucf_and_numbered_sections(make_txt):
    sents = _walk(make_txt, "SECTION L - INSTRUCTIONS TO OFFERORS\nL.4 Technical Volume\nThe offeror shall describe its approach.\n")
    s = sents[-1]
    assert (s.ucf, s.section, s.section_title) == ("L", "L.4", "Technical Volume")


def test_inline_heading_title(make_txt):
    sents = _walk(make_txt, "SECTION C - PWS\nC.3.1 Help Desk. The Contractor shall staff the desk.\n")
    assert sents[-1].section == "C.3.1"
    assert sents[-1].section_title == "Help Desk"
    assert sents[-1].text == "Help Desk. The Contractor shall staff the desk." or sents[-1].text.endswith("staff the desk.")


def test_leadin_items_become_rows(make_txt):
    text = "SECTION C - PWS\nC.1 Tasks\nThe Contractor shall:\n(a) answer calls;\n(b) log tickets; and\n(c) close tickets.\nNext paragraph here.\n"
    sents = _walk(make_txt, text)
    items = [s for s in sents if s.leadin]
    assert [s.marker for s in items] == ["(a)", "(b)", "(c)"]
    assert all(s.leadin == "The Contractor shall:" for s in items)
    assert not any(s.text == "The Contractor shall:" for s in sents)
    assert sents[-1].text == "Next paragraph here." and not sents[-1].leadin


def test_sentence_across_page_break_keeps_start_page(make_txt):
    sents = _walk(make_txt, "The Contractor shall deliver the report\f to the COR every month.\n")
    assert sents[0].text == "The Contractor shall deliver the report to the COR every month."
    assert (sents[0].page_start, sents[0].page_end) == (1, 2)


def test_toc_lines_skipped(make_txt):
    text = "TABLE OF CONTENTS\nSECTION C - PWS .......... 2\nSECTION L - INSTRUCTIONS .......... 4\nSECTION C - PWS\nThe Contractor shall work.\n"
    sents = _walk(make_txt, text)
    assert [s.text for s in sents] == ["The Contractor shall work."]


def test_attachment_sets_section(make_txt):
    sents = _walk(make_txt, "Attachment 2 - Labor Categories\nThe Contractor shall use these categories.\n")
    assert sents[-1].section == "Attachment 2"
    assert sents[-1].ucf == "J"


def test_hyphenated_line_break_rejoined(make_txt):
    sents = _walk(make_txt, "The Contractor shall pro-\nvide support.\n")
    assert sents[0].text == "The Contractor shall provide support."
