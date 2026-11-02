# Source-bound HTML context corrections

The subsequent [text-recovery successor](html-text-recovery.md) reassesses the
remaining text using explicit standard/illustrative references. This page records
the preceding checkpoint; its source observations and publication remain unchanged.

The owner authorized remediation of the 140 textual HOLD Sections from the first
HTML admission publication. The other 78 unsupported Sections remain unchanged.
`combined-html-context-qa-1.0` is an opt-in successor, selected by
`config/html-context-qa-successor.json`. Original captures, parsed observations,
normalized Sections, earlier policies and publications are preserved.

The additive overlay lives under `data/normalized/html/context-remediation-v1/`.
Its manifest binds the original corpus and the exact correction file. The release
fingerprints that overlay, its policy, the actual implementation and existing
shared components. No source text or Section identity is regenerated.

The existing `shared.qa.assess` still consolidates checks, and
`validation_reviews.make_decisions` alone publishes eligibility decisions. The
context evidence supplier cannot issue an approval. Original technical warnings
remain visible; a scoped resolution must establish complete source bindings and
context without overriding failed integrity checks or unknown restrictions.

Corrections cover complete static notes, list/nested-note ownership, paragraph and
code context, exact heading ancestry and source-bound dependencies. A narrow API
syntax check can distinguish typed inline calls and dollar-prefixed operator names
from the legacy mathematical regex. It does not waive actual formula, glyph,
fraction, table, visual or dynamic-content restrictions. Code remains attributed
documentation, including explicitly invalid examples; it is never executed or
certified as a working program.

For C09, the unique captured article H1 supplies a document-title projection. Its
original Section remains HOLD, and the projection explicitly states that it was
hidden in the capture. The same source article must own the visible body. The
projection is context metadata, never an admitted member or a visibility claim.
Other hidden elements and unverified alternative panels remain excluded.

The successor adds 102 Sections in 34 complete units. All previous 239 Sections
and 74 unit bindings remain valid and unchanged. The resulting handoff has 341
unique Sections in 108 units. The remaining 116 HOLD Sections comprise 38 context
dependencies and the original 78 unsupported Sections. These counts do not
establish source-wide readiness, independent visual correctness or publisher truth.

Load the new publication explicitly from the repository root:

```python
import json
from pathlib import Path
from rag_hub.html_handoff import load_units

root = Path.cwd()
selection = json.loads(
    (root / "config/html-remediated-admission-publication.json").read_bytes()
)
units = load_units(root, **selection)
```

Consumers must retain the complete required membership, heading and parent
context, source-context projections, source trees, citations, limitations and
publication bindings. The body `text` field alone is not permission to discard
required context. Context-only records are not independent answer passages.
No workspace files, reparsing, network or models are needed by this loader.

The original `config/html-admission-publication.json` still loads its exact
74 units through a fingerprinted compatibility check. Its identity, evidence and
scope are not relabeled. The new PDF reader compatibility manifest retains only
the original eight PDF parents and their publication-expiration warning policy.
PDF admission, Markdown policy, historical decisions and default QA remain unchanged.

Results, exact Section/unit IDs, exceptions and publication hashes are recorded
under `data/validation/html/scoped-admission-v2/`. Dashboard records reference sole
QA publications and contain no separate readiness logic. Rollback is an explicit
selection of the original publication while retaining the matching compatibility
release; no historical receipt is rewritten. A code rollback must restore a matching
fingerprint set, rather than editing hashes to hide implementation changes.

No chunking, embeddings, indexing, retrieval, generation, new acquisition or
source-readiness execution is part of this checkpoint.
