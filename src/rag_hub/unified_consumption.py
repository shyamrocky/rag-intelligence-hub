"""Unified read-only catalog and verified evidence gateway for the accepted POC.

This module never assesses QA, publishes decisions or offers raw Section text.
Native loaders perform their existing full validation once per loaded snapshot.
"""

import json
from collections import Counter
from types import MappingProxyType

from rag_hub.unified_adapters import html_adapter, markdown_adapter, pdf_adapter
from rag_hub.unified_bindings import INDEX, PDF_ISSUES, SELECTORS, accepted_bindings
from rag_hub.unified_models import DocumentRecord, SectionRecord, encode, sha

SCHEMA = "unified-consumption-catalog-1.0"
FILTERS = {
    "format", "document_id", "admission_status", "reference_classification", "issue_type",
    "reason", "context_only", "has_units", "has_known_issues", "requires_context",
}


def matches(row, filters):
    if set(filters) - FILTERS:
        raise ValueError("unknown_unified_filter")
    for key, value in filters.items():
        if key == "issue_type":
            if not any(value == x.get("issue_type") for x in row.get("issues", [])):
                return False
        elif key == "has_units":
            if bool(row.get("unit_ids")) != value:
                return False
        elif row.get(key) != value:
            return False
    return True


def dynamic_evidence(unit):
    value = unit.evidence()
    consumer = value["consumer"]
    if "publication_expiration" in consumer:
        from rag_hub.pdf_publication import display_metadata

        expiration = display_metadata(consumer["publication_expiration"])
        consumer["publication_expiration"] = expiration
        observations = consumer["llm_context"]["qa_observations"]
        observations[:] = [o for o in observations if o.get("issue_id") != "PDF_PUBLICATION_EXPIRED"]
        if expiration["warning"]:
            observations.append({
                "kind": "QA_OBSERVATION", "severity": "WARNING",
                "issue_id": "PDF_PUBLICATION_EXPIRED", "explanation": expiration["warning"],
                "display_to_user_when_used": True,
            })
        if "qa_observations" in consumer:
            consumer["qa_observations"] = list(observations)
    return value


class Catalog:
    """Inspection metadata only, including HOLD/excluded records and both graph directions."""

    def __init__(self, snapshot):
        self._snapshot = snapshot

    def get_corpus_summary(self):
        self._snapshot._check()
        return json.loads(self._snapshot._summary)

    def list_documents(self) -> list[DocumentRecord]:
        self._snapshot._check()
        return [json.loads(v) for _, v in sorted(self._snapshot._documents.items())]

    def get_section(self, section_id: str) -> SectionRecord:
        self._snapshot._check()
        try:
            return json.loads(self._snapshot._sections[section_id])
        except KeyError:
            raise ValueError("unknown_canonical_section") from None

    def get_section_qa_details(self, section_id):
        row = self.get_section(section_id)
        result = {k: row[k] for k in (
            "section_id", "admission_status", "native_disposition", "reason", "issues",
            "issue_ids", "evidence_refs", "publication_identity", "citation_locators",
            "memberships", "context_only", "scope_limited_projection")}
        result["unit_qualifications"] = [
            {"unit_id": uid, **{k: json.loads(self._snapshot._unit_metadata[uid])[k]
                                for k in ("qualification", "issues", "memberships")}}
            for uid in row["unit_ids"]]
        return result

    def list_sections(self, document_id=None, *, filters=None, offset=0, limit=100):
        self._snapshot._check()
        if (type(offset) is not int or type(limit) is not int
                or offset < 0 or not 1 <= limit <= 1000):
            raise ValueError("invalid_catalog_pagination")
        selected = dict(filters or {})
        if document_id is not None:
            selected["document_id"] = document_id
        rows = [json.loads(v) for _, v in sorted(self._snapshot._sections.items())]
        rows = [r for r in rows if matches(r, selected)]
        return {"total": len(rows), "offset": offset, "limit": limit,
                "items": rows[offset:offset + limit],
                "next_offset": offset + limit if offset + limit < len(rows) else None}

    def list_units(self, document_id=None, *, filters=None):
        self._snapshot._check()
        selected = dict(filters or {})
        if document_id is not None:
            selected["document_id"] = document_id
        return [r for r in (json.loads(v) for _, v in sorted(self._snapshot._unit_metadata.items()))
                if matches(r, selected)]

    def get_unit_sections(self, unit_id):
        self._snapshot._check()
        unit = self._snapshot._find(unit_id)
        return [vars(m) for m in unit.memberships]

    def export(self):
        """Deterministic inspection-only export. Never accepted as evidence input."""
        self._snapshot._check()
        return encode({
            "schema": SCHEMA, "authority": "INSPECTION_ONLY",
            "summary": json.loads(self._snapshot._summary),
            "documents": {k: json.loads(v) for k, v in sorted(self._snapshot._documents.items())},
            "sections": {k: json.loads(v) for k, v in sorted(self._snapshot._sections.items())},
            "units": {k: json.loads(v) for k, v in sorted(self._snapshot._unit_metadata.items())},
        })


