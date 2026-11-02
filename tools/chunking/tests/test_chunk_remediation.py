"""Bounded successor controls: real gateway + owned negative cases, no QA approvals."""

import json
from collections import Counter
from pathlib import Path

import pytest

from rag_hub.chunk_catalog import ChunkCatalog
from rag_hub.chunk_inputs import ChunkInput, SourceContent
from rag_hub.chunk_remediation import (
    BoundedRemediator,
    numbered_reference_atoms,
    python_statement_atoms,
    table_atoms,
)
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.unified_consumption import load_verified_corpus
from rag_hub.unified_models import encode, sha

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "workspace/rag-implementation/v1/m3-remediation-v1"
DATA = ROOT / "data/chunking/m3-remediation-v1"
CASES = json.loads((WORK / "FROZEN_CASE_REVIEW.json").read_bytes())["cases"]
RECORDS = {r["unit_id"]: ChunkInput.model_validate(r) for r in
           map(json.loads, (WORK / "affected-prepared-inputs.jsonl").read_text().splitlines())}


def case_source(case):
    return next(s for s in RECORDS[case["unit_id"]].indexable_source_content
                if s.source_pointer == case["source_pointer"])


def owned_source(kind, text, native=None):
    return SourceContent(source_pointer="/owned", content_type=kind, text=text,
                         section_ids=["owned"], source_spans=[], native_source=native or {})


@pytest.fixture(scope="module")
def environment():
    corpus = load_verified_corpus(ROOT)
    before = ChunkCatalog(ROOT, corpus)
    after = ChunkCatalog(ROOT, corpus, selector="config/retrieval-chunks-m3-remediation-v1.json")
    tokenizer = PinnedBgeTokenizer(ROOT)
    return before, after, tokenizer


def test_all_22_frozen_classifications_and_four_separate_authorization_restrictions():
    original = [c for c in CASES if c["case_id"].startswith("M3R-")]
    assert len(original) == 22
    assert Counter(c["classification"] for c in original) == {
        "TECHNICALLY_REMEDIABLE": 15, "REQUIRES_OWNER_REVIEW": 7}
    assert len([c for c in CASES if c["classification"] == "AUTHORIZATION_RESTRICTED"]) == 4
    assert [c["case_id"] for c in original] == [f"M3R-{i:02}" for i in range(1, 23)]
    for c in original:
        source = case_source(c)
        assert sha(source.text.encode()) == c["source_text_sha256"]
        assert sha(encode(source.native_source)) == c["native_source_sha256"]


def test_preserve_every_original_row_and_configuration(environment):
    before, after, _ = environment
    old = {c["chunk_id"]: c for c in before.list_chunks(limit=1000)["items"]}
    new = {c["chunk_id"]: c for c in after.list_chunks(limit=1000)["items"]}
    assert len(old) == 893 and len(new) == 954
    assert {k: new[k] for k in old} == old
    assert all(after.manifest["configurations"][k] == v
               for k, v in before.manifest["configurations"].items())
    assert len(after.outcomes()) == 550
    assert len({c["unit_id"] for c in new.values()}) == 544


def test_all_61_new_slices_through_live_authorization_and_exact_budget(environment):
    before, after, tokenizer = environment
    old_ids = {c["chunk_id"] for c in before.list_chunks(limit=1000)["items"]}
    new = [c for c in after.list_chunks(limit=1000)["items"] if c["chunk_id"] not in old_ids]
    assert len(new) == 61
    records = {}
    for row in new:
        uid = row["unit_id"]
        if uid not in records:
            records[uid] = after.preparation.prepare(uid)
        source = next(s for s in records[uid].indexable_source_content
                      if s.source_pointer == row["source"]["pointer"])
        view = after.open_chunk(row["chunk_id"])
        text = source.text[row["source"]["start"]:row["source"]["end"]]
        assert view["source_slice"] == text
        assert sha(text.encode()) == row["source"]["text_sha256"]
        prefix = "\n".join(h["text"] for h in view["heading_context"])
        prefix = prefix + "\n\n" if prefix else ""
        assert tokenizer.count(prefix + text) == row["token_count"] <= 384
        assert view["verified_parent"]["consumer"]["llm_context"]["qualification"]["mandatory"]
        assert after.get_unit_chunks(uid).count(row["chunk_id"]) == 1
        assert after.get_chunk_sections(row["chunk_id"])  # Authorized parent roles retained.


