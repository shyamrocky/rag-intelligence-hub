# Standard and illustrative HTML text references

> Current C10 checkpoint: the explicit selector `config/html-c10-admission-publication.json`
> adds one illustrative table unit, bringing the current HTML collection to427/457
> Sections in155 units, with30 intentional exclusions and no substantive HOLD.
> The426-Section release described below remains unchanged historical evidence.
> See [source-grounded consumption](qa-consumption.md) for the verified successor,
> mandatory ambiguity disclosure and separate RRF context.

The owner authorized a final text-first reassessment of all 457 Sections from the
eleven frozen HTML sources, including the earlier 116 HOLD Sections.
`combined-html-text-qa-1.0` is an explicitly selectable successor; it does not
change PDF/Markdown policy or source-level readiness.

The existing `shared.qa.assess` consolidates evidence and
`validation_reviews.make_decisions` alone issues scoped eligibility decisions.
The additional text evidence module reuses source/DOM/span verification and the
existing publication/reader interfaces. No parser, source record or original
Section identity is replaced. Corrections are additive projections under
`data/normalized/html/text-recovery-v1/`.

Each admitted unit has a reference class, mandatory limitations, permitted use and
prohibited inferences bound into its QA scopes and hash:

| Class | Meaning |
|---|---|
| `STANDARD_REFERENCE` | Complete, source-verified textual reference within its required scope; publisher truth is not independently certified |
| `ILLUSTRATIVE_REFERENCE` | Faithful, useful source text with explicit example, missing-context, visual or runtime limitations |
| `HOLD` | A material unresolved ambiguity or integrity defect prevents safe use |
| `EXCLUDED_NON_TEXT` | Image-only observation without usable explanatory text |
| `EXCLUDED_NON_KNOWLEDGE` | Navigation, presentation label or metadata without an additional knowledge payload |

Captured code inside tabs or collapsed containers can be quoted as an illustrative
snapshot payload. Its source language, container, characters and offsets are
verified; selection state, button-to-panel label mapping and runtime behavior are
not inferred. Language/package-manager variants remain separate units with their
own required context. Source code is never executed.

Figure observations can provide exact native figcaption text without qualifying
the image or its contents. Simple native HTML tables retain explicit headers,
rows, cells, original numbers and source spans. Merged or ambiguous grids are
rejected. These text facets do not establish general mathematical recognition or
independent numerical correctness. A printed native ASCII expression can be a
source reference without invoking PDF formula reconstruction. A caption-style
footnote marker remains a citation observation, with missing footnote content
explicitly unverified.

Publisher typos, intentionally invalid examples, placeholders and ambiguous worked
values are preserved and recorded as source issues. They are not silently repaired
or labeled parser defects. Illustrative fixture answers are not factual ground
truth. A materially ambiguous worked-score table remains HOLD despite exact cell
copying; readable surrounding prose is separately usable with its limitations.

The successor admits 426 unique Sections in 154 units: 288 standard and 138
illustrative. The 31 non-admitted Sections comprise one HOLD, seven image-only
observations and 23 navigation/presentation observations. Section totals use a
standard scope when one exists, otherwise an illustrative scope; scope-specific
warnings always remain binding. Context-only Sections are not independent passages.
The baseline's standard/illustrative split is a current classification audit, not
a retroactive alteration of earlier publications.

Load explicitly from repository root:

```python
import json
from pathlib import Path
from rag_hub.html_handoff import load_units

root = Path.cwd()
selection = json.loads(
    (root / "config/html-text-admission-publication.json").read_bytes()
)
units = load_units(root, **selection)
```

Retain `reference_classification`, `limitations`, `allowed_usage`, `forbidden_usage`,
`textual_projections`, all required member/heading/parent context, source citations
and publication bindings. Consuming only the body text would discard required
qualifications. The verified read-only loader rejects modified or stripped warnings,
forged projections, incomplete scopes and unapproved neighbors.

The earlier 239-Section and 341-Section selections remain valid and unchanged under
fingerprinted reader compatibility. New publication units identify predecessor
hashes when reference metadata is added; old unit records are never overwritten.
PDF's eight parents / nineteen Sections, expiration-warning behavior, C04 approvals
and historical decisions remain intact. Rollback means explicitly selecting a prior
publication with its matching compatibility release, never editing frozen receipts.

Durable results, every remaining exclusion, exact new IDs and source issues are in
`data/validation/html/text-recovery-v1/`. No chunking, embedding, indexing, ranked
retrieval, generation, acquisition or source-readiness execution is included.
