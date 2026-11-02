# Unified Verified-Consumption Layer v1

## Accepted explicit M3 successor — October 23, 2026

The original 550-unit default and public contract described below remain unchanged. Owner-accepted M3 selects the C14 successor explicitly through `rag_hub.c14_unified_selection.load_c14_verified_corpus`, reusing these native adapters, `VerifiedCorpus`, membership checks, evidence gateway and filesystem leases. Its pinned selection has 553 units with the same 3,040 Sections and 3,727 memberships; it does not add an admission engine or mutable active registry. See [accepted catalog](RETRIEVAL_CHUNK_CATALOG.md), decision D029 and [M4 handoff](M3_TO_M4_HANDOFF.md). Do not pass the successor selector to the historical fixed-selection constructor or alias old PDF handles. M4 remains not started and not authorized.


Status: implemented under project-owner authorization; verification and owner review recorded separately in [the verification report](UNIFIED_CONSUMPTION_LAYER_VERIFICATION.md).

This Python library provides two interfaces over the accepted text-first POC baseline: a metadata-only inspection catalog and a publication-bound evidence gateway. It adds no QA decisions, ingestion, chunking, ranking, server or UI. The [ingestion freeze](ingestion-poc-freeze.md) remains unchanged.

## Components and authority

| New component | Responsibility |
|---|---|
| `rag_hub.unified_models` | Frozen adapter records, memberships and deterministic JSON |
| `rag_hub.unified_bindings` | Verify the frozen selections, supporting bindings and filesystem integrity leases |
| `rag_hub.unified_adapters` | Adapt the unchanged HTML, Markdown and PDF loaders |
| `rag_hub.unified_consumption` | Immutable loaded snapshot, catalog, evidence gateway and relationship index |

`shared.qa.assess` and `validation_reviews.make_decisions` remain the sole QA owners. The native loaders perform their existing publication/source verification on construction, including their established QA replay. The unified layer neither calls QA independently nor issues an admission. Later lookups never call native loaders, parsers or QA.

The descriptive freeze and closure indexes supply inventory, integrity references and inspection metadata. They do not authorize payloads: admission membership must reconcile with the selected publications **and** the native verified unit inventory. A discrepancy fails construction; no silent repair or status downgrade occurs.

The new library pins the exact accepted freeze hash and verifies its separately bound selections. This fixed scope is not a mutable active-publication registry. An optional `selection_set` must exactly match all three accepted selections. Historical selections continue working through their original interfaces, but cannot substitute for the unified baseline.

## Independently selected publications

| Format | Existing explicit selector | Release SHA-256 | Publication/manifest SHA-256 |
|---|---|---|---|
| HTML | `config/html-c10-admission-publication.json` | `a3150a29be457207a34c1bbc49149dd7b6c0407d1112869e7ad75d2b968b3b35` | `c009966ac7dd6abfc815a0d21dc350d386fc5e222a00ef295564248cb7b93ac8` |
| Markdown | `config/markdown-admission-publication-v1-1.json` | `d8a4b9989972bd853c6a1ef0dee0b5a017998c38d4b2fda4259747babe032779` | `46bcda194aef58ad5a91125b76240713ab742a2ec06ba986f2f728ad16f80852` |
| PDF | `config/pdf-residual-admission-publication-v1.json` | `72918218e944187e19088647a061d03d9536ad5b702387b19272373d91ebf425` | `796bc668888ab2537bba55d1b3ddd03500782b68d3e73239e2ebff87dea55c9e` |

The three identities are preserved separately. Markdown's historical forty-only default is never called by the adapter. No native defaults or loader files change.

## Actual native contract differences

| Format | Native behavior retained | Adapter projection |
|---|---|---|
| HTML | `qa-consumption-unit-1.0`, separate source/QA/qualification objects, explicit content/context IDs, C10 linked RRF unit, publication-bound exclusion views | Preserve the exact qualified `llm_context`, related evidence, citations and publication identity; audit-only payload remains opaque |
| Markdown/MDX | Typed Pydantic Sections, separate heading context, provider/tab/alternative metadata, documentation scope, four warning-bearing restricted projections; no common consumer envelope | Ordinary admitted member text and headings are projected from the already verified native unit; preserve source metadata, documentation scope, provider/context boundaries. Restricted units expose **only** their native restricted projection, with mandatory warnings; original `source_evidence` remains opaque |
| PDF | Scoped consumer envelope, reversible source spans, separately attached heading evidence, qualified tables/math/captions and historical expiration metadata | Preserve exact qualified consumer fields. Native `audit_only.original_extracted_text` and original observations are never a consumer fallback |

Markdown's `STANDARD_REFERENCE`/`ILLUSTRATIVE_REFERENCE` mapping is inherited inspection vocabulary, not a new native QA classification. The native labels (including `B_illustrative_documentation_example`, source-defect and metric restrictions, or null legacy labels) remain visible alongside it. Historical `Section.index_status` remains source evidence; current membership derives from the accepted successor publication.

One C05 HTML unit has a required approval scope broader than its consumable text/context. These extra Sections are recorded as `approval_scope_dependency`, mapped to required context for inspection. No extra source text is injected. Four historical PDF parents have separately reviewed heading spans outside their original body membership: these are explicit additional supporting-heading edges, checked against currently admitted Sections, not added body text. These are preserved native distinctions, not repaired contracts.

## Catalog and bidirectional relationship index

`corpus.catalog` offers:

- `list_documents()` and `get_corpus_summary()`.
- `list_sections(document_id=None, filters=None, offset=0, limit=100)`.
- `get_section(section_id)` and `get_section_qa_details(section_id)`.
- `list_units(document_id=None, filters=None)`.
- `get_unit_sections(unit_id)` and deterministic `export()`.

