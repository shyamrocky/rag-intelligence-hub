# M3 protected Markdown representation assessment

Status: bounded assessment complete; pending project-owner review. No indexing candidate was implemented or published. M4 remains unapproved.

All four C04 units remain **ADMITTED** for complete, qualified consumption through the existing verified gateway. Their absence from M3 chunks is a representation limitation, not a new QA eligibility decision. The previous M3 register's historical authorization-restriction label must not be read as rejection of these admitted units.

## Measured per-unit result

The existing pinned BGE tokenizer measured each exact `restricted_projection.consumable_text`, its required source headings and two special tokens. No warning, source character or required context was removed.

| Native Unit suffix | Example | Projection + special tokens | With required headings | Excess over 384 | Result |
|---|---|---:|---:|---:|---|
| `24d530f6a7ce22b998da` | Attributed similarity-score example | 380 | 401 | 17 | Representation blocked |
| `2aeb8bc33b558e34a3e8` | OpenSearch publisher example | 741 | 757 | 373 | Representation blocked |
| `3db2ac55b9cfb2e5a0ae` | Voyage AI publisher example | 448 | 465 | 81 | Representation blocked |
| `57ad43dbb596d19c635b` | Isaacus publisher example | 440 | 457 | 73 | Representation blocked |

The first projection alone fits, but discarding its three required headings would bypass the complete-context requirement. The OpenSearch rendering also exceeds the tokenizer's 512-token model ceiling. Raising the 384-token budget is outside this authorization and would not resolve every case.

`consumable_text` is an authoritative warning-bearing presentation containing source quotations, labels and QA restrictions. These counts assess its indivisible complete representation; they are **not** permission to flatten QA commentary into source knowledge for embedding. Its internal `segments` are provenance for the native rendering, not separately authorized indexable fragments. Deduplicating warnings, extracting selected segments, repairing defective code, summarizing or shortening the rendering would change the authorized representation.

## Contracts and ownership

The existing [Markdown contract](markdown-qa.md), [unified contract](UNIFIED_CONSUMPTION_LAYER_DESIGN.md) and [M0/M1 separation](CHUNK_PREPARATION_CONTRACT.md) remain unchanged:

- Only the exact native restricted projection, with its warnings, is consumable for these units.
- Source Sections remain audit/provenance evidence, without a raw-text consumer fallback.
- Complete native membership, headings, provider/context boundaries, qualifications, citations and publication bindings remain mandatory.
- The existing evidence gateway rehydrates and validates the full approved parent before consumption; constructing a new preparation object confers no permission.
- A catalog entry is not another QA authority or a substitute for parent verification.

Parent-bound search handles followed by authoritative parent rehydration remain a reasonable design pattern. However, none of the four unchanged complete representations fits this milestone's budget. No partial handle payload, special protected-input channel or new reader behavior was implemented to work around that result.

## Reconciliation and recommendation

Existing totals remain **954 chunks**, **550 verified units**, **544 units producing chunks**, and **four admitted protected Markdown units with zero chunks**. Markdown retains 86 verified units and 204 chunks from 82 units. Per-unit source-display coverage remains 92.69%; protected renderings remain outside that source-only denominator.

The existing catalog and all selectors are unchanged. The seven unrelated structural exceptions were not remediated. No upstream QA, sources, canonical records, unified/M0–M3 implementation, dashboard, model or dependencies changed.

Recommendation: accept this bounded assessment and preserve the four units' existing complete-unit access. If searchable routing for them remains necessary, separately define and authorize a compact, source-bound **search-only representation**: specify its permitted source fields, distinguish QA restrictions from publisher content, require full parent rehydration and prohibit standalone evidentiary use. That would be a new representation contract requiring review, not an assumed permission to split these protected projections. No such contract or candidate was implemented here.

Exact source/publication hashes, complete Unit IDs, memberships, source spans, token counts, test logs, reproducibility and preservation evidence are retained privately under `workspace/rag-implementation/v1/m3-protected-markdown-v1/`. The result is machine-verified engineering evidence, not new human content approval or retrieval-quality evaluation.
