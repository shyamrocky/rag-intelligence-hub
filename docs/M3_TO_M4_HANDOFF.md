> Forward status: the owner subsequently authorized M4-only local BGE embedding implementation under D030. The original handoff below retains its closure-date authorization boundary; see [M4 documentation](LOCAL_EMBEDDINGS.md) for the current workstream. M5 and later remain unapproved.

# M3-to-M4 technical handoff

**M3: OWNER_ACCEPTED / CLOSED — October 23, 2026 (D029).**
**M4: NOT STARTED / NOT AUTHORIZED.**

The accepted source-grounded input is 992 chunk representations from all 553
verified units across 16 documents. All prior M3 chunking exceptions are resolved
within admitted source fields. The 358 source QA HOLD Sections remain unavailable.
Acceptance authorizes neither model-weight downloads nor embedding generation.

## Pinned input and dependencies

| Dependency | Accepted identity |
|---|---|
| Chunk selector | `config/retrieval-chunks-m3-c14-scope-v2.json` |
| Chunk manifest SHA-256 | `f07828feea381507a76ed06e2b7d86f7bd79eab65c8f1188d70ce82cce92653c` |
| Unified selector | `config/unified-c14-scope-selection-v1.json` |
| Unified selector SHA-256 | `382c87b298fd94034910128ae7ceda3ac8730287d1ec1e505fd632874baf3c5e` |
| PDF QA selector | `config/pdf-c14-scope-admission-publication-v1.json` |
| PDF QA release | `combined-pdf-c14-scope-qa-1.0` (accepted engine-contract version reused) |
| PDF QA release SHA-256 | `b901d0623ba64b3f7f62e4ae56a96fe95b4c427062211614b976b866c9212e3d` |
| PDF publication manifest SHA-256 | `2589cbcb33d239c26c71d1201fdb610d8960833f9cc6dbbe57ed43aa8b30b976` |
| HTML selector | `config/html-c10-admission-publication.json` |
| HTML QA / publication SHA-256 | `a3150a29be457207a34c1bbc49149dd7b6c0407d1112869e7ad75d2b968b3b35` / `c009966ac7dd6abfc815a0d21dc350d386fc5e222a00ef295564248cb7b93ac8` |
| Markdown selector | `config/markdown-admission-publication-v1-1.json` |
| Markdown QA / publication SHA-256 | `d8a4b9989972bd853c6a1ef0dee0b5a017998c38d4b2fda4259747babe032779` / `46bcda194aef58ad5a91125b76240713ab742a2ec06ba986f2f728ad16f80852` |

The accepted M3 manifest binds the complete upstream file set, implementation
components, configurations and payload hashes. Its v2 envelope and structural
witness index reference unchanged full-rebuild payloads under
`data/chunking/m3-c14-scope-v1/`; no duplicate corpus copy or chunk rewrite is
required. Earlier selectors/publications remain exact historical replay paths.
They are not interchangeable with this selection. Original default unified and
dashboard selections are not silently switched.

The private owner receipt and current closure evidence are under
`workspace/rag-implementation/v1/m3-owner-closure-v1/`. These inspection/decision
records do not replace native QA publications or the live evidence gateway.

## Supported loading, iteration and lineage

Use the accepted explicit loader and reader in the existing locked chunking
environment; keep a single live snapshot for repeated access:

```python
import json
from pathlib import Path
from rag_hub.c14_unified_selection import load_c14_verified_corpus
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog

root = Path.cwd()
selected = json.loads((root / "config/retrieval-chunks-m3-c14-scope-v2.json").read_bytes())
assert selected["manifest_sha256"] == "f07828feea381507a76ed06e2b7d86f7bd79eab65c8f1188d70ce82cce92653c"
corpus = load_c14_verified_corpus(root)
catalog = QualifiedChunkCatalog(
    root, corpus, selector="config/retrieval-chunks-m3-c14-scope-v2.json"
)

offset = 0
while True:
    page = catalog.list_chunks(offset=offset, limit=100)
    for row in page["items"]:
        view = catalog.open_chunk(row["chunk_id"])
        catalog.validate_view(view)
        parent = view["verified_parent"]  # Full live validated evidence is mandatory.
        if "search_representation" in view:
            prospective_input = view["search_representation"]["text"]
        else:
            heading = "\n".join(h["text"] for h in view["heading_context"])
            prospective_input = (heading + "\n\n" if heading else "") + view["source_slice"]
        # Read-only M3 inspection; no embedding/model call is performed here.
    offset += len(page["items"])
    if offset >= page["total"]:
        break
```

`get_unit_chunks(unit_id)`, `get_chunk_sections(chunk_id)` and
`get_section_chunks(section_id)` preserve bidirectional Chunk ↔ Unit ↔ Section
relationships. `corpus.catalog.get_unit_sections(unit_id)` supplies exact native
membership roles. Section totals deduplicate canonical IDs. A supporting-heading
or required-context edge is not independent source evidence.

