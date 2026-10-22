"""Regression tests for layouts found in real federal solicitations (DOE and Navy drafts)."""

from amagi_federal_compliance_matrix.detect import government_names
from amagi_federal_compliance_matrix.extract import _PAGE_NUM, load
from amagi_federal_compliance_matrix.segment import walk


def _walk(make_txt, text):
    return walk(load(make_txt(text)))


def test_sibling_items_do_not_inherit_a_nested_leadin(run_reqs):
    text = (
        "SECTION L - INSTRUCTIONS\n"
        "L.3 Volumes\n"
        "(a) The offeror shall provide the following:\n"
        "(1) A cover letter.\n"
        "(2) A table of contents.\n"
        "(b) The offeror shall sign the SF 33.\n"
    )
    assert [r.text for r in run_reqs(text)] == [
        "(a) The offeror shall provide the following: (1) A cover letter.",
        "(a) The offeror shall provide the following: (2) A table of contents.",
        "(b) The offeror shall sign the SF 33.",
    ]


def test_dash_leadin(run_reqs):
    text = (
        "SECTION L - INSTRUCTIONS\n"
        "L.5 Evaluation Basis\n"
        "Offerors shall submit information based upon-\n"
        "(1) their own records; and\n"
        "(2) client references.\n"
    )
    assert [r.text for r in run_reqs(text)] == [
        "Offerors shall submit information based upon- (1) their own records; and",
        "Offerors shall submit information based upon- (2) client references.",
    ]


def test_line_ending_in_or_does_not_end_the_sentence(make_txt):
    text = (
        "SECTION C - PWS\n"
        "The Contractor shall maintain Configuration Control or\n"
        "an equivalent process for all software.\n"
    )
    out = [s.text for s in _walk(make_txt, text)]
    assert out == ["The Contractor shall maintain Configuration Control or an equivalent process for all software."]


def test_standalone_heading_is_not_glued_to_the_next_sentence(make_txt):
    text = (
        "SECTION L - INSTRUCTIONS\n"
        "The offeror shall submit one volume.\n"
        "Notice to Offerors - Contents Review\n"
        "The offeror shall review the contents.\n"
    )
    out = [s.text for s in _walk(make_txt, text)]
    assert out[-1] == "The offeror shall review the contents."


def test_wrapped_attachment_reference_is_not_a_heading(make_txt):
    text = (
        "SECTION L - INSTRUCTIONS\n"
        "L.12 Cost Proposal\n"
        "Costs are to be proposed in the format provided in Section L,\n"
        "Attachment L-10, Summary of Key Personnel and Transition Cost Worksheet.\n"
        "The offeror shall enter the estimate in Volume III.\n"
    )
    sents = _walk(make_txt, text)
    assert {s.section for s in sents} == {"L.12"}


def test_numbered_list_inside_a_lettered_section_stays_in_it(make_txt):
    text = (
        "SECTION L - INSTRUCTIONS\n"
        "L.4.2.1 FINANCIAL RESOURCES\n"
        "(d) Attachment J.11 Instructions:\n"
        "1. Section I - General Information\n"
        "a. The offeror must complete all applicable sections.\n"
    )
    sents = _walk(make_txt, text)
    assert {s.section for s in sents} == {"L.4.2.1"}


def test_government_named_after_a_preposition_is_not_the_subject(run_reqs):
    reqs = run_reqs(
        "SECTION L - INSTRUCTIONS\n"
        "Protests filed with the Government Accountability Office (GAO) shall be copied to the offeror's counsel.\n"
    )
    assert [r.actor for r in reqs] == ["Offeror"]


def test_agency_abbreviations_are_detected():
    pages = [[
        "The Department of Energy (DOE) and the Defense Contract Audit Agency (DCAA) will review it.",
        "Use the Product and Service Code (PSC) and the Commercial and Government Entity (CAGE) code.",
    ]]
    assert government_names(pages) == ["DOE", "DCAA"]


def test_agency_abbreviation_sets_the_actor(run_reqs):
    text = "SECTION L - INSTRUCTIONS\nThe DOE will evaluate each proposal.\n"
    assert [r.actor for r in run_reqs(text, government_names=["DOE"])] == ["Government"]


def test_section_m_team_will_is_government(run_reqs):
    text = "SECTION M - EVALUATION\nFirst, the team will verify that a support document exists.\n"
    assert [r.actor for r in run_reqs(text)] == ["Government"]


def test_roman_page_footer_is_furniture():
    assert _PAGE_NUM.match("Section L, Page i")
    assert _PAGE_NUM.match("Page 12 of 51")
    assert not _PAGE_NUM.match("The offeror shall number each page of the volume in order.")