def test_every_field_exactly_accounted_and_non_targets_unchanged(environment):
    before, after, _ = environment
    old = {o["unit_id"]: o for o in before.outcomes()}
    target_units = {c["unit_id"] for c in CASES if c["case_id"].startswith("M3R-")}
    rows = after.list_chunks(limit=1000)["items"]
    for outcome in after.outcomes():
        uid = outcome["unit_id"]
        if uid not in target_units:
            assert outcome == old[uid]
        for source in outcome["source_coverage"]:
            pointer = source["source_pointer"]
            intervals = [(r["source"]["start"], r["source"]["end"]) for r in rows
                         if r["unit_id"] == uid and r["source"]["pointer"] == pointer]
            intervals += [(r["display_start"], r["display_end"])
                          for r in outcome["unresolved"] + outcome.get("context_intervals", [])
                          if r["source_pointer"] == pointer]
            pos = 0
            for a, b in sorted(intervals):
                assert a == pos and b > a
                pos = b
            assert pos == source["source_characters"]
    summary = after.manifest["summary"]["by_document"]
    assert sum(d["source_characters"] for d in summary.values()) == 476769
    assert sum(d["chunked_characters"] for d in summary.values()) == 441910
    assert sum(d["context_only_characters"] for d in summary.values()) == 89
    assert sum(d["unresolved_characters"] for d in summary.values()) == 34770


@pytest.mark.parametrize("case", [c for c in CASES if c["classification"] == "REQUIRES_OWNER_REVIEW"],
                         ids=lambda c: c["case_id"])
def test_unsupported_fields_stay_wholly_unresolved(environment, case):
    _, after, _ = environment
    outcome = next(o for o in after.outcomes() if o["unit_id"] == case["unit_id"])
    unresolved = [r for r in outcome["unresolved"] if r["source_pointer"] == case["source_pointer"]]
    assert len(unresolved) == 1
    assert unresolved[0]["source_text_sha256"] == case["source_text_sha256"]
    assert unresolved[0]["display_end"] == case["source_characters"]
    assert not [r for r in after.list_chunks(unit_id=case["unit_id"], limit=1000)["items"]
                if r["source"]["pointer"] == case["source_pointer"]]


@pytest.mark.parametrize("case", [c for c in CASES if c["classification"] == "AUTHORIZATION_RESTRICTED"],
                         ids=lambda c: c["case_id"])
def test_protected_markdown_cannot_be_remediated(environment, case):
    before, after, tokenizer = environment
    uid = case["unit_id"]
    assert before.get_unit_chunks(uid) == after.get_unit_chunks(uid) == []
    record = after.preparation.prepare(uid)
    assert not record.indexable_source_content and record.protected_consumable_projections
    with pytest.raises(ValueError, match="not_indexable"):
        BoundedRemediator(after.preparation, tokenizer).remediate(record, case["source_pointer"])


def test_six_headings_only_retained_in_original_parent(environment):
    _, after, _ = environment
    headings = [c for c in CASES if c.get("content_type") == "heading"]
    assert len(headings) == 6
    assert sum(c["source_characters"] for c in headings) == 89
    for case in headings:
        o = next(o for o in after.outcomes() if o["unit_id"] == case["unit_id"])
        assert o["context_intervals"][0]["native_membership_roles_unchanged"]
        assert not [r for r in after.list_chunks(unit_id=case["unit_id"], limit=1000)["items"]
                    if r["source"]["pointer"] == case["source_pointer"]]
        assert o["chunk_ids"]  # The published body still has evidence children.


def test_frozen_witnesses_boundaries_and_182_reference_entries(environment):
    _, after, _ = environment
    results = json.loads((DATA / "CASE_RESULTS.json").read_bytes())["cases"]
    evidence = {r["case_id"]: r for r in json.loads((DATA / "STRUCTURE_EVIDENCE.json").read_bytes())["fields"]}
    assert Counter(c["outcome"] for c in results) == {
        "FULLY_RECOVERED": 9, "RESOLVED_AS_PARENT_CONTEXT": 6,
        "OWNER_REVIEW_REQUIRED": 7, "UNCHANGED_NON_INDEXABLE": 4}
    for c in results:
        if c["outcome"] != "FULLY_RECOVERED":
            continue
        e = evidence[c["case_id"]]
        source = case_source(c)
        chunks = [after.get_chunk(cid) for cid in c["new_chunk_ids"]]
        assert sum(r["source"]["end"] - r["source"]["start"] for r in chunks) == len(source.text)
        if e["method"] == "CPython_AST_top_level_statement_boundaries_only":
            assert e["allowed_top_level_cuts"] == c["witness"]["allowed_top_level_cuts"]
            allowed = set(c["witness"]["allowed_top_level_cuts"])
        elif e["method"] == "native_verified_table_rows":
            assert e["structure_sha256"] == c["witness"]["structure_sha256"]
            assert [[r["start"], r["end"]] for r in e["row_ranges_including_header"]] == c["witness"]["row_ranges_including_header"]
            allowed = {0, *[r[1] for r in c["witness"]["row_ranges_including_header"]]}
            assert chunks[0]["source"]["end"] > e["required_header_range"][1]
        elif source.content_type == "bibliography":
            assert len(e["entries"]) == 182
            assert [{"start": r["start"], "end": r["end"], "reference": r["reference_numbers"][0],
                     "marker_source_block": r["marker_source_block"], "marker_raw_start": r["marker_raw_start"]}
                    for r in e["entries"]] == c["witness"]["entries"]
            assert [n for r in chunks for n in r["reference_numbers"]] == list(range(1, 183))
            allowed = {0, len(source.text), *[r["start"] for r in c["witness"]["entries"]]}
        else:
            allowed = {0, len(source.text)}
        assert all(r["source"]["start"] in allowed and r["source"]["end"] in allowed for r in chunks)


