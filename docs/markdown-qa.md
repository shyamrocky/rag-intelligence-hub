# C04 Markdown QA admission and handoff

`markdown-complete-units-1.2` is integrated through the sole shared QA owner,
`shared.qa.assess`, and the existing decision function,
`validation_reviews.make_decisions`. The explicitly selected engineering release
is `combined-markdown-qa-1.1`; accepted earlier release identities are unchanged.

The frozen C04 source contains 158 source-verified Sections. The authoritative
publication admits 154: 40 exact historical approvals plus 114 additional
complete-unit-scoped decisions. Four discovery/navigation/footer/separator
Sections remain excluded (their engine decisions remain HOLD). There are zero
unresolved Section-level qualification cases. This does not grant whole-source
readiness, executable-code certification or independent truth of publisher claims.

The verified handoff returns **86 units**: **59 newly qualified complete units**
and **27 legacy-only units**. Other historical approvals are already members of
the complete units; all 40 historical decision objects remain unchanged. Units
may overlap in required context; consumers must preserve unit IDs rather than
flattening or independently admitting headings and fragments.

## Explicit read-only loading

```python
import json
from pathlib import Path
from rag_hub.markdown_handoff import load_units

root = Path.cwd()
selection = json.loads(
    (root / "config/markdown-admission-publication-v1-1.json").read_bytes()
)
units = load_units(root, **selection)
```

Without explicit `admission=`, `load_units(root)` continues to expose only the
40 historical code approvals. The persistent original corpus and immutable
historical ledger are not rewritten. The selected publication and issue register
are under `data/validation/markdown/scoped-admission-v1/final-v1-1/`; its manifest
pins the actual publication, policy enablement, evidence and release hashes.
Private data is Git-ignored; no third-party source content is in this document.
The initial integration candidate is superseded by the explicit `v1-1` selector;
its unselected artifacts remain preserved for audit, not current consumption.

## Mandatory consumption boundaries

Retain each complete unit's source citation, exact source spans, provider/Tab and
CodeGroup alternatives, heading ancestry, required context and documentation
limitations. Static source checks do not execute vendor code or contact services.

Four units have `consumption_contract=restricted-illustrative-projection-1.0`:
three contain documented original publisher code defects, and one contains an
unverified similarity-score example. Consume only their
`restricted_projection.consumable_text`, including all mandatory warnings.
Raw Sections reside in `source_evidence`, marked non-retrievable; restricted
`members` deliberately contain no `section.text` fallback. Unsupported metric
assertions and unrelated output remain provenance, outside the consumable view.
No corrected code, inferred score interpretation or verified measurement is
invented. Publisher defects remain unresolved source issues.

Before later serialization or use, call
`markdown_illustrative.validate_illustrative_handoff(root, unit)`. For a serialized
restricted payload, call `validate_restricted_payload(root, payload,
expected_unit_id=...)`. These guards reject stripped warnings, altered text,
missing headings/members, changed source identity/provenance, provider mixing and
changed scope. They verify consumption contracts; they grant no admission.
The loader replays authoritative QA evidence and rejects forged or incomplete
publications, stale hashes and altered source content.

## Cross-format preservation

The latest HTML selector and all HTML publications remain unchanged. A pinned
compatibility successor validates actual current code and the exact predecessor
validator observations. HTML replay compares all original validations, decisions,
scopes and content; only the known non-admission sampling fingerprint and its
strictly derived qualification stamp use their original source-bound values.
This does not run an alternate decision engine or waive a failed check.

A separately fingerprinted PDF reader retains the four original publication
hashes, eight complete parents/19 Sections, heading safeguards and attribution.
Publication expiration remains informational, with mandatory display metadata;
integrity, complete-parent and unapproved-neighbor checks remain enforced.
Historical **40 eligible / 1,634 HOLD** records remain unchanged. No chunking,
embedding, indexing, retrieval, generation or source-readiness execution is part
of this checkpoint.
