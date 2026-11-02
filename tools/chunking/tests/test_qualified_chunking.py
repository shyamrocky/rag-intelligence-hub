"""Opt-in qualified search contracts against frozen source and live gateway."""
import json
from itertools import pairwise
from pathlib import Path

import pytest

from rag_hub.chunk_catalog import ChunkCatalog
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
from rag_hub.qualified_chunking import QualifiedChunker, typescript_atoms
from rag_hub.unified_consumption import load_verified_corpus
from rag_hub.unified_models import sha

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "workspace/rag-implementation/v1/m3-qualified-recovery-v1"
DATA = ROOT / "data/chunking/m3-qualified-v2"
FROZEN = {c["case_id"]: c for c in json.loads((WORK / "FROZEN_BOUNDARIES.json").read_bytes())["cases"]}
EXPOSED = {r["case_id"]: r["record"] for r in json.loads((WORK / "SOURCE_INSPECTION.json").read_bytes())}


@pytest.fixture(scope="module")
def env():
    corpus = load_verified_corpus(ROOT)
    before = ChunkCatalog(ROOT, corpus, selector="config/retrieval-chunks-m3-remediation-v1.json")
    after = QualifiedChunkCatalog(ROOT, corpus)
    return corpus, before, after, PinnedBgeTokenizer(ROOT)


def all_chunks(catalog):
    rows, offset = [], 0
    while True:
        page = catalog.list_chunks(offset=offset, limit=1000)
        rows.extend(page["items"])
        if len(rows) == page["total"]:
            return rows
        offset += 1000


def new_chunks(env):
    _, old, after, _ = env
    old_ids = {c["chunk_id"] for c in all_chunks(old)}
    return [c for c in all_chunks(after) if c["chunk_id"] not in old_ids]


def test_old_954_records_configs_and_all550_units_preserved(env):
    corpus, before, after, _ = env
    old = {c["chunk_id"]: c for c in all_chunks(before)}
    current = {c["chunk_id"]: c for c in all_chunks(after)}
    assert len(old) == 954 and {k: current[k] for k in old} == old
    assert all(after.manifest["configurations"][k] == v for k, v in before.manifest["configurations"].items())
    assert len(after.outcomes()) == len(corpus.catalog.list_units()) == 550
    assert corpus.catalog.get_corpus_summary()["sections"] == 3040


@pytest.mark.parametrize("case_id", ["M3P-01", "M3P-02", "M3P-03", "M3P-04"])
def test_protected_source_only_parent_bound_representation(env, case_id):
    corpus, _, after, _ = env
    uid = FROZEN[case_id]["unit_id"]
    p = after.qualified_preparation.prepare(uid)
    native = p["record"]["protected_consumable_projections"][0]["native_source"]["restricted_projection"]
    assert p["record"]["indexable_source_content"] == []  # old M0 contract unchanged
    outcome = next(o for o in after.outcomes() if o["unit_id"] == uid)
    assert outcome["source_field_count"] == len(p["search_sources"]) > 0
    assert outcome["native_preparation_source_field_count"] == 0
    assert outcome["non_indexable"] == [] and outcome["historical_preparation_limits"]
    assert native["projection_sha256"] == FROZEN[case_id]["projection_sha256"]
    assert [s["native_source"]["segment"]["role"] for s in p["search_sources"]] == FROZEN[case_id]["expected_search_roles"]
    for s in p["search_sources"]:
        exact = s["native_source"]["segment"]
        assert s["text"] == exact["text"]
        assert s["consumption_scope"] == "complete_verified_unit_only"
        assert "Limitations remain mandatory:" not in s["text"]
        assert not s["text"].startswith("ILLUSTRATIVE_")
    rows = after.list_chunks(unit_id=uid)["items"]
    assert rows
    for row in rows:
        v = after.open_chunk(row["chunk_id"])
        assert v["search_representation"]["complete_parent_required"]
        assert v["verified_parent"]["consumer"]["llm_context"]["source_content"][0]["restricted_projection"] == native
        assert after.validate_view(v)
        # A search-only slice never passes the authoritative evidence gateway.
        with pytest.raises((ValueError, KeyError, TypeError)):
            corpus.evidence.validate(v["search_representation"])