class EvidenceGateway:
    """Only complete publication-bound unit payloads; Section IDs grant no access."""

    def __init__(self, snapshot):
        self._snapshot = snapshot

    def get_verified_unit(self, unit_id):
        self._snapshot._check()
        result = dynamic_evidence(self._snapshot._find(unit_id))
        self._snapshot._check()
        return result

    def load_verified_units(self, *, filters=None):
        # Filtering selects entire already-authorized units without reclassification.
        ids = [u["unit_id"] for u in self._snapshot.catalog.list_units(filters=filters)]
        values = [dynamic_evidence(self._snapshot._find(uid)) for uid in ids]
        self._snapshot._check()
        return values

    def validate(self, value):
        if not isinstance(value, dict) or not isinstance(value.get("unit_id"), str):
            raise TypeError("not_a_verified_unit")
        expected = self.get_verified_unit(value["unit_id"])
        if encode(value) != encode(expected):
            raise ValueError("altered_or_warning_context_stripped_unified_unit")
        self._snapshot._check()
        return True

    def serialize(self, value):
        self.validate(value)
        return encode(value)


class VerifiedCorpus:
    """An in-process immutable snapshot. Construct through load_verified_corpus only.

    Python trusted application code is the boundary (not an adversarial process
    sandbox). No export/import path can substitute cached caller-authored JSON.
    """

    def __init__(self, bound, rows, units, sources, expected_counts, selections):
        self._bound = bound
        self._units = MappingProxyType({u.unit_id: u for u in units})
        if len(self._units) != len(units):
            raise ValueError("duplicate_unified_unit_identity")
        native_keys = {(u.format, u.native_id) for u in units}
        if len(native_keys) != len(units):
            raise ValueError("ambiguous_native_unit_identity")
        section_edges = {sid: [] for sid in rows}
        for u in units:
            for m in u.memberships:
                if m.section_id not in rows:
                    raise ValueError("unified_membership_missing_section")
                row = rows[m.section_id]
                if row["admission_status"] != "ADMITTED" or row["document_id"] != u.document_id:
                    raise ValueError("unified_unauthorized_or_foreign_membership")
                section_edges[m.section_id].append({
                    "unit_id": u.unit_id, "role": m.role, "native_role": m.native_role})
        identities = {}
        for u in units:
            identities[u.format] = json.loads(u.publication_json)
        for sid, row in rows.items():
            edges = sorted(section_edges[sid], key=lambda e: (e["unit_id"], e["role"], e["native_role"]))
            if (row["admission_status"] == "ADMITTED") != bool(edges):
                raise ValueError("unified_admitted_section_without_verified_unit")
            row.update(
                memberships=edges, unit_ids=sorted({e["unit_id"] for e in edges}),
                context_only=bool(edges) and all(
                    e["role"] in {"required_context", "supporting_heading"} for e in edges),
                publication_identity=identities[row["format"]],
                raw_section_is_independent_consumption_unit=False,
                authority="INSPECTION_ONLY",
            )
        self._sections = MappingProxyType({k: encode(v) for k, v in rows.items()})
        metadata = {}
        for u in units:
            consumer = json.loads(u.consumer_json)
            context = consumer["llm_context"]
            metadata[u.unit_id] = encode({
                **u.metadata(), "has_known_issues": bool(context.get("qa_observations")),
                "issues": [o for o in context.get("qa_observations", [])
                           if o.get("issue_id") != "PDF_PUBLICATION_EXPIRED"],
                "qualification": context["qualification"],
                "requires_context": bool(context["required_context"])
                or any(m.role in {"supporting_heading", "required_context"} for m in u.memberships),
            })
        self._unit_metadata = MappingProxyType(metadata)
        documents = {}
        for s in sources:
            source = s["source"]
            doc_id = source["doc_id"]
            doc_rows = [r for r in rows.values() if r["document_id"] == doc_id]
            counts = Counter(r["admission_status"] for r in doc_rows)
            doc_units = sorted(u.unit_id for u in units if u.document_id == doc_id)
            documents[doc_id] = encode({
                "document_id": doc_id, "format": doc_rows[0]["format"], "source": source,
                "snapshot": s["snapshot"], "counts": {"sections": len(doc_rows), **counts},
                "unit_ids": doc_units, "publication_identity": identities[doc_rows[0]["format"]],
                "selector_path": selections[doc_rows[0]["format"]],
            })
        if set(documents) != {r["document_id"] for r in rows.values()}:
            raise ValueError("unified_document_inventory_mismatch")
        self._documents = MappingProxyType(documents)
        counts = Counter(r["admission_status"] for r in rows.values())
        totals = {"documents": len(documents), "sections": len(rows), "units": len(units),
                  "admitted": counts["ADMITTED"], "excluded": counts["EXCLUDED"], "HOLD": counts["HOLD"]}
        if totals != expected_counts:
            raise ValueError("unified_frozen_counts_disagree")
        formats = {}
        for fmt in ("html", "markdown", "pdf"):
            rr = [r for r in rows.values() if r["format"] == fmt]
            cc = Counter(r["admission_status"] for r in rr)
            formats[fmt] = {"sections": len(rr), **{k: cc[k] for k in ("ADMITTED", "EXCLUDED", "HOLD")},
                            "units": sum(u.format == fmt for u in units)}
        self._summary = encode({**totals, "formats": formats,
                                "membership_edges": sum(len(e) for e in section_edges.values()),
                                "unique_sections_counted_once": True})
        self.catalog = Catalog(self)
        self.evidence = EvidenceGateway(self)
        self._check()

    def _find(self, unit_id):
        try:
            return self._units[unit_id]
        except (KeyError, TypeError):
            raise ValueError("unknown_forged_or_wrong_publication_unit") from None

    def _check(self):
        self._bound.check()

    def binding_manifest(self):
        self._check()
        return {"schema": "unified-loaded-snapshot-1.0", "authority": "INSPECTION_ONLY",
                "files": self._bound.fingerprints(), "catalog_sha256": sha(self.catalog.export())}