Section IDs remain exact canonical IDs. Unit IDs include format, a digest of the accepted native publication identity, and the original unit ID. This prevents cross-format collisions and old-publication aliases. Display names or rehashed caller payloads cannot mint a valid unit.

Every admitted Section must have at least one verified unit membership. HOLD and excluded Sections remain catalog-addressable and have no authorized unit memberships. Each Section response contains linked unit IDs and exact roles; unit-to-Section responses preserve all roles, including multiple roles for one Section. A source-bound required linked-context relationship can add an edge without merging units.

Common roles are `content`, `projection`, `required_context` and `supporting_heading`; `native_role` preserves their actual origin. PDF source-member content is conservatively labeled projection because the native contract authorizes source spans, not unrestricted Sections. `scope_limited_projection` additionally preserves existing documented interval restrictions; it must never be interpreted as permission for raw access when false.

Context-only is calculated across **all** memberships. Counts use unique canonical Section IDs, never edge totals. Distinct units sharing headings/text are retained. The catalog distinguishes membership from independent consumption: `raw_section_is_independent_consumption_unit` is always false.

Filters select whole records/units by format, document, admission status, display classification, issue type, reason, context-only membership, unit association, known issues or context requirements. Unknown filter keys fail. Pagination uses stable canonical-ID order with explicit offset/limit and next offset. `get_section_qa_details` includes scoped unit qualifications and source/decision references, without exposing raw evidence text.

Catalog exports are **INSPECTION_ONLY** and cannot be loaded as authorization. Ordinary responses contain citations, locators, reasons and evidence references, not raw HOLD/excluded text. An independently authorized future dashboard evidence viewer is outside this milestone.

## Verified evidence and immutable loaded state

`corpus.evidence` offers:

- `load_verified_units(filters=None)`.
- `get_verified_unit(unit_id)`.
- `validate(value)` and `serialize(value)`.

Every returned item retains the complete consumer bundle, publication identity, source citations, native binding handle, exact memberships and scope qualifiers. `SOURCE_CONTENT`, `QA_OBSERVATION` and `QUALIFICATION` stay distinct. Native envelopes are held privately as immutable serialized bytes; public handles confer no standalone authorization. No generic native/raw-text accessor is added.

Construction hashes the accepted publications, snapshots, canonical artifacts, policies/components and supporting inventory. It validates each format through its original loader and checks bindings again after loading. In-memory unit/catalog state is serialized to immutable bytes behind read-only mappings; public responses are detached copies.

Every access checks filesystem leases (resolved path, device/inode, size, nanosecond mtime and ctime) for bound files. A changed, missing or redirected file permanently invalidates that loaded snapshot. Reloading performs hashes and native verification again. This avoids full source hashing/QA on every lookup while detecting ordinary in-place writes, same-size edits, timestamp restoration, file replacement and symlink changes. It is a trusted local Python process, not protection against privileged filesystem adversaries or hostile code that can monkeypatch the running process. No caller-authored disk cache can be imported as a verified corpus.

`validate` compares the entire submitted bundle to the trusted loaded value, not a supplied/recomputed hash. Removed warnings/context, forged identities, changed text/classification and partial units fail. For PDF, expiration is refreshed through the unchanged native `display_metadata` function at access: expired intact publications remain readable with mandatory user-visible warning metadata. A pre-expiration payload must be refreshed before serialization after expiration; no authorization window is extended. Catalog identity remains deterministic across clock-only expiration changes.

## Usage and downstream boundary

```python
from pathlib import Path
from rag_hub.unified_consumption import load_verified_corpus

corpus = load_verified_corpus(Path.cwd())  # full native verification once
summary = corpus.catalog.get_corpus_summary()
page = corpus.catalog.list_sections("C04", limit=10)
section = corpus.catalog.get_section(page["items"][0]["section_id"])

metadata = corpus.catalog.list_units(filters={"format": "markdown"})
unit_id = metadata[0]["unit_id"]
relationships = corpus.catalog.get_unit_sections(unit_id)
unit = corpus.evidence.get_verified_unit(unit_id)
serialized_complete_bundle = corpus.evidence.serialize(unit)
```

One-shot `load_verified_units(root, selection_set=None)` and `get_verified_unit(root, unit_id, selection_set=None)` conveniences also exist. Reuse a loaded corpus for repeated access rather than rebuilding it per unit.

Future chunking must take **only verified whole consumer bundles**, preserving citations, required context, provider boundaries and all restrictions; no chunker is implemented here. Future dashboard work should use the catalog and QA details, never infer current eligibility from historical HOLD or inspection counts. Neither publication inspection nor a Section's ADMITTED label grants raw text access.

No dependencies, databases, model calls, source acquisition, parser corrections, shared QA changes, publication changes, UI, retrieval or generation are introduced. Performance is measured as adapter loading/lookup behavior, not RAG quality.

## Decision record

ID: UVCL-01. Date: October 22, 2026 (owner project date). Status: implementation authorized; delivered candidate awaits owner review. Decision: use a thin read-only catalog/evidence layer over the three independently accepted readers, with publication-qualified unit IDs and bidirectional memberships. Rationale: unify inspection and authorized consumption without duplicating QA or flattening format restrictions. Alternatives: rewrite native readers to a common schema; import a raw combined corpus; build a registry/database. These are unnecessary or outside scope. Authority: the owner's Unified Verified-Consumption Layer v1 request and additional bidirectional-index requirement.