Chunk IDs bind configuration, publication-qualified parent and exact source
interval/hash. Changed publication identities require new qualified handles;
414 earlier PDF chunk identities changed in this accepted reconciliation, while
564 HTML/Markdown rows retained their exact IDs. Old IDs are not aliases. All
previous artifacts remain unchanged.

## Tokenizer and prospective embedding inputs

Selected M4 model: **`BAAI/bge-small-en-v1.5`**. Existing tokenizer/configuration
assets are pinned to revision **`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`** by
`config/bge-tokenizer-v1.json`, specification SHA-256
`03d41df1a646ed13d41bd8b485c573864da5821109e57750135bf94f0dbde577`.
The tokenizer JSON SHA-256 is
`d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`.
Individual vocabulary/configuration/license hashes are in that specification.
Runtime versions are tokenizers 0.22.2, LangChain Text Splitters 1.1.2 and
langchain-core 1.7.0, with the existing chunking lockfile. No embedding weights
have been acquired by M3 closure.

- Default total budget: **384**, including each view's literal source-heading
  prefix, delimiters and two special tokens (CLS/SEP).
- Four accepted selective 512 limits: C14 bibliography **385**, C06 prompt **474**,
  C16 examples **485** and **507** actual tokens. Maximum actual input: **507**.
- Document instruction: empty. No query instruction, QA observations,
  classifications, provenance JSON or qualifications are embedded as source text.
- No padding/truncation is enabled in the accepted tokenizer. M4 must verify
  that its actual model preprocessing agrees with these counts; it cannot
  silently truncate or broaden budgets.

Use the exact input reconstructed from the validated view above. Do not rebuild
prefixes with a newer heading policy, reflow hyphens, rewrite code, add warnings
to source text, flatten a parent envelope or use raw normalized data. The
selected slice and its search role never confer standalone evidence permission.

M4 must associate every embedding deterministically with the accepted catalog
manifest, exact Chunk ID, prospective input-text hash, tokenizer assets and its
separately pinned model-weight/runtime configuration. A model or preprocessing
change needs an explicit versioned embedding artifact, not reuse of incompatible
vectors under an existing identity. No vector format, pooling, normalization or
quality result is asserted by M3; M4 must specify and validate those details
within its separately approved scope.

## Qualifications that must survive

Native shared QA publishes decisions. The Unified Layer is the sole downstream
admission/qualification gateway. M0–M3 creates derivatives, never new eligibility.
Source text, context, QA observations and consumption qualifications stay separate.

All four protected Markdown units have primary source quotations for search,
with complete-unit/provider context, warnings and source-defect/score restrictions
retained. C06's printed prompt has two verified source-bound pieces; it is not
executed. C16 TypeScript examples use preserved whole examples or complete
source-supported statements; no executable-code correctness is certified.
C14 has an attribution-only 47-entry bibliography and three separate qualified
appendix narratives; no graph interpretation or unacquired-paper claims are
permitted.

The 99.98% metric describes per-unit authorized display fields: 477,977 of
478,066 characters emitted, 89 parent-only heading characters, no unresolved
intervals. It is not whole-corpus source fidelity. Another 1,441 protected Markdown
contextual quotation characters remain parent-only outside that denominator.
C14 additionally moved 145 source heading characters into required context;
six obsolete synthetic joins were retired without losing source characters.

Exact hash-verified source slices carry original offsets. Other accepted display
projections retain exact display intervals and parent-level citations; finer raw
offsets must not be invented. Seven inherited tokenizer unknowns, including the
recorded C01 diagnostics, remain visible. PDF expiration is an informational
warning for intact published content, never a waiver of integrity checks.
C02/C14 heading safeguards, C06 attribution, C10 QA scoring observations and
restricted Markdown projections remain mandatory.

Later consumers must rehydrate/validate the complete parent before using evidence
and show mandatory limitations/citations when relevant. Saving source text or a
JSON copy is not a detached authorization. Source-fidelity checks are not
publisher certification. Supported reader protections assume trusted local
application code; they do not prevent arbitrary Python or filesystem callers
from bypassing the application.

## M4 entry and stop boundary

Before separately authorized M4 execution:

1. Verify the exact accepted artifact, component and publication bindings.
2. Reproduce iteration over all 992 authorized representations and account for
   all 553 units; no unresolved M3 source intervals may be introduced.
3. Preserve immutable sources, QA, memberships, qualifications and accepted
   chunk inputs while preparing embedding artifacts.
4. Obtain explicit owner authorization before model-weight downloads or
   embedding generation; then pin and validate actual weights, preprocessing,
   output shape, finite values, ordering, resource behavior and reproducibility.

M4 generates and validates embeddings. It does not reinterpret QA, change source
scope, retune chunking, build a vector/lexical index or imply retrieval quality.
**No M4 implementation or downloads are authorized by this handoff.**