def load_verified_corpus(root, selection_set=None):
    """Full native validation once; reuse returned catalog/gateway for cheap lookups."""
    bound, freeze, selections = accepted_bindings(root, selection_set)
    index = bound.json(INDEX)
    pdf_issues = bound.json(PDF_ISSUES)
    rows, units = {}, []
    for adapter, fmt, metadata in [
        (html_adapter, "html", index), (markdown_adapter, "markdown", index),
        (pdf_adapter, "pdf", pdf_issues),
    ]:
        rr, uu = adapter(bound.root, selections[fmt], bound, metadata)
        if set(rows) & set(rr):
            raise ValueError("duplicate_cross_format_section_identity")
        rows.update(rr)
        units.extend(uu)
    bound.check()
    sources = json.loads(encode(freeze["frozen_source_identities"]))
    pdf_manifest = bound.json(selections["pdf"]["manifest_path"])
    for desc in pdf_manifest["publications"]:
        source = bound.json(desc["path"])["qa"]["pdf_text_support"]["source"]
        entry = next(s for s in sources if s["source"]["doc_id"] == source["doc_id"])
        if source["raw_sha256"] != entry["source"]["raw_sha256"]:
            raise ValueError("unified_document_source_identity_disagreement")
        entry["source"] = source
    corpus = VerifiedCorpus(bound, rows, units, sources, freeze["combined_counts"], SELECTORS)
    bound._json_cache.clear()
    return corpus


def load_verified_units(root, selection_set=None):
    """One-shot convenience; repeated access should reuse load_verified_corpus()."""
    return load_verified_corpus(root, selection_set).evidence.load_verified_units()


def get_verified_unit(root, unit_id, selection_set=None):
    """One-shot convenience; no Section/raw-text fallback."""
    return load_verified_corpus(root, selection_set).evidence.get_verified_unit(unit_id)
