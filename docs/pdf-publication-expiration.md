# PDF publication expiration — POC reading policy

Expiration is informational when reading the eight unchanged paragraphs already
approved in PDF-PROSE-COHORT-01. It does not extend the authorization timestamp,
create new decisions or authorize another publication. New QA execution continues
to enforce its authorization window.

Use the existing `pdf_prose_handoff.load_passages` call with the original published
handoff. For this exact cohort, the read-only implementation checks its installed
`config/pdf-publication-reader.json`, the unchanged historical combined QA manifest,
the four frozen publication hashes and all existing receipt/source/parent checks.
The accepted QA manifest is never rewritten to pretend it describes changed reader
bytes; the separate read configuration fingerprints actual reader implementation
and the unchanged QA/HTML dependencies. It cannot authorize a new QA run.

Every returned passage has `publication` metadata:

```json
{
  "status": "EXPIRED",
  "expires_at": "2026-10-23T06:12:23.097104+00:00",
  "warning": "Publication authorization expired on 2026-10-23T06:12:23.097104+00:00. This answer uses previously approved PDF content; its source integrity and complete-paragraph approval were verified.",
  "warning_code": "PDF_PUBLICATION_EXPIRED",
  "display_to_user_when_used": true,
  "retrieval_allowed": true
}
```

Before expiry the status is VALID, warning/code are null, and display is false.
At expiry the status becomes EXPIRED; the same verified paragraphs remain readable.
Malformed or not-yet-valid authorization remains an error. Source corruption,
changed publication hashes, missing receipts, incomplete approvals, unsupported
neighbors and changed context/attribution continue to reject. C02/C14 heading
projections, C06 claim attribution and all original citations are preserved.

The answer presentation hook is:

```python
from rag_hub.ui import format_answer_for_display

visible_text = format_answer_for_display(answer_text, used_passages)
```

Pass only evidence actually used by the answer. The helper appends the warning,
deduplicates it, rechecks expiry at display time, preserves answer/citation text, and rejects missing
publication display metadata. Do not display bare generation text for these
passages. The future Streamlit adapter must invoke this hook; a live answer UI
and generation/retrieval execution remain unimplemented and outside this change.
The helper itself performs neither generation nor retrieval.

Historical expiry-blocking reports describe the old reader. This document and the
current read-side configuration supersede that read policy only. Source-wide
fidelity, whole-source readiness, historical eligibility and unsupported HOLD
obligations are unchanged. No renewed owner attestation is needed to read the
same unchanged published content.
