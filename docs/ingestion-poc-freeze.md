# Final POC ingestion acceptance and freeze

**HTML, Markdown and PDF ingestion/QA are FORMALLY CLOSED — PROJECT-OWNER ACCEPTED.** Decision date: **October 22, 2026**. Receipt creation UTC: `2026-10-23T01:53:39.992157+00:00`. This records the explicit owner instruction; it does not assert an authenticated identity, handwritten/digital signature or publisher/model certification.

| Format | Documents | Canonical Sections | Admitted | Excluded | HOLD | Verified units |
|---|---:|---:|---:|---:|---:|---:|
| HTML | 11 | 457 | 427 | 30 | 0 | 155 |
| Markdown | 1 | 158 | 154 | 4 | 0 | 86 |
| PDF | 4 | 2425 | 1991 | 76 | 358 | 309 |
| Total |16 |3040 |2572 |110 |358 |550 |

The PDF baseline preserves all 19 original approvals, eight reviewed parents, 246 prior recovery units and 63 residual units. Unit memberships overlap; 550 is not a Section or chunk count. Contextual-only Sections are not independently retrievable raw passages. PDF's seven new bounded projections and all 33 historical limited scopes retain their restrictions; 29 current Section records have uncovered intervals after additional body/context lineage accounting. These are distinct measures, not broader raw-text permission.

## Independent authoritative fingerprints

| Format/release | QA release SHA-256 | Publication/manifest SHA-256 |
|---|---|---|
| HTML `combined-c10-html-qa-1.0` | `a3150a29be457207a34c1bbc49149dd7b6c0407d1112869e7ad75d2b968b3b35` | `c009966ac7dd6abfc815a0d21dc350d386fc5e222a00ef295564248cb7b93ac8` |
| Markdown `combined-markdown-qa-1.1` | `d8a4b9989972bd853c6a1ef0dee0b5a017998c38d4b2fda4259747babe032779` | `46bcda194aef58ad5a91125b76240713ab742a2ec06ba986f2f728ad16f80852` |
| PDF `combined-pdf-residual-qa-1.0` | `72918218e944187e19088647a061d03d9536ad5b702387b19272373d91ebf425` | `796bc668888ab2537bba55d1b3ddd03500782b68d3e73239e2ebff87dea55c9e` |

The releases remain independent. Markdown's fingerprint identifies its source QA publication; HTML/PDF fingerprints identify their manifests. No combined admission authority or automatic selector is created.

## Receipts, static freeze and existing readers

- [PDF owner acceptance](../data/validation/pdf/residual-recovery-v1/OWNER_ACCEPTANCE.json) records acceptance of the exact published scope, exclusions, qualifications and residual HOLD. It supersedes only the pending owner-acceptance status of prior technical reports; those reports remain unchanged.
- [Existing HTML/Markdown acceptance](../data/validation/html-markdown-qa-closure/v1/OWNER_ACCEPTANCE.json) is preserved unchanged and is not reissued.
- [Combined freeze record](../data/validation/corpus-qa/ingestion-freeze-v1/CORPUS_INGESTION_FREEZE.json) is **INSPECTION_ONLY**. Its SHA-256 is `3c00d5df6f7cb15530c13c5161c24531df537eb9b1a585ef19bad8ceff8c86a5`. It is a descriptive project-stage freeze, not a runtime active-publication registry, replacement loader, filesystem lock or source-readiness execution.

| Format | Existing explicit selector | Existing verified reader |
|---|---|---|
| HTML | `config/html-c10-admission-publication.json` | `rag_hub.html_handoff.load_units(root, **selection)` |
| Markdown | `config/markdown-admission-publication-v1-1.json` | `rag_hub.markdown_handoff.load_units(root, **selection)` |
| PDF | `config/pdf-residual-admission-publication-v1.json` | `rag_hub.pdf_text_handoff.load_units(root, **selection)` |

The reader implementations and selector behavior are unchanged. Future material ingestion changes require separate owner authorization, validation and a new successor publication. Older versions remain available for exact historical replay.

## Preserved restrictions and deferred work

All 358 PDF HOLD cases are accepted as unavailable for the current POC: 156 visual graph/series relationships, 101 structural/context dependencies, 54 mathematical notation/attachment relationships, 45 table/diagram associations and two decoder/glyph defects. Their statuses remain HOLD, not EXCLUDED or ADMITTED. Some may be recoverable with future targeted source analysis or visual capabilities; no inherent irrecoverability is asserted. See the source-bound [PDF exception register](../data/validation/pdf/residual-recovery-v1/PDF_RESIDUAL_NON_ADMITTED_REGISTER.json), which remains inspection-only.

C02/C14 heading safeguards, Chroma attribution, mathematical/visual limitations, HTML C10's RRF context and separate QA ambiguity observation, and Markdown's four restricted illustrative units/three source code defects remain binding. SOURCE_CONTENT, QA_OBSERVATION and QUALIFICATION must stay distinguishable. STANDARD/ILLUSTRATIVE means qualified source representation, not independent publisher truth.

Original publication expiration timestamps are unchanged. Expiration remains an informational user-visible warning when unchanged approved content is used; integrity failures still block consumption. No owner reapproval is required merely to read the same unchanged expired publication.

**Requirement for the next architectural discussion:**

> Future chunking, indexing, retrieval and LLM consumption must be based on validated, admitted, publication-bound consumer units and their approved source-backed projections. Raw normalized Sections, inspection-only QA registers, historical HOLD decisions, and audit-only text must not be treated as unrestricted knowledge inputs.

Mandatory qualifications, warnings and related source context cannot be separated from admitted evidence. A unified loader, adapter/selector registry, chunker, index, vector database or LLM interface is neither designed nor implemented by this task. Dashboard, retrieval/generation and evaluation also remain deferred pending separate discussion and authorization.

## Focused closure verification

**1033 read-only reconciliation assertions PASS**, covering 321 distinct hash-bound artifacts, all 16 original source snapshots, all 3,040 canonical IDs and referenced authoritative decisions. The exact per-PDF counts, 358 HOLD categories, 550 unit inventory and old/new PDF unit hashes reconcile. Inspection registers retain their non-authoritative role.

The unchanged prior 875-test engineering evidence and successful native/publication/reader replay are reused after source/component/artifact integrity verification. This closure did not rerun pytest, lint/smoke, readers, parsing, QA admission, publication or publisher correctness analysis. These are closure integrity/accounting checks, not new parser, model or retrieval-quality measurements.

Verification detail: `workspace/ingestion-freeze/v1/VERIFICATION.json`; preservation evidence: `workspace/ingestion-freeze/v1/PRESERVATION_RESULTS.json`. No authoritative content, parser/normalizer, QA policy/decision, consumer reader or historical artifact changed. No Git staging, commit, merge or push. **Blockers: none found. Stop for the separate architecture discussion.**
