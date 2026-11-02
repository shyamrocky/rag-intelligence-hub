# Optional scoped PDF QA and passage handoff

`pdf-scoped-qa-1.0` implements the bounded eight-passage PDF admission extension.
Engineering authorization permits implementation and non-promoting validation;
owner content acceptance and authoritative eligible publication remain pending.
It does not change source-wide fidelity or source readiness.

## Ownership and selection

`rag_hub.shared.qa.assess` remains the sole QA owner. Its default-None
`pdf_prose_admission` argument accepts only trusted operator configuration.
Adapters, source documents and HTML controls cannot activate it. The existing
`validation_reviews.make_decisions` applies validated proofs and emits the new
`ScopedPdfDecision` type. There is no second eligibility engine.

Explicit selection requires `config/pdf-prose-qa-successor.json` and its trusted
SHA-256. The manifest pins actual implementation files, dependencies and the
lockfile. The accepted Level 1.3 parser manifest is unchanged. Its old hashes do
not describe the successor's three modified QA files; rollback copies and an
exact change inventory accompany the private implementation report. No parser,
normalization or default release dispatch was changed.

## Consolidated owner decision

One versioned consolidated record binds all eight passages, complete paragraph
parents, all 19 constituent Sections, original source/snapshot hashes, offsets,
locators and reviewed heading context. It has one PENDING/APPROVE_SCOPED/REJECT
decision, not 72 fabricated facet votes. Existing per-facet submissions remain
supported when genuinely supplied.

The pending record and independent recommendations live under
`data/validation/pdf/scoped-prose-admission-v1/`. Recommendations are recorded as
owner-reported independent review evidence, not an owner signature. Null review
times remain unknown. Explicit owner confirmation establishes the consolidated
attestation through the project's trusted operator boundary; JSON alone cannot
prove a person's identity.

An independently authorized QA execution must additionally bind the exact
approved receipt bytes, evidence and policy hashes, owner identity, and a valid
execution interval. Missing, changed, contradictory or expired inputs reject.
Neither implementation permission nor content approval alone authorizes eligible
publication. No new authoritative publication has been made.

## Context and admission safeguards

C02 uses the reviewed Introduction span, excluding the detached drop cap and
incorrect inherited title ancestry. C14 uses its source-backed Introduction
heading rather than the inherited arXiv-stamp path. Original persisted records
remain untouched. These corrections are separate context projections.

The C06 benchmark-limitation passage carries mandatory frozen-report attribution
and an explicit indication that a universal claim has not been independently
verified. This metadata is a downstream consumption obligation, not a claim that
future generation behavior has already been tested.

Admission is restricted to complete parent bundles. New hazards, failed checks,
high-risk content, incomplete bundles and neighboring Sections cannot qualify.
Original diagnostics and source-wide manual-required status remain unchanged.
Specialized content is excluded. Legacy typed decision readers reject the new
scoped type rather than silently treating constituent line fragments as generally
approved.

## Read-only offline use

`rag_hub.pdf_prose_execution.assess_persisted` replays the shared QA owner over
persisted observations and verified native-object evidence. It does not invoke a
parser, re-extract text, write a ledger, publish a pointer or execute readiness.
The explicit replay seam requires exact frozen source, block, Section, audit and
classification bindings. Default native-image verification remains unchanged.

`rag_hub.pdf_prose_handoff.load_passages` accepts externally trusted publication
paths/hashes and the explicit successor selection. Empty publications yield an
empty passage set. Each supplied publication must have schema
`pdf-scoped-QA-publication-1.0`, a source ID and the sole owner's `qa` result.
The reader verifies receipts, source/context bindings, complete member decisions,
unchanged diagnostics and exact policy. It replays the existing decision function
for verification; it does not implement a parallel admission policy.

Legacy fingerprints depend on insertion-ordered model JSON. The QA publication
retains the exact policy/validation serialization strings so sorted outer JSON
cannot invalidate their fingerprints. The consumer checks those strings against
the published and frozen records before verification.

Returned passages contain exact text, parent hash/ID, source spans, required
Section IDs, reviewed retrieval context, attribution and receipt/publication
bindings. Historical heading fields are not copied into retrieval metadata.
Raw observations and their historical metadata remain accessible in the original
corpus for audit. No chunking, search, model calls or generation occurs.

All reusable code is under `src/rag_hub/`; required evidence and images are under
`data/`. No runtime dependency on a temporary or workspace implementation is
introduced. Old corpus manifests and decisions remain immutable.

## Next boundary

To inspect the current empty handoff offline, use the operator-prepared handoff
configuration (its release hash must be trusted separately when publishing):

```python
import json
from pathlib import Path
from rag_hub.pdf_prose_handoff import load_passages

root = Path.cwd()
config = json.loads((root / "data/validation/pdf/scoped-prose-admission-v1/handoff.json").read_text())
passages = load_passages(
    root,
    config["publications"],
    release_path=config["release_path"],
    expected_release_sha256=config["expected_release_sha256"],
)
assert passages == []  # No authoritative scoped publication exists yet.
```

The owner can approve the single bound cohort record in one reply. Separately
explicit publication authorization then allows a controlled QA run and immutable
publication in the existing private validation hierarchy. Verify the resulting
handoff before requesting a separate chunking milestone. Another PDF parsing
cycle is not required for this subset. Whole-source and specialized-content
qualification remain outside this scope.
