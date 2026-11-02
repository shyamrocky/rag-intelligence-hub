# M3 bounded exception remediation

Status: implemented candidate, pending project-owner review. M4 remains unapproved.

The opt-in successor preserves all 893 previous chunk records and adds 61 source-bound chunks. All 550 verified units remain accounted for. It resolves 15 of the 22 original exception fields: nine fields yield chunks and six headings remain exclusively in their complete parents. Seven fields still require source-boundary review. Four protected Markdown projections remain non-indexable; they are authorization restrictions separate from those 22 fields.

| Measure | Original M3 | Bounded successor |
|---|---:|---:|
| Chunks | 893 | 954 |
| Units with chunks | 541 | 544 |
| Source-display characters emitted | 382,185 | 441,910 |
| Emitted share | 80.16% | 92.69% |
| Parent-context-only characters | 0 | 89 |
| Unresolved characters | 94,584 | 34,770 |
| Total source-display characters accounted | 476,769 | 476,769 |

These character counts sum authorized indexable fields across units, including existing shared source membership. They are not unique original-source character coverage. Protected Markdown projections are outside this indexable-field denominator. Full accounting does not mean full chunk emission, corpus-wide extraction correctness or retrieval quality.

## Source-supported handling

- Tables use existing published row/cell associations, preserving exact source serialization and the original suffix. The first slice includes headers and a body row. Subsequent slices require the complete original parent and its headers; they are not independently usable subtables. No synthesized repeated headers enter source text.
- The C02 bibliography uses 182 explicit printed reference labels witnessed inside hash-verified native source members. Labels need not begin a parser block. No author/year or hanging-indent boundaries are inferred.
- Five C16 Python examples use top-level CPython AST statement boundaries, including decorators. Functions, classes and multiline literals are not internally split. Parsing does not execute or certify publisher code. Source fences remain unchanged; fragments are not represented as independently executable examples.
- The C07 field is an already-qualified source media description, not video content or a transcript. Its existing limitation remains mandatory.
- Six C13 headings remain in their source-bound parent units. No heading-only retrieval evidence is created, and original QA membership roles remain unchanged.

The 384-token ceiling includes the literal approved heading prefix and tokenizer special tokens. There is no truncation or overlap added by remediation. A verified atomic element that cannot fit remains explicitly unresolved. Source content, required context, QA commentary and qualifications remain separate.

Seven fields remain unresolved: five TypeScript examples (18,065 characters), the C06 printed prompt (3,115), and the C14 bibliography (13,590). Existing evidence does not establish safe statement, line-number/payload or reference-entry boundaries respectively. No authorization restriction was weakened to process them.

## Opt-in loading and reproduction

The existing default selector and dashboard remain unchanged. Load the successor explicitly through the existing validated reader:

```python
from pathlib import Path
from rag_hub.chunk_catalog import ChunkCatalog
from rag_hub.unified_consumption import load_verified_corpus

root = Path.cwd()
corpus = load_verified_corpus(root)
catalog = ChunkCatalog(
    root, corpus,
    selector="config/retrieval-chunks-m3-remediation-v1.json",
)
rows = catalog.list_chunks(document_id="C02", limit=200)["items"]
view = catalog.open_chunk(rows[0]["chunk_id"])
catalog.validate_view(view)
```

A chunk slice is inspection data requiring its complete verified parent. The catalog does not grant independent evidence authorization. Do not flatten QA observations into indexable text or bypass mandatory table, code, context, projection or expiration qualifications.

Run from the repository root, using the existing locked chunking environment:

```sh
HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false TOKENIZERS_PARALLELISM=false uv run --project tools/chunking --locked python tools/chunking/remediate_catalog.py --output workspace/rag-implementation/v1/m3-remediation-v1/replay
```

All six payload files reproduce byte-identically. Relocating output changes manifest file paths and consequently its hash. Components and upstream bindings remain identical. No models, dependencies, source snapshots or QA publications are created or changed by this command.

## Bindings and review evidence

- Selector: [retrieval-chunks-m3-remediation-v1.json](../config/retrieval-chunks-m3-remediation-v1.json).
- Successor manifest SHA-256: `3fcd8430d5019146abc856b8af7c94032f62b807302811364d19e66f115745c2`.
- Predecessor manifest SHA-256: `d3aec5237a145e7b5f033f385aea5428edbda98c3cd7f7cde3cc25d5ae81a211`.
- Implementation: [chunk_remediation.py](../src/rag_hub/chunk_remediation.py) and [remediate_catalog.py](../tools/chunking/remediate_catalog.py).
- Controls: [test_chunk_remediation.py](../tools/chunking/tests/test_chunk_remediation.py).
- Private source-bound review, exact case mappings, before/after document counts, test results, replay and preservation evidence: `workspace/rag-implementation/v1/m3-remediation-v1/`.

Existing exact raw-span precision is retained where supported: 229 chunks have hash-verified raw slices; 725 have exact approved display slices with parent raw citations. No finer offsets are invented. Existing five tokenizer UNK diagnostics persist, with two additional C02 bibliography occurrences; source characters are retained. The two C01 affiliation-star diagnostics and both M2 configurations are unchanged.

No admission decisions, publication authorizations, frozen upstream schemas, default loaders or dashboard code changed. Owner review of M3 is the next checkpoint. This implementation does not authorize embeddings, indexing or retrieval.
