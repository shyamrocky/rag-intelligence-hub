# Experimental cross-encoder windowing contract

Policy: `ce-fullcoverage-two-window-1.0`. Decision reference: D050 / DRAFT-D050-P3-02.
The owner explicitly approved implementation and **preflight verification only** on
October 26, 2026. Neither RRF nor cross-encoder ranking execution is authorized.
Technical results require owner review. This is an isolated experimental adapter,
not an accepted M7/M8 release, evidence reader or source-admission mechanism.

Implementation: [windowing adapter](../tools/ranking/windowing_v1.py).
Synthetic controls: [focused tests](../tests/test_ranking_windowing_v1.py).
Private execution evidence is referenced by the existing canonical working tracker,
`workspace/rag-implementation/v1/MILESTONE_TRACKER.json`.

## Inputs and boundaries

The experiment retains its exact frozen 15-question dataset and 1,294 original
question–candidate memberships. A candidate is identified by its original exact
publication-qualified Chunk ID within a question; the same Chunk ID can occur in
different questions. Before preparing inputs, the private coordinator verifies the
frozen manifests, pinned runtime and model/tokenizer asset hashes, and reopens each
original search input through `EmbeddingArtifacts.open_bound_chunk` and the accepted
`embedding_input` projection. Original text, headings, question and full token hashes
must match sealed prior evidence. It does not rerun retrieval or M8 assembly.

The pure adapter accepts these already verified bindings. It cannot independently
authorize a supplied dictionary or replace the live gateway. Raw normalized source,
audit-only records, candidate scores and stored plan arrays are not alternate
evidence inputs. Complete-parent restrictions, classifications, qualifications,
source relationships and publication/citation bindings remain mandatory.

## Full-coverage question-aware windows

Use the exact acquired `cross-encoder/ms-marco-MiniLM-L6-v2` tokenizer revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a` in the unchanged locked environment.
The total limit is 512, including the full question and three pair special tokens.
Approved source headings are already part of the passage and consume passage budget.
No heading, prompt instruction or QA commentary is added or removed.

The 1,291 fitting pairs retain their original complete token sequences. Only the
three explicitly approved overflowing memberships use two overlapping token views:

| Question | Complete original length | Passage budget | Passage-token intervals |
|---|---:|---:|---|
| M9-Q05 | 529 | 488 | `[0,488)`, `[17,505)` |
| M9-Q25 | 513 | 482 | `[0,482)`, `[1,483)` |
| R02 | 523 | 494 | `[0,494)`, `[11,505)` |

Intervals are zero-based and half-open. Every window repeats the full unchanged
question. Token slices come from the once-tokenized original passage; no
decode/re-encode, rewriting, clipping, sentence inference or new source partition
is performed. Pair specials, token-type IDs and attention masks are explicitly
constructed and validated. Unexpected overflows or changed approved lengths fail
closed; no generic additional splitting is enabled.

The plan has exactly **1,297 future scoring inputs**, mapped to the same 1,294
memberships. Internal scoring-input handles are question/Chunk/policy-qualified;
they are not new authoritative Chunk IDs, independent retrieval records or labels.

## Display mappings and semantic limits

The fast tokenizer supplies offsets into the exact authorized display input,
including existing headings. Full pair offsets/sequence IDs are checked against
the separate full question and passage encodings. Offset order, range, token count,
window ranges and original token coverage must reconcile. A lossless partition
accounts for every original display character through token spans and hashed gaps.
Whitespace and normalizer-ignored characters remain bound to the original text;
the adapter does not claim that the model observes untokenized characters.

These are display-character mappings, not newly verified raw HTML/PDF source spans.
Original Section relationships, source locators and citation precision remain
unchanged. No exact raw offsets or page coordinates are fabricated.

Full coverage across windows does **not** reproduce whole-passage attention. A view
can cut through a code expression or WordPiece, omit leading context from that view,
or move absolute token positions. The affected illustrative code remains qualified;
neither view is asserted to be a complete code example or executable guidance.
The owner-approved internal scoring decomposition does not grant detached evidence
consumption. Accepted M8 still requires the complete authoritative parent.

## Aggregation prepared for future authorized inference

`aggregate_window_scores(records, scores, *, expected_memberships,
expected_plan_sha256)` is a pure function. During preflight it may receive
**synthetic values only**. It neither loads a model nor computes RRF.

Verify the current live source/QA bindings and experimental manifest before future
use; a saved plan or a self-supplied hash is not a bearer authorization. The plan
digest must come from verified, trusted experiment configuration. The function
validates all expected memberships, scoring handles and plan structure, then requires
exactly one finite numerical score for every planned scoring input. Unknown,
missing or duplicate handles, NaN/Inf and altered plans fail closed.

Use the maximum raw window score per original candidate, preserve every individual
window score, and sort within each question by descending score and ascending exact
Chunk ID for exact ties. No summation, score blending, calibration, new positives
or independent window ranks are introduced. Two-window candidates have additional
scoring opportunities; this max-score bias and the lack of joint context must be
disclosed in any later comparison. Frozen equivalence/group labels remain unchanged.

## Verification and execution boundary

Run synthetic tests without any model dependency:

```sh
UV_CACHE_DIR=/private/tmp/rag-uv-cache uv run --locked --offline --no-sync pytest tests/test_ranking_windowing_v1.py -q
```

The private preflight runner requires the existing locked embedding environment and
private frozen artifacts. It uses only the pinned local tokenizer; no classifier is
instantiated. Network access is disabled and neural module execution is denied in
both processes. Model tensor-loading checks from the prior sealed preflight are
reused only after exact asset hashes are reverified; they are not reported as fresh
model-load tests. It constructs and reproduces plans, then stops.

Do not replay a runner into a sealed output directory. A separately authorized
reproduction needs a new version/output, unchanged upstream bindings and preserved
prior results. No dependency changes, accepted release mutations, M7/M8 changes or
Git operations follow from this contract.

Before any real ranking, obtain separate explicit owner authorization. Actual
inference latency, memory, relevance quality and the RRF comparison remain
unmeasured by preflight. Synthetic ordering is not a relevance result. M10/M11 and
production adoption remain outside scope.