@pytest.mark.parametrize("mutation", ["source", "qualification", "context", "publication", "headers", "memberships"])
def test_new_table_reader_rejects_stripped_or_forged_view(environment, mutation):
    _, after, _ = environment
    case = next(c for c in CASES if c["case_id"] == "M3R-19")
    row = next(r for r in after.list_chunks(unit_id=case["unit_id"], limit=1000)["items"]
               if r["source"]["pointer"] == case["source_pointer"])
    view = after.open_chunk(row["chunk_id"])
    if mutation == "source":
        view["source_slice"] += "0"
    elif mutation == "qualification":
        view["verified_parent"]["consumer"]["llm_context"]["qualification"] = {}
    elif mutation == "context":
        view["verified_parent"]["consumer"]["llm_context"]["required_context"] = []
        # Ensure mutation even where native required context is empty.
        view["verified_parent"]["consumer"]["llm_context"]["required_context"].append("forged")
    elif mutation == "publication":
        view["verified_parent"]["publication_identity"] = {}
    elif mutation == "headers":
        view["verified_parent"]["consumer"]["llm_context"]["source_content"] = []
    else:
        view["chunk"]["memberships"] = []
    with pytest.raises(ValueError, match="altered_stale"):
        after.validate_view(view)


@pytest.mark.parametrize("mutation", ["hash", "locator", "span", "header", "missing_cell", "serialization"])
def test_html_table_rejects_unbound_or_incomplete_cells(mutation):
    source = case_source(next(c for c in CASES if c["case_id"] == "M3R-02")).model_copy(deep=True)
    table = source.native_source["table"]
    if mutation == "hash":
        table["rows"][1][0]["raw_fragment_sha256"] = "bad"
    elif mutation == "locator":
        table["rows"][1][0]["dom_path"] = ""
    elif mutation == "span":
        table["rows"][1][0]["raw_character_span"] = [10, 2]
    elif mutation == "header":
        table["headers"][0] += "forged"
    elif mutation == "missing_cell":
        table["rows"][1].pop()
    else:
        source = source.model_copy(update={"text": source.text + "forged"})
    with pytest.raises(ValueError):
        table_atoms(source)


@pytest.mark.parametrize("mutation", ["hash", "span", "merged", "text"])
def test_pdf_table_rejects_false_source_accounting(mutation):
    source = case_source(next(c for c in CASES if c["case_id"] == "M3R-19")).model_copy(deep=True)
    structure = source.native_source["structure"]
    if mutation == "merged":
        structure["merged_cells_supported"] = True
    elif mutation == "text":
        structure["rows"][0][0]["text"] += "forged"
    else:
        member = structure["rows"][0][0]["member"]
        if mutation == "hash":
            member["span_sha256"] = "0" * 64
        else:
            member["end"] = member["start"]
    with pytest.raises(ValueError):
        table_atoms(source)


