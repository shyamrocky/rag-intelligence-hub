# Persistent four-PDF corpus

The opt-in four-PDF completion store separates extraction evidence, normalized
views and authoritative QA evidence. Persisting a record does not approve it.
The accepted `maintained-pdf-level1-1.3` parser and its explicit release selection
are unchanged. `pdf-corpus-cleanup-1.0` is a separately fingerprinted correction
layer, not a new name for the unchanged parser release.

All paths below are relative to the repository root and Git-ignored:

| Path | Contents |
|---|---|
| `data/snapshots/<source-sha256>/` | Existing immutable original PDFs; not moved or duplicated |
| `data/parsed/pdf/four-pdf-poc-v1/<doc-id>/` | Original `ParsedBlock` observations, source manifest, parser component, classification and identity evidence |
| `data/normalized/pdf/four-pdf-poc-v1/<doc-id>/` | Atomic `Section` records, corrected source-span parents, audit, non-text sidecars, structure checks and per-record metadata |
| `data/validation/pdf/four-pdf-poc-v1/<doc-id>/` | Unmodified shared QA result/input and authoritative execution record |
| `data/normalized/pdf/four-pdf-poc-v1/manifest.json` | Versioned four-document index and SHA-256 artifact bindings |
| `data/normalized/pdf/four-pdf-poc-v1/candidate-prose.json` | Exact provisional prose review candidates; all HOLD |
| `data/evals/pdf/four-pdf-poc-v1/questions.json` | Frozen machine-prepared passage-linked questions; owner reference review pending |

`<doc-id>` is C01, C02, C06 or C14. The full private run/evidence handoff is
`workspace/pdf-remediation/phase3/pdf-corpus-completion-v1/README.md`.

## Loading without PDF parsing

From the repository root, with the existing environment:

```python
from pathlib import Path
from rag_hub.pdf_corpus import load_corpus, citation_lookup, approved_parents

corpus = load_corpus(Path.cwd())
document = corpus["documents"]["C01"]
parents = document["parents"]
sections = document["sections"]
blocks = document["blocks"]
locator = citation_lookup(corpus, "C01", parents[0]["id"])
assert approved_parents(corpus) == []  # no PDF parent admission was granted
```

The loader reads durable JSON and checks artifact/source hashes, schemas,
provenance and existing parent conformance. It does not parse PDFs, call models,
execute QA or consult workspace prediction files. Original snapshot bytes must
remain available for integrity verification. Local source text is untrusted data.

The returned records are ordinary dictionaries using the existing source,
`ParsedBlock`, `Section` and parent-span models. The additive manifest schema is
`persistent-pdf-corpus-1.0`. Offsets are Python Unicode code points, end exclusive;
bounding boxes retain original block scope rather than invented character boxes.
Parent text joins exact member spans with synthetic newlines. Original Section
heading paths remain intact; derived parent heading references and pending
context qualification are separate fields in `record-metadata.json`.

`corrections.json` retains original and replacement parent records, exact hashes,
source evidence bindings and an exact graph inverse. Raw observations are never
rewritten. Folios remain accounted excluded furniture. Caption typing does not
establish figure ownership or visual correctness. Native span completeness is
distinct from independent PDF glyph/paragraph correctness.

## Admission boundary

`rag_hub.shared.qa.assess` remains the only QA owner. Stored QA applies to unchanged
atomic Sections; corrected parents have conformance evidence but no admission
receipt. Every PDF record remains HOLD. Historical 40 eligible / 1,634 HOLD is
unchanged and belongs to its original ledger, not this four-PDF inventory.

A future chunker can read the persisted representation without reparsing, but
must consume explicitly admitted evidence. `approved_parents` deliberately returns
an empty list for this corpus and rejects unsupported promotion flags. It is a
fail-safe handoff, not a second eligibility engine or a future admission policy.

Source-level readiness, chunking, indexing and retrieval were not executed.
Specialized mathematics, tables, substantive visuals, code qualification,
ambiguous context and unresolved cross-record continuations remain excluded/HOLD.
