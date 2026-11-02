# M9 benchmark review checkpoint

M8 is **OWNER_ACCEPTED / CLOSED** for verified engineering integrity under the project owner's October 26, 2026 instruction. M9 benchmark preparation is authorized. **Stop for explicit approval of proposed questions and evidence labels before evaluation.** M10 remains unauthorized.

The canonical working milestone tracker remains `workspace/rag-implementation/v1/MILESTONE_TRACKER.json`. The additive M8 acceptance receipt and preparation evidence are under `workspace/rag-implementation/v1/m9-benchmark-review-v1/`. Historical M8 delivery artifacts remain sealed and unchanged.

## Review the proposed benchmark

Private, persistent benchmark artifacts are in `data/evals/m9/benchmark-v1/`:

- `REVIEW_PACKET.html`: one self-contained source/evidence review page, without retrieval rankings, external assets, scripts or prefilled approval decisions.
- `QUESTION_SET.json`: versioned questions and accepted release bindings.
- `PROPOSED_EVIDENCE_LABELS.json`: proposed relevance, required-parent groups, alternative representations, exact IDs, source spans, citation and qualification obligations.
- `REVIEW_EVIDENCE.json`: native live-validated parent snapshots for private owner review. Saved snapshots are not evidence authorizations.
- `BENCHMARK_MANIFEST.json`: exact review-file fingerprints.
- `OWNER_REVIEW_TEMPLATE.json`: optional blank consolidated decision template.

There are 29 machine-prepared questions: 26 proposed answerable and three unsupported controls, covering all 16 documents. Four questions require multiple evidence groups. Shared source passages have explicit alternative parent representations. This source-authored set uses previously exposed engineering material; it is not a blind held-out benchmark.

Review may be consolidated: explicitly approve the benchmark version and manifest fingerprint, or identify corrections by Question ID. Acceptance must confirm proposed answerability, relevance, required evidence groups and the bounded known-positive denominator. No human review, individual attestations or ground-truth acceptance is inferred from file creation or technical validation. Unjudged chunks are not asserted irrelevant. If a returned alternative was missed, record label uncertainty and version any subsequent correction consistently across modes.

Only authorized source content and qualified projections may support labels. Required context, QA observations and qualifications remain separate; QA observations cannot become publisher claims. C04 score interpretation, C06 benchmark attribution, C10 scoring ambiguity, C14 bibliography/appendix separation and PDF citation precision/expiration obligations remain binding.

## Evaluation after explicit label approval

The proposed fixed settings reuse accepted M7 defaults: all three modes, final top-K 10, candidate depth 50, RRF constant 60, no metadata filters. Compute rank-prefix results at K=1,3,5,10 on identical accepted questions. Evidence evaluation uses the top-10 results at 4,000/8,000/16,000/32,000 BGE-token scenarios through unchanged M8. These are evaluation budgets, not an M10 context-window decision. A secondary top-5/16,000 scenario may be used uniformly to distinguish excess candidate overhead; it must be reported separately.

Chunk Recall@K uses accepted known-positive Chunk IDs as its explicit denominator; it is not exhaustive semantic recall over unjudged content. Report macro and micro denominators and MRR@10. Also report parent/evidence-group coverage and all-required-group completeness, allowing any owner-approved source-equivalent parent within a group. This prevents repeated authorized representations from becoming artificial missing-evidence requirements. Unanswerable questions are excluded from recall/MRR denominators and analyzed separately. Returning a nearest neighbor or a valid M8 package is not evidence that an unsupported question is answered.

Measure retrieval discovery separately from inclusion of complete relevant M8 parents. Report missing candidates, failed integrity, ordinary budget omissions, insufficient evidence and label uncertainty distinctly. Do not convert an integrity error to a retrieval miss. Token accounting must distinguish exact final concatenated tokens, conservative per-block reserves, omitted whole-block tokens and non-additive component measurements. Source/qualification text embedded inside a restricted projection cannot be stripped or reclassified as unnecessary commentary.

The C14 bibliography reference question deliberately requires its full admitted parent. The approximately 84,064-token native envelope is inherited M8 engineering evidence, not a new M9 result. Current per-query sizes include contributing-chunk lineage and must be measured after approval. Compare source text, required context, citations, repeated metadata and lineage without changing the envelope. Any compact representation remains a separately authorized, versioned future proposal.

The historical C01 256-token M2 pilot exists, but does not supply a compatible full-corpus alternative M3/M4/M5/M6/M7 chain. Do not compare it numerically with the current 992-record release or create alternate chunks, vectors or indexes in this checkpoint. The private experiment proposal specifies the separate authorization required.

## Approved decision D041

- **Date:** October 26, 2026.
- **Decision:** Accept M8's exact selected engineering baseline; authorize staged M9 evaluation, with a mandatory owner ground-truth checkpoint before scoring or the evaluation dashboard.
- **Rationale:** Measure retrieval discovery, authorized evidence usability and token cost separately. Technical evidence availability is not relevance or answer quality.
- **Alternatives:** Automatically accept machine labels, score before review, treat unjudged content as known negatives, compact parents or generate an alternative index without approval. None is selected.
- **Status:** Owner-approved scope; benchmark proposals await owner acceptance. M9 results are not accepted. M10/M11, compact evidence, alternate pipelines, Git and backup operations remain unauthorized.

No M0–M8 source, QA, model, chunk, embedding, index, selector, runtime or dashboard implementation is modified by preparation. The existing eight Post-M11 deferred findings and separate source-control/recovery follow-ups remain in their canonical records. No new debt or admission authority is created.