def test_context_only_score_output_and_installation_never_independently_indexed(env):
    _, _, after, _ = env
    for cid in ["M3P-01", "M3P-02", "M3P-03", "M3P-04"]:
        p = after.qualified_preparation.prepare(FROZEN[cid]["unit_id"])
        pointers = {s["source_pointer"] for s in p["search_sources"]}
        assert all(c["pointer"] not in pointers for c in p["parent_only_projection_segments"])
        if cid == "M3P-01":
            assert any(c["role"] == "attributed_score_output_only" for c in p["parent_only_projection_segments"])


@pytest.mark.parametrize("mutation", ["warning", "source", "parent", "context", "publication", "heading", "search"])
def test_protected_reader_rejects_warning_context_parent_or_source_stripping(env, mutation):
    _, _, after, _ = env
    row = after.list_chunks(unit_id=FROZEN["M3P-02"]["unit_id"])["items"][0]
    v = after.open_chunk(row["chunk_id"])
    if mutation == "warning":
        v["verified_parent"]["consumer"]["llm_context"]["source_content"][0]["restricted_projection"]["warnings"] = []
    elif mutation == "source":
        v["source_slice"] += " unsupported repair"
    elif mutation == "parent":
        del v["verified_parent"]
    elif mutation == "context":
        v["verified_parent"]["consumer"]["llm_context"]["required_context"] = []
    elif mutation == "publication":
        v["verified_parent"]["publication_identity"] = {}
    elif mutation == "heading":
        v["heading_context"] = []
    else:
        v["search_representation"]["complete_parent_required"] = False
    with pytest.raises(ValueError, match="altered_stale"):
        after.validate_view(v)


@pytest.mark.parametrize("field", ["search_sources", "headings", "record", "parent_only_projection_segments", "complete_parent_required"])
def test_M0_successor_live_validation_rejects_mutated_preparation(env, field):
    _, _, after, _ = env
    p = after.qualified_preparation.prepare(FROZEN["M3P-01"]["unit_id"])
    p[field] = [] if isinstance(p[field], list) else {} if isinstance(p[field], dict) else False
    # Missing parent identity is rejected before a gateway lookup (KeyError);
    # bound-but-mutated payloads are rejected by whole-record comparison.
    with pytest.raises((ValueError, KeyError)):
        after.qualified_preparation.validate(p)


@pytest.mark.parametrize("cid", ["M3R-11", "M3R-13", "M3R-15", "M3R-16", "M3R-18"])
def test_TS_maps_match_preimplementation_exposed_source_boundaries(cid):
    source = EXPOSED[cid]["indexable_source_content"][1]
    atoms, e = typescript_atoms(source["text"])
    assert sha(source["text"].encode()) == FROZEN[cid]["text_sha256"]
    assert e["cuts"] == FROZEN[cid]["cuts"]
    assert "".join(source["text"][a["start"]:a["end"]] for a in atoms) == source["text"]


@pytest.mark.parametrize("body", [
    'const s = `first\nconst fake = 1;\nlast`;\nconst z = 1;',
    'const s = `value ${inputs.question}`;\nasync function f() {\n  const nested = [1,2];\n  return nested;\n}\nconst z = 1;',
    '// first\nconst x = {a: [1, 2], b: "semicolon;"};\n/* comment */\nconst z = 2;',
])
def test_TS_functions_objects_comments_and_templates_are_indivisible(body):
    text = '```typescript\n' + body + '\n```'
    atoms, e = typescript_atoms(text)
    assert len(atoms) in {2, 3}
    assert text.index("const z") in e["cuts"]
    assert all(text[a:b] for a, b in pairwise(e["cuts"]))
    if "const fake" in text:
        assert text.index("const fake") not in e["cuts"]
    if "const nested" in text:
        assert text.index("const nested") not in e["cuts"]


@pytest.mark.parametrize("body", [
    'const x = /a;b/g;\nconst z = 1;',
    'const x = a / b;\nconst z = 1;',
    'const x = `value ${call()}`;\nconst z = 1;',
    'const x = (1;\nconst z = 1;',
    'const x = "unterminated;\nconst z = 1;',
    'const x = 1\nconst z = 2;',
    'const x = `unterminated;\nconst z = 1;',
])
def test_unsupported_TS_syntax_abstains_without_guessing(body):
    with pytest.raises(ValueError):
        typescript_atoms('```typescript\n' + body + '\n```')


