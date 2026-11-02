# M0/M1 — Verified chunk preparation

Current acceptance: M0–M3 are owner accepted as of October 23, 2026 (D029). This unchanged `ChunkInput` contract is reused for the accepted 553-unit explicit selection. The original 550-unit freeze and M1 artifacts remain unchanged. [The accepted M3 catalog](RETRIEVAL_CHUNK_CATALOG.md) and [M4 handoff](M3_TO_M4_HANDOFF.md) define the current opt-in bindings; earlier M0/M1-only scope descriptions below are historical.

The project owner authorized M0 (contract) and M1 (preparation) of Master RAG Implementation Plan v1.0. Actual splitting begins at M2 and requires separate approval. These milestone IDs are separate from historical ingestion milestone numbering.

## Authority and scope

`rag_hub.chunk_preparation.ChunkPreparation` consumes the accepted unified catalog and live evidence gateway. It does not parse, normalize, infer relationships, assess QA, grant eligibility, or create retrieval chunks. Existing format-specific publications remain authoritative. The 550-unit / 3,040-Section ingestion foundation and dashboard are unchanged.

`ChunkInput` is a versioned Pydantic contract in `rag_hub.chunk_inputs`; its [JSON Schema](schemas/chunk-input-1.0.schema.json) rejects extra fields. A record loaded from disk is a preparation derivative, not an evidence authorization. Before consuming it, validate it against the current original gateway. Recomputing a hash never authorizes edited content.

## Separate representations

| Field | Meaning and permitted preparation behavior |
|---|---|
| `indexable_source_content` | Exact explicit `llm_context.source_content[i].text` and its native source structure. Candidate text only within the complete verified unit; no standalone eligibility is created. |
| `required_context` | Exact native context and supporting headings, including linked-unit dependencies. Not automatically independent retrieval evidence. |
| `qa_observations` | Ingestion analysis kept separate from publisher source text. Never indexed as publisher knowledge. |
| `qualification` | Mandatory complete-unit scope, limitations, and allowed/forbidden usage. Cannot be omitted because it is stored separately. |
| `protected_consumable_projections` | Native restricted warning-bearing renderings. Retained intact; M0/M1 does not strip warnings or expose alternate segments as indexable source text. |
| `memberships` / `section_bindings` | Exact native roles, canonical identity, provenance and source-locator references. Many-to-many relationships retained. |
| `citation_locators` / `publication_identity` | Original source and publication authorization bindings. |
| `consumer_metadata` | Remaining native consumer fields, including provider/tab boundaries, source fidelity, related evidence, duplicate native safeguards and expiration state. Not an additional source-text channel. |
| `evidence_sha256` / `record_id` | Deterministic bindings to the entire current gateway view and derived preparation, respectively; neither confers authority independently. |

Source entries retain native content types, table/equation structures, source citations, representation descriptions, and the original JSON pointer. Block-to-Section mapping uses explicit catalog block IDs; never textual similarity, adjacency or inferred headings. A context-only membership cannot be promoted into the source-content channel. Offsets retain their upstream units; display text can differ from raw span length because upstream reversible views/transcriptions exist. No invented one-to-one display-to-raw mapping is added.

The source field may contain an already accepted heading inside a native complete passage. Preparation preserves that exact boundary; it does not reclassify or extract the heading into a new independent passage.

## Validation and reproducibility

`prepare(unit_id)` fetches and validates a complete gateway bundle, checks membership and admitted Section identities, constructs separate fields, and rechecks the bundle. `validate(record)` reconstructs through that same gateway and compares the entire derived record. `serialize(record)` first validates. JSON Schema validation alone is insufficient.

Only metadata is cached, tied to the original live snapshot. The gateway continues enforcing source/publication hashes and filesystem integrity leases. No detached payload cache, raw Section fallback, new selector, QA publication or admission engine is introduced. Unsupported, forged, HOLD and excluded IDs fail safely.

Determinism applies to identical source/publication/component bindings and the same clock-derived warning state. PDF expiration remains informational and readable. When expiration changes the required warning, stale preparation must be refreshed through the gateway; content scope and the original expiration window do not change.

## Loading prepared C01 records

The private, durable output is `data/preparation/chunk-input-v1/C01/`:

- `chunk-inputs.jsonl`: 61 versioned complete preparation records.
- `manifest.json`: component, output and original loaded-snapshot fingerprints.
- `C01_PROFILE.json`: unit and unique-Section inspection statistics.
- `C01_PREPARATION_PREVIEW.html`: local static inspection preview, not an authorization.
- `chunk-input.schema.json`: schema copy bound by the preparation manifest.

```python
import json
from pathlib import Path
from rag_hub.chunk_inputs import ChunkInput
from rag_hub.chunk_preparation import ChunkPreparation
from rag_hub.unified_consumption import load_verified_corpus

root = Path.cwd()
preparation = ChunkPreparation(load_verified_corpus(root))
path = root / "data/preparation/chunk-input-v1/C01/chunk-inputs.jsonl"
records = [ChunkInput.model_validate(json.loads(line))
           for line in path.read_text().splitlines()]
for record in records:
    preparation.validate(record)  # Mandatory; fails if stale, edited, or stripped.
```

For fresh generation, choose a new versioned output if evidence or warning state changed:

```sh
uv run --locked python -m rag_hub.chunk_preparation --document C01 --output data/preparation/chunk-input-replay-v1/C01/chunk-inputs.jsonl
```

Existing outputs cannot silently be overwritten. No PDF parsing is needed. The accepted gateway performs its normal initial publication verification; later preparation lookups reuse it.

## Profiling limits and next decision

`rag_hub.chunk_profile` uses versioned `unicode-lexical-1.0` counts: Unicode word runs, apostrophe continuations and individual punctuation/symbol tokens. This is a deterministic descriptive tokenizer, **not** the BGE WordPiece tokenizer. It establishes no embedding input limit, special-token reserve or final chunk size. No tokenizer/model dependency or download is introduced.

Unit counts describe authorized displayed source text; context text is counted separately. Unique Section counts deduplicate canonical IDs. Span coverage unions explicit block/offset coordinates, so repeated headings and overlaps are not counted as fresh source coverage. Section token counts are supplied only for directly attributable display fields or hash-verified source slices/cells within gateway content; missing witnesses are null, not zero. Formula transcriptions and mixed views may have no exact per-Section token allocation. Coverage and denominators are reported rather than substituting unrestricted raw records.

Any 256/384-token comparison is a **lexical size screen**, not a model-budget check or a splitting result. M2 must qualify a pinned model-compatible tokenizer, account for retained context, and inspect native atomic structures before splitting. No overlap, embedding, lexical index, retrieval or new dashboard view exists in M0/M1.

## Approved decision

ID: RAG-M0-01. Date: October 22, 2026 (project-owner date). Status: owner-authorized direction; implementation delivered for review. Decision: prepare separate source, context, QA, lineage and citation/publication channels through the existing verified gateway; stop after M1. Rationale: preserve source fidelity and complete-unit obligations without embedding QA commentary or independently promoting context. Alternatives: flatten whole envelopes, read raw normalized Sections, or create another approval authority. Those alternatives violate the approved boundary. Technology choices for M2–M11 remain proposals until separately validated and authorized.

The authoritative working milestone tracker is `workspace/rag-implementation/v1/MILESTONE_TRACKER.json`, with a Markdown view beside it. Future sessions update that tracker and append checkpoint evidence rather than creating a competing master plan. Private artifacts remain ignored by Git.
