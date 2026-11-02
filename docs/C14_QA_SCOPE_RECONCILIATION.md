# C14 QA scope correction and M3 reconciliation

**OWNER_ACCEPTED / CLOSED — October 23, 2026 (D029).** The accepted final catalog is the v2 witness-bound envelope described below. Its full rebuild payloads remain under v1 to avoid duplication. Owner acceptance is recorded forward without changing historical delivery reports or QA publications. [M3-to-M4 handoff](M3_TO_M4_HANDOFF.md). M4 remains unapproved.

The C14-only successor separates a bibliography parent from three substantive
appendix sections. It preserves the original PDF, canonical Sections, parser
classifications and historical publications. Source text is reconstructed from
original spans; the original misclassification remains available as audit evidence.
This does not qualify figure contents or independently certify research results.

`rag_hub.c14_scope_correction` prepares the four proposed scopes from a frozen,
source-bound witness. The existing `shared.qa.assess` and
`validation_reviews.make_decisions` remain the only admission owners. The existing
PDF publication engine verifies the new policy, authorization, evidence, source
spans and complete membership. The new release has a distinct `release_id` and
fingerprint while reusing the accepted PDF engine-contract version. Execution
permission is recorded separately from owner acceptance of the resulting candidate.
Machine visual/geometry checks are not independent human review.

The corrected bibliography remains attribution-only. Its author-year entry map
uses printed hanging indentation and original line/block geometry, including
cross-column and cross-page continuations. Appendix A/B/C bodies have their own
source headings and mandatory reported-research/visual limitations. Headings are
required context, not independent search content. Printed notation, identifiers,
word wraps and source defects are retained without invented repairs.

## Explicit selection

The old `load_verified_corpus` default and dashboard remain unchanged. Opt in with:

```python
from pathlib import Path
from rag_hub.c14_unified_selection import load_c14_verified_corpus
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog

root = Path.cwd()
corpus = load_c14_verified_corpus(root)
catalog = QualifiedChunkCatalog(
    root, corpus, selector="config/retrieval-chunks-m3-c14-scope-v2.json"
)
```

The explicit unified selection is
`config/unified-c14-scope-selection-v1.json`. The native PDF selection is
`config/pdf-c14-scope-admission-publication-v1.json`. This opt-in composition
reuses the accepted native adapters, `VerifiedCorpus`, evidence validation and
filesystem leases. It checks unchanged admissions and source scopes in other
PDFs, and requires the exact source-bound C14 correction. It does not calculate
new eligibility or add a general active-publication registry.

The PDF manifest identity qualifies all PDF Unit IDs. Therefore even unchanged
PDF content receives new qualified handles. Rebuilt PDF chunks are regenerated
with the existing chunkers and compared with their previous source intervals,
tokens and lineage before receiving new identities. Unchanged HTML/Markdown
rows retain their original IDs and records. Historical selectors remain exact
replay paths; old handles are never aliases for the new publication.

## Reproduction and consumption

The deterministic builder is:

```sh
HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false TOKENIZERS_PARALLELISM=false \
UV_CACHE_DIR=/private/tmp/rag-uv-cache \
uv run --project tools/chunking --locked python tools/chunking/build_c14_successor.py \
  --output data/chunking/m3-c14-scope-v1
```

It reconstructs all M0/M1 preparation records through the selected gateway,
replays affected PDF chunking, validates both accepted C01 M2 budgets (256/384),
and consolidates all sixteen documents. The new C14 chunker uses only published
reference-entry/appendix boundaries. Default total budget remains 384 BGE tokens,
including source headings and special tokens, with bounded 512 exceptions only
when an indivisible qualified element requires one. No truncation is permitted.

Persistent preparation, validation, coverage and Chunk-ID reconciliation artifacts
are stored with the explicit successor under `data/chunking/m3-c14-scope-v1/`.
The source overlay is `data/normalized/pdf/c14-scope-correction-v1/C14.json`.
The QA publication is under `data/validation/pdf/c14-scope-correction-v1/`.

Call `catalog.open_chunk` and `catalog.validate_view` to obtain a slice with its
complete freshly verified parent. A chunk record or inspection register does not
authorize source evidence. Required context, warnings, citation and publication
bindings must remain attached; raw canonical content is never a fallback.

Coverage is reported per authorized unit display, separately from unique Section
accounting. Moving appendix headings into required context changes the indexable
text denominator; removed synthetic inter-section separators are not missing
source characters. Protected Markdown contextual quotations remain parent-only.
No embedding, indexing, retrieval ranking or generation is implemented here.

After the full rebuild, consolidate the unchanged payloads with historical boundary-witness bindings:

```sh
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked python \
  tools/chunking/bind_c14_witnesses.py \
  --selector config/retrieval-chunks-m3-c14-scope-v2.json
```

The final manifest and structural-witness index are under `data/chunking/m3-c14-scope-v2/`. They reference the unchanged M0/M1/M2/chunk payloads under `m3-c14-scope-v1/`, avoiding duplicate corpus storage. Original witness handles remain audit references, with explicit current handles; the superseded mixed C14 scope has no alias. No chunk record is patched.
