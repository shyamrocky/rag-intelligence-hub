# Source-bound PDF text qualification

The full four-PDF recovery milestone adds an explicitly selected QA publication.
Original sources, canonical Sections, parsing/normalization behavior and previous
publications remain immutable. The historical default PDF reader retains its
original eight-parent scope. This does not establish whole-source readiness.

The sole QA owner remains `shared.qa.assess`; only
`validation_reviews.make_decisions` publishes Section eligibility. The optional
`pdf_text_admission` contribution supplies version-bound source/structure evidence.
Legacy diagnostic results are reused only after exact source/input and unchanged
validation-implementation verification. Their manual-required status is retained;
technical parser consistency is never converted directly to unrestricted approval.

Recovery overlays reside in `data/normalized/pdf/text-recovery-v1/`. They reference
original Unicode offsets, source hashes, page/block coordinates and immutable
canonical IDs. The overlays preserve block boundaries within source heading scopes,
not token-sized retrieval chunks. Original extracted text remains audit evidence.
Native replay and selected rendered-page inspection are machine checks, not an
independent human certification of every paragraph or source character.

The qualification policy admits faithful explanatory text without certifying
research conclusions. Tables require explicit printed cell/header associations;
partial page tables retain unresolved row dispositions. Caption-only units do not
certify figures. Mathematical references are limited to five previously
owner-verified PDF transcriptions; no model inference or generalized mathematical
PASS is introduced. Unresolved source notation and visual/structural dependencies
remain HOLD. Scoped sentence projections never grant use of an entire raw Section.

## Explicit consumption

```python
import json
from pathlib import Path
from rag_hub.pdf_text_handoff import load_units, serialize_consumption_unit

root = Path.cwd()
selection = json.loads(
    (root / "config/pdf-text-admission-publication-v1-1.json").read_bytes()
)
units = load_units(root, **selection)
# For serialized delivery, use the validating function, not raw Section JSON.
serialized = serialize_consumption_unit(root, units[0], selection=selection)
```

The verified reader hashes original snapshots and checks persisted source spans,
context, exact authoritative decisions, complete membership and release bindings.
It does not run a PDF parser, models, readiness, chunking or search. The complete
`llm_context` bundle includes SOURCE_CONTENT, separately identified QA_OBSERVATION
and mandatory QUALIFICATION. Structure fields are source-backed annotations,
not additional publisher prose. Mathematical critical-reference notes are owner
reference annotations, not claims quoted from the publisher. Original extraction
and presentation evidence under `audit_only` must never become a raw-text fallback.

Use whole-envelope filters such as `reference_classification="STANDARD_REFERENCE"`,
`source_id="C06"`, `has_known_issues=True` or `requires_context=True`. Filtering does
not remove qualifications or change a unit's classification. Exclusions/HOLD are
available in the inspection register, not returned as consumable text.

The eight earlier parents retain their exact text and reviewed context. Original
expiration remains informational and is propagated to related admitted units;
`publication_expiration.warning` and its `display_to_user_when_used` flag must be
surfaced whenever the content is used. Expiration never overrides a failed
integrity check. C02/C14 heading safeguards and Chroma attribution remain binding.

The new compatibility successor preserves existing explicit HTML/Markdown
selectors, original release identities, scopes and warning-bearing projections.
Only their already known component differences and immutable sampling-fingerprint
observations are reconciled. No historical approval/publication is rewritten.
The first PDF recovery release also remains replayable through the pinned
successor. There is no combined active-publication registry or changed default.

## Inspection and closure

`data/validation/pdf/text-recovery-v1/` contains the final closure report,
`PDF_QA_ISSUES.json`, `PDF_NON_ADMITTED_REGISTER.json`, exact-span accounting and
verified consumer examples. These inspection artifacts reference the authoritative
QA records; they do not grant eligibility. Sections, content-unit memberships,
context-only membership and partially projected Sections are counted separately.

Downstream RAG implementation requires a separate owner authorization.