def test_each_new_chunk_live_source_budget_lineage_and_mandatory_parent(env):
    _, _, after, tokenizer = env
    for row in new_chunks(env):
        v = after.open_chunk(row["chunk_id"])
        assert tokenizer.count(v["search_representation"]["text"]) == row["token_count"]
        limit = v["search_representation"]["total_token_limit"]
        assert row["token_count"] <= limit <= 512
        assert limit == (384 if row["token_count"] <= 384 else 512)
        assert sha(v["source_slice"].encode()) == row["source"]["text_sha256"]
        assert after.get_chunk_sections(row["chunk_id"])
        assert v["verified_parent"]["consumer"]["llm_context"]["qualification"]["mandatory"]
        assert v["verified_parent"]["consumer"]["llm_context"]["qualification"]["complete_unit_only"]


def test_C06_source_prompt_partition_exact_boundaries_and_all73_members(env):
    _, _, after, _ = env
    cid = "M3R-21"
    uid = FROZEN[cid]["unit_id"]
    rows = after.list_chunks(unit_id=uid)["items"]
    assert [(r["source"]["start"], r["source"]["end"]) for r in rows] == [(0,918),(918,3115)]
    assert [r["token_count"] for r in rows] == [192,474]
    assert "".join(after.open_chunk(r["chunk_id"])["source_slice"] for r in rows) == EXPOSED[cid]["indexable_source_content"][0]["text"]
    assert len({s["block_id"] for r in rows for s in r["lineage"]["source_spans"]}) == 73


def test_C16_nested_headings_and_selective_whole_fields(env):
    _, _, after, _ = env
    for cid, expected in [("M3R-13",507),("M3R-15",485)]:
        rows = [r for r in after.list_chunks(unit_id=FROZEN[cid]["unit_id"])["items"]
                if r["source"]["pointer"] == "/consumer/llm_context/source_content/1"]
        assert len(rows) == 1 and rows[0]["token_count"] == expected
        v = after.open_chunk(rows[0]["chunk_id"])
        assert v["heading_context"] and all(h["native_type"] == "heading" for h in v["heading_context"])
        assert v["source_slice"] == EXPOSED[cid]["indexable_source_content"][1]["text"]


def test_C14_unchanged_deferred_and_no_new_QA_disposition(env):
    _, before, after, _ = env
    uid = FROZEN["M3R-22"]["unit_id"]
    assert before.get_unit_chunks(uid) == after.get_unit_chunks(uid) == []
    assert next(o for o in before.outcomes() if o["unit_id"] == uid) == next(o for o in after.outcomes() if o["unit_id"] == uid)
    with pytest.raises(ValueError, match="C14_deferred"):
        p = after.qualified_preparation.prepare(uid)
        QualifiedChunker(after.qualified_preparation, env[3]).chunk(p, p["search_sources"][0]["source_pointer"])


def test_all_field_intervals_and_unresolved_characters_accounted(env):
    _, _, after, _ = env
    chunks = all_chunks(after)
    for o in after.outcomes():
        for field in o["source_coverage"]:
            pointer = field["source_pointer"]
            intervals = [(r["source"]["start"], r["source"]["end"]) for r in chunks
                         if r["unit_id"] == o["unit_id"] and r["source"]["pointer"] == pointer]
            intervals += [(r["display_start"],r["display_end"]) for r in o["unresolved"] + o.get("context_intervals",[])
                          if r["source_pointer"] == pointer]
            end = 0
            for a,b in sorted(intervals):
                assert a == end and b > a
                end = b
            assert end == field["source_characters"]


def test_unknown_ID_and_unauthorized_scope_fail_closed(env):
    corpus, _, after, _ = env
    with pytest.raises(ValueError):
        after.open_chunk("rc:forged")
    for status in ["HOLD", "EXCLUDED"]:
        sid = corpus.catalog.list_sections(filters={"admission_status":status}, limit=1)["items"][0]["section_id"]
        with pytest.raises(ValueError):
            after.qualified_preparation.prepare(sid)
    p = after.qualified_preparation.prepare(FROZEN["M3P-01"]["unit_id"])
    with pytest.raises(ValueError):
        QualifiedChunker(after.qualified_preparation, env[3]).chunk(p, "/consumer/raw/unsupported")


def test_bound_files_and_independent_replay():
    manifest = json.loads((DATA / "manifest.json").read_bytes())
    for p,h in manifest["components"].items():
        assert sha((ROOT/p).read_bytes()) == h
    for p,h in manifest["files"].items():
        assert sha((ROOT/p).read_bytes()) == h
        assert (ROOT/p).read_bytes() == (WORK/"replay-v2"/Path(p).name).read_bytes()
