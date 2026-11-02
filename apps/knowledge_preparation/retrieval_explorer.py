"""Versioned single-question presentation of the historical Explorer, without search."""
import json
import math
import re

from tools.quality_dashboard.artifacts import ArtifactError

BASE = "data/visualizations/retrieval-pipeline-explorer-v1"
COMPLETION = "data/evals/benchmark-completion/v1"
VERSION = "retrieval-explorer-integration-1.0"


def historical(store):
    # load_completed has already verified the pinned Explorer output manifest.
    name = BASE + "/RAG_Retrieval_Pipeline_Explorer.html"
    from tools.quality_dashboard.adapter import explorer_html
    html = explorer_html(store)
    match = re.search(r'<script id="recorded-data" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not match or name not in store.verified:
        raise ArtifactError("UNVERIFIED_EXPLORER")
    return json.loads(match.group(1))


def read_text(store, name):
    from tools.quality_dashboard.artifacts import safe_path, sha
    path = safe_path(store.root, name)
    if name not in store.verified or sha(path) != store.verified[name]:
        raise ArtifactError("UNVERIFIED_EXPLORER_COMPONENT")
    return path.read_text()


def build(data, qid):
    """Project sealed native lists and Top-30, never calculate a new ranking."""
    store = data["store"]
    record = data["records"][qid]
    old = historical(store)
    previous = next((q for q in old["questions"] if q["question_id"] == qid), None)
    envelope = store.json(f"{COMPLETION}/m7/{qid}.json")
    case = store.json(f"{COMPLETION}/m8/{qid}.json")
    expected = record["reference"]["question_text_sha256"]
    if envelope["query_sha256"] != expected or case["question_id"] != qid:
        raise ArtifactError("EXPLORER_QUESTION_MISMATCH")
    refs = envelope["diagnostics"].get("native_inputs")
    if refs:
        names = {}
        for name, fingerprint in refs.items():
            store.bind(name, fingerprint)
            value = store.json(name)
            mode = value["retrieval_mode"]
            if mode in names or mode not in {"bm25", "vector"}:
                raise ArtifactError("EXPLORER_NATIVE_MODE_MISMATCH")
            names[mode] = name
    elif previous:
        names = {}
        for mode, ref in previous["native_sources"].items():
            store.bind(ref["path"], ref["sha256"])
            names[mode] = ref["path"]
    else:
        names = {mode: f"data/evals/intersection-selection/holdout-v1/native/{qid}-{mode}.json"
                 for mode in ("bm25", "vector")}
    if set(names) != {"bm25", "vector"}:
        raise ArtifactError("EXPLORER_NATIVE_LIST_MISSING")
    native, hits = {}, {}
    for mode, name in names.items():
        result = store.json(name)
        candidates = result["candidates"]
        if (result["query_sha256"] != expected or result["retrieval_mode"] != mode
                or len(candidates) != 50 or len({r['chunk_id'] for r in candidates}) != 50
                or result["parameters"]["top_k"] != 50 or result["parameters"]["candidate_depth"] != 50):
            raise ArtifactError("EXPLORER_NATIVE_IDENTITY_MISMATCH")
        metric = "bm25_score" if mode == "bm25" else "vector_distance"
        if any(r["rank"] != i or r[mode + "_rank"] != i or not math.isfinite(r[metric])
               for i, r in enumerate(candidates, 1)):
            raise ArtifactError("EXPLORER_NATIVE_RANK_MISMATCH")
        hits[mode] = {r["chunk_id"]: r for r in candidates}
        native[mode] = [{"chunk_id": r["chunk_id"], "document_id": r["document_id"],
                         "rank": r["rank"], "value": r[metric], "value_display": repr(r[metric])}
                        for r in candidates]
    # Metadata-only published vector export: no embedding model or Chroma connection.
    selector = store.json("config/vector-index-m5-v1-1.json")
    manifest = store.json(selector["manifest_path"])
    store.bind(manifest["payload_path"], manifest["spec"]["payload_sha256"])
    inventory = {r["id"]: r["metadata"] for r in store.json(manifest["payload_path"])["rows"]}
    ids = list(dict.fromkeys([r["chunk_id"] for mode in ("bm25", "vector") for r in native[mode]]))
    chunks, pool = {}, []
    for cid in ids:
        meta = inventory[cid]
        for mode, method_hits in hits.items():
            if cid in method_hits and any(method_hits[cid][key] != meta[key]
                                       for key in ("document_id", "format", "reference_classification")):
                raise ArtifactError("EXPLORER_CHUNK_IDENTITY_MISMATCH")
        chunks[cid] = old["chunks"].get(cid, {
            "document_id": meta["document_id"], "format": meta["format"],
            "reference_classification": meta["reference_classification"], "unit_id": meta["unit_id"],
            "lineage_precision": "See complete parent via authorized reader",
            "lineage_note": "Section/locator details unavailable in this saved metadata projection.",
            "section_ids": [], "source_field": {"pointer": "UNAVAILABLE", "start": "—", "end": "—", "content_type": "UNAVAILABLE"},
            "audit_reference": {"path": manifest["payload_path"], "pointer": cid},
            "citation_locators_sha256": "UNAVAILABLE", "parent_binding": {"publication_sha256": "UNAVAILABLE"},
            "locator_examples": [], "locator_count": 0, "publication_reference": {},
        })
        if chunks[cid]["unit_id"] != meta["unit_id"]:
            raise ArtifactError("EXPLORER_PARENT_MISMATCH")
        row = {"chunk_id": cid, "document_id": meta["document_id"]}
        for mode, metric in (("bm25", "bm25_score"), ("vector", "vector_distance")):
            hit = hits[mode].get(cid)
            row[mode + "_rank"] = hit["rank"] if hit else None
            row[metric] = hit[metric] if hit else None
        pool.append(row)
    rrf = []
    for i, row in enumerate(envelope["candidates"], 1):
        cid = row["chunk_id"]
        if cid not in chunks or row["rank"] != i:
            raise ArtifactError("EXPLORER_SELECTED_ID_MISMATCH")
        for mode, metric in (("bm25", "bm25_score"), ("vector", "vector_distance")):
            hit = hits[mode].get(cid)
            if row[mode + "_rank"] != (hit["rank"] if hit else None) or row[metric] != (hit[metric] if hit else None):
                raise ArtifactError("EXPLORER_SELECTED_NATIVE_MISMATCH")
        bc = 1 / (60 + row["bm25_rank"]) if row["bm25_rank"] else 0.0
        vc = 1 / (60 + row["vector_rank"]) if row["vector_rank"] else 0.0
        if row["rrf_score"] != bc + vc:
            raise ArtifactError("EXPLORER_SAVED_SCORE_MISMATCH")
        rrf.append(row | {"bm25_contribution": bc, "vector_contribution": vc, "rrf_score_display": repr(row["rrf_score"])})
    if len(rrf) != 30 or case["considered_chunk_ids"] != [r["chunk_id"] for r in rrf]:
        raise ArtifactError("EXPLORER_M8_SELECTION_MISMATCH")
    if {chunks[r["chunk_id"]]["unit_id"] for r in rrf} != set(case["considered_parent_ids"]):
        raise ArtifactError("EXPLORER_M8_PARENT_MISMATCH")
    question = {"question_id": qid, "question": record["question"], **native, "pool": pool, "rrf": rrf}
    bindings = {name: store.verified[name] for name in [*names.values(), f"{COMPLETION}/m7/{qid}.json", f"{COMPLETION}/m8/{qid}.json"]}
    return {"schema": VERSION, "questions": [question], "chunks": chunks,
            "reader_reference": old["reader_reference"], "manifest_bindings": bindings}, case


def html(data, qid):
    """Reuse the sealed template/model/UI with explicit, additive display adaptations."""
    payload, case = build(data, qid)
    store = data["store"]
    template = read_text(store, BASE + "/explorer.template.html")
    model = read_text(store, BASE + "/model.js")
    ui = read_text(store, BASE + "/app.js")
    # One question is supplied by Streamlit. No independent question control.
    template = template.replace('<select id="question-select">', '<select id="question-select" hidden>')
    template = template.replace('<label for="question-select" class="question-field">Choose a benchmark question</label>', '')
    template = re.sub(r'<header class="header-line">.*?</header>', '', template, flags=re.DOTALL)
    template = re.sub(r'<footer>.*?</footer>', '<footer>Recorded results · selected Top-30 only · no searches or provider calls</footer>', template, flags=re.DOTALL)
    template = template.replace('All 534 distinct chunks', 'All displayed chunks').replace('sealed Phase 3 output', 'sealed question-specific M7 output')
    template = template.replace('5 · Accepted RRF ranking', '5 · Selected RRF Top-30')
    template = template.replace('Follow one actual chunk', 'Follow one selected Top-30 chunk')
    ui = ui.replace("const span=make('div');const button=", "const span=make('div');if(!currentQuestion().rrf.some(r=>r.chunk_id===row.chunk_id)){span.append(make('span',row.chunk_id+' · outside selected Top-30','chunk-full'));return span;}const button=")
    ui = ui.replace('From the accepted Phase 3 output', 'From the saved selected M7 output')
    ui = re.sub(r"refs.push\(make\('p','15 questions .*?'\)\);", "refs.push(make('p','One selected question · 50 BM25 + 50 vector hits · 30 selected RRF candidates. Native union is display order, not a new ranking.'));", ui)
    # Readability-only successor: keep raw fields, arithmetic and sealed originals intact.
    template = template.replace('sealed question-specific M7 output', 'saved Candidate Retrieval & Ranking output')
    template = template.replace('<div id="score-breakdown"></div>', '<p class="small subtle">Each search contributes 1 / (60 + search rank) to the combined RRF score. A missing search contributes zero. The contributions are scores, not ranks; their sum determines the final RRF rank.</p><div id="score-breakdown"></div>')
    ui = ui.replace("'Native #'", "'Search rank #'")
    ui = ui.replace("['5 · Saved RRF','Final #'", "['5 · RRF ranking','Final RRF rank #'")
    ui = ui.replace('Saved final RRF score', 'Combined RRF score')
    ui = ui.replace('BM25 contribution', 'BM25 score contribution').replace('Vector contribution', 'Vector score contribution')
    ui = ui.replace('From the saved selected M7 output', 'From saved Candidate Retrieval & Ranking')
    ui = ui.replace('Verified parent Unit ID (recorded)', 'Evidence Unit ID (recorded)')
    ui = ui.replace('Native BM25 rank', 'BM25 search rank').replace('Native vector rank', 'Vector search rank')
    ui = ui.replace('Saved RRF score', 'Combined RRF score')
    # Escape closing tags and HTML metacharacters in JSON; publisher text is not included.
    serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    return template.replace('@@DATA@@', serialized).replace('@@MODEL@@', model).replace('@@UI@@', ui), payload, case
