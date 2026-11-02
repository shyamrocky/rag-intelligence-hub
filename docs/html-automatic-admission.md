# Opt-in HTML qualification and complete-unit handoff

The subsequent [bounded context-remediation successor](html-context-remediation.md)
adds source-supported textual scopes while preserving this original publication.
Its separate selector is `config/html-remediated-admission-publication.json`.

The owner authorized automated, evidence-based assessment of the eleven frozen
HTML sources and all 457 Sections. `combined-html-auto-qa-1.0` is an explicitly
selected successor, fingerprinted by `config/html-auto-qa-successor.json`.
The accepted Level 1.3, combined predecessor, raw sources, Sections and historical
QA publications retain their original identities. This does not qualify entire
sources or their visual, dynamic, mathematical or table content.

`shared.qa.assess` remains the sole QA owner. Its optional trusted `html_admission`
argument invokes source/structure evidence checks; `validation_reviews.make_decisions`
remains the only eligibility decision function. Without that argument all HTML
records retain their previous HOLD behavior. `ValidationPolicy` and the PDF/MDX
admission branches are unchanged. New `ScopedHtmlDecision` records require whole
content-unit consumption; legacy decision readers reject their unfamiliar basis.

The policy pins the corpus and prior evidence, verifies raw and snapshot bytes,
complete DOM trees, character spans, text, list/code structure, headings, source
order and required context. It rejects failed integrity checks, unsupported
content, hidden/dynamic dependencies and unresolved contextual restrictions.
Source heading-level gaps can use exact observed heading levels without inventing
intermediate headings. Source-defined adjacent paragraphs/lists/code remain
complete units, with ancestor heading evidence. An inherited code example must
carry its verified parent context; simple Python name-binding checks never execute
source code or certify program behavior. Unknown legacy reasons remain blocking.

Qualification is a bounded textual-source claim, not semantic truth, mathematical
correctness, CSS/browser fidelity, code executability or independent human review.
Publisher technical and benchmark claims retain explicit frozen-source attribution.
Machine suggestions are not human attestations. The authorization records the
owner's explicit automated-run instruction; it does not invent individual approvals.

Final receipts, decisions, complete unit bindings, exceptions and dashboard-ready
limitations live under `data/validation/html/scoped-admission-v1/`. Original
`data/validation/html/v2/` remains unchanged. The publication selector is
`config/html-admission-publication.json`; it pins the final manifest, authorization
and release hashes. A retained earlier unselected publication attempt is diagnostic
history, not a current handoff.

Load only complete admitted units from repository root, without parsing or network:

```python
import json
from pathlib import Path
from rag_hub.html_handoff import load_units

root = Path.cwd()
selection = json.loads((root / "config/html-admission-publication.json").read_bytes())
units = load_units(root, **selection)
```

The loader verifies the externally selected manifest, source and artifact hashes,
then replays the same QA evidence and sole decision function read-only. It rejects
partial, forged, stale or neighboring content even if an outer publication hash is
recomputed. Consumers must preserve `required_section_ids`, `heading_context`,
`required_parent_context`, list/code source trees, source citations and limitations.
Headings marked as context do not become independent answer passages. Structural
units have no retrieval chunk budget, overlap, embeddings or index.

`pdf-publication-reader-html-v1.json` is a fingerprinted compatibility successor
for reading the unchanged eight PDF parent approvals. It retains the exact original
publication allowlist and expiration-warning policy, while binding the changed
shared QA implementation. It cannot authorize new PDF content. The preceding
reader and QA manifests are preserved rather than relabeled.

Rollback means explicitly deselecting this HTML publication. Do not change its
immutable receipts or revoke unrelated PDF/MDX approvals. A code rollback must
restore a matching reader/release fingerprint set; editing a manifest hash to hide
changed implementation is prohibited. No application default is switched to new
HTML admission by merely importing these modules.
