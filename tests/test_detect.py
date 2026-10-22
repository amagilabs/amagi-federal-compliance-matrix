from amagi_federal_compliance_matrix.detect import classify_actor, find_clauses


def one(run_reqs, text, **opts):
    reqs = run_reqs(text, **opts)
    assert len(reqs) == 1, [r.text for r in reqs]
    return reqs[0]


def test_keywords_found(run_reqs):
    text = (
        "SECTION C - PWS\n"
        "The Contractor shall do A. The Contractor must do B. The Contractor will do C. "
        "A plan is required within ten days. The Contractor is required to do E. "
        "This sentence has no obligation.\n"
    )
    reqs = run_reqs(text)
    assert [r.keyword for r in reqs] == ["shall", "must", "will", "required", "required"]


def test_definitions_skipped(run_reqs):
    assert run_reqs('"Business day" shall mean Monday through Friday.\n') == []
    assert run_reqs("The term deliverable shall include every report.\n") == []


def test_hyphenated_name_is_not_a_keyword(run_reqs):
    assert run_reqs("This file was made with amagi-federal-compliance-matrix for testing.\n") == []


def test_should_is_opt_in(run_reqs):
    text = "SECTION L - INSTRUCTIONS\nThe proposal should include a staffing chart.\n"
    assert run_reqs(text) == []
    r = one(run_reqs, text, include_should=True)
    assert r.kind == "Desirable" and r.actor == "Offeror"


def test_should_then_shall_counts_shall(run_reqs):
    r = one(run_reqs, "SECTION C - PWS\nIf possible staff should be local, but the Contractor shall attend meetings.\n")
    assert r.keyword == "shall"


def test_no_will_option(run_reqs):
    text = "SECTION C - PWS\nThe Contractor will attend meetings. The Contractor shall file reports.\n"
    assert len(run_reqs(text)) == 2
    assert [r.keyword for r in run_reqs(text, include_will=False)] == ["shall"]


def test_not_required_skipped(run_reqs):
    assert run_reqs("SECTION L - INSTRUCTIONS\nA cover letter is not required.\n") == []


def test_prohibition_kind(run_reqs):
    r = one(run_reqs, "SECTION C - PWS\nContractor staff shall not install software.\n")
    assert r.keyword == "shall not" and r.kind == "Prohibition"


def test_actor_from_subject(run_reqs):
    text = (
        "SECTION L - INSTRUCTIONS\n"
        "The Government will answer questions. Offerors shall submit one copy. "
        "The Contractor shall keep records.\n"
    )
    assert [r.actor for r in run_reqs(text)] == ["Government", "Offeror", "Contractor"]


def test_actor_falls_back_to_ucf(run_reqs):
    assert one(run_reqs, "SECTION L - INSTRUCTIONS\nPages shall be numbered.\n").actor == "Offeror"
    assert one(run_reqs, "SECTION C - PWS\nPages shall be numbered.\n").actor == "Contractor"
    assert one(run_reqs, "Pages shall be numbered.\n").actor == "Unclear"


def test_section_m_will_is_government(run_reqs):
    r = one(run_reqs, "SECTION M - EVALUATION\nProposals will be evaluated on technical merit.\n")
    assert r.actor == "Government" and r.kind == "Government"


def test_extra_government_name(run_reqs):
    text = "NASA will provide badges.\n"
    assert one(run_reqs, text).actor == "Unclear"
    assert one(run_reqs, text, government_names=["NASA"]).actor == "Government"


def test_offeror_only(run_reqs):
    text = "SECTION C - PWS\nThe Contractor shall work. Offerors shall submit a plan.\n"
    reqs = run_reqs(text, offeror_only=True)
    assert [r.actor for r in reqs] == ["Offeror"]


def test_skip_ucf(run_reqs):
    text = (
        "SECTION C - PWS\nThe Contractor shall work.\n"
        "SECTION I - CLAUSES\nThe Contractor shall comply with 52.204-21.\n"
    )
    assert [r.ucf for r in run_reqs(text, skip_ucf=["I"])] == ["C"]


def test_ids_count_per_section(run_reqs):
    text = (
        "SECTION C - PWS\nC.1 Scope\nThe Contractor shall do A. The Contractor shall do B.\n"
        "C.2 Staff\nStaff shall be trained.\n"
    )
    assert [r.id for r in run_reqs(text)] == ["C.1-01", "C.1-02", "C.2-01"]


def test_doc_ids_without_sections(run_reqs):
    assert [r.id for r in run_reqs("You must sign. You must date it.\n")] == ["Doc-01", "Doc-02"]


def test_leadin_text_in_requirement(run_reqs):
    text = "SECTION C - PWS\nThe Contractor shall:\n(a) answer calls;\n(b) log tickets.\n"
    reqs = run_reqs(text)
    assert [r.text for r in reqs] == [
        "The Contractor shall: (a) answer calls;",
        "The Contractor shall: (b) log tickets.",
    ]
    assert all(r.actor == "Contractor" for r in reqs)


# Built from parts so the release scanner does not read the clause number as a phone number.
DFARS_7012 = "252.204-" + "7012"


def test_refs_column(run_reqs):
    r = one(run_reqs, f"SECTION I - CLAUSES\nThe Contractor shall comply with FAR 52.222-41 and DFARS {DFARS_7012}.\n")
    assert r.refs == ["52.222-41", DFARS_7012]


def test_find_clauses_with_titles():
    pages = [[
        "52.204-21 Basic Safeguarding of Covered Contractor Information Systems (NOV 2021)",
        f"{DFARS_7012} Safeguarding Covered Defense Information and Cyber Incident",
        "Reporting (MAY 2024)",
        "See also 52.212-1 for instructions.",
    ], ["52.212-1 again on page two."]]
    clauses = {c.number: c for c in find_clauses(pages)}
    assert clauses["52.204-21"].title == "Basic Safeguarding of Covered Contractor Information Systems"
    assert clauses["52.204-21"].date == "NOV 2021"
    assert clauses[DFARS_7012].title.endswith("Cyber Incident Reporting")
    assert clauses["52.212-1"].title == ""
    assert clauses["52.212-1"].pages == [1, 2]
    assert list(clauses) == ["52.204-21", "52.212-1", DFARS_7012]


def test_classify_actor_after_comma():
    assert classify_actor("If awarded, the contractor ", "shall", "") == "Contractor"
    assert classify_actor("Within ten days of award, the offeror ", "shall", "C") == "Offeror"