@pytest.mark.parametrize("mutation", ["duplicate", "skip", "missing_map", "false_member_hash"])
def test_bibliography_never_infers_absent_reference_boundaries(mutation):
    source = case_source(next(c for c in CASES if c["case_id"] == "M3R-20")).model_copy(deep=True)
    if mutation in {"duplicate", "skip"}:
        source = source.model_copy(update={"text": source.text.replace("[2] ", "[1] " if mutation == "duplicate" else "[3] ", 1)})
    elif mutation == "missing_map":
        source.native_source.clear()
    else:
        source.native_source["structure"]["paragraphs"][0]["source_member"]["span_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        numbered_reference_atoms(source)


@pytest.mark.parametrize("text", [
    "```python\nπ = 'Ω'\n\n@decorator\ndef f():\n    return '-12.5 all-MiniLM-L6-v2'\n\nz = 400\n```",
    '```python\nx = """first\nnot a new statement\nlast"""\ny = 1\n```',
])
def test_python_unicode_decorators_and_multiline_literals_keep_whole_statements(text):
    atoms, evidence = python_statement_atoms(owned_source("code_block", text))
    assert "".join(text[a["start"]:a["end"]] for a in atoms) == text
    cuts = evidence["allowed_top_level_cuts"]
    assert all(text[p:p + 1] not in {" ", "\t"} for p in cuts[1:-1])
    if "return" in text:
        assert text.index("return") not in cuts
    if "@decorator" in text:
        assert text.index("@decorator") in cuts and text.index("def f") not in cuts
    if "not a new" in text:
        assert text.index("not a new") not in cuts


@pytest.mark.parametrize("text", ["```typescript\nconst x = 1;\n```", "```python\nx = (\n```", "```python\na=1; b=2\n```"])
def test_unsupported_or_ambiguous_code_abstains(text):
    with pytest.raises((ValueError, SyntaxError)):
        python_statement_atoms(owned_source("code_block", text))


def test_oversized_atomic_function_and_string_not_truncated_or_executed(environment, tmp_path):
    _, _, tokenizer = environment
    base = next(iter(RECORDS.values())).model_copy(deep=True)
    kernel = BoundedRemediator(None, tokenizer)
    for text in ["```python\ndef f():\n" + "    print('protected -12.5 Ω')\n" * 200 + "```",
                 '```python\nx = """' + "complete text " * 500 + '"""\n```']:
        source = owned_source("code_block", text)
        r = kernel._remediate_verified(base, source)
        assert not r["chunks"] and len(r["unresolved"]) == 1
        assert r["unresolved"][0]["display_end"] == len(text)
    sentinel = tmp_path / "must-not-exist"
    text = f'```python\nopen({str(sentinel)!r}, "w").write("BAD")\n```'
    python_statement_atoms(owned_source("code_block", text))
    assert not sentinel.exists()


def test_unknown_text_needs_exact_published_media_qualification_and_budget(environment):
    _, _, tokenizer = environment
    case = next(c for c in CASES if c["case_id"] == "M3R-01")
    record, source = RECORDS[case["unit_id"]], case_source(case)
    kernel = BoundedRemediator(None, tokenizer)
    bad = record.model_copy(deep=True)
    bad.qualification["limitations"] = []
    result = kernel._remediate_verified(bad, source)
    assert not result["chunks"] and result["unresolved"]
    good = kernel._remediate_verified(record, source)
    assert good["chunks"][0]["source_text"] == source.text
    assert good["evidence"]["video_inspected"] is False
    for budget in [256, 385, 512]:
        with pytest.raises(ValueError, match="384"):
            kernel._remediate_verified(record, source, total_tokens=budget)


def test_replay_payloads_byte_identical_and_components_bound():
    for filename in ["chunks.jsonl", "unit-outcomes.json", "COVERAGE.json", "CASE_RESULTS.json",
                     "STRUCTURE_EVIDENCE.json", "FROZEN_CASE_REVIEW.json"]:
        assert (DATA / filename).read_bytes() == (WORK / "replay" / filename).read_bytes()
    manifest = json.loads((DATA / "manifest.json").read_bytes())
    for path, digest in manifest["components"].items():
        assert sha((ROOT / path).read_bytes()) == digest
    for path, digest in manifest["files"].items():
        assert sha((ROOT / path).read_bytes()) == digest


@pytest.mark.parametrize("mutation", ["source_text", "structure", "span", "qualification"])
def test_public_remediation_rejects_forged_prepared_evidence(environment, mutation):
    _, after, tokenizer = environment
    case = next(c for c in CASES if c["case_id"] == "M3R-02")
    record = after.preparation.prepare(case["unit_id"]).model_copy(deep=True)
    source = next(s for s in record.indexable_source_content if s.source_pointer == case["source_pointer"])
    if mutation == "source_text":
        record = record.model_copy(update={"indexable_source_content": [
            s.model_copy(update={"text": s.text + "forged"}) if s == source else s
            for s in record.indexable_source_content]})
    elif mutation == "structure":
        source.native_source["table"]["rows"][1][0]["text"] = "forged"
    elif mutation == "span":
        source.native_source["table"]["rows"][1][0]["raw_character_span"] = [-1, 2]
    else:
        record.qualification.clear()
    with pytest.raises(ValueError):
        BoundedRemediator(after.preparation, tokenizer).remediate(record, case["source_pointer"])
