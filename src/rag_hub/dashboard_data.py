"""Read-only dashboard queries over the accepted unified public contracts.

Supplementary canonical records supply only allowlisted INSPECTION_ONLY typing
metadata. They cannot provide source text, memberships or eligibility decisions.
"""

import json
from collections import Counter
from pathlib import Path
from threading import RLock
from time import perf_counter

from rag_hub.unified_bindings import BoundFiles
from rag_hub.unified_consumption import load_verified_corpus

UNRECORDED = "Not available in the frozen evidence."
ASSEMBLY_UNRECORDED = (
    "Verified membership established by the accepted QA publication; "
    "original assembly rationale not separately recorded."
)
ISSUE_FIELDS = {
    "issue_id", "issue_type", "description", "explanation", "severity", "origin", "kind",
    "mitigation", "confirmed_source_defect", "publisher_error_confirmed", "must_accompany",
    "remaining_unqualified_aspects", "disposition",
}


def issue_metadata(issues):
    # Native issue evidence can contain raw source trees/text. Never display it
    # as catalog metadata, including for HOLD/excluded Sections.
    return [{k: v for k, v in item.items() if k in ISSUE_FIELDS} for item in issues]


def locator_label(locators):
    parts = []
    for loc in locators:
        if loc.get("page") is not None:
            part = f"p. {loc['page']}"
        elif loc.get("line_start") is not None:
            part = f"lines {loc['line_start']}–{loc.get('line_end', loc['line_start'])}"
        else:
            part = loc.get("anchor") or loc.get("dom_path") or "Source reference"
        if part not in parts:
            parts.append(part)
    return "; ".join(parts) or UNRECORDED


def educational_example():
    return {
        "authority": "ILLUSTRATIVE_ONLY_NOT_CORPUS_EVIDENCE",
        "label": "Illustrative example — not actual corpus evidence or approval.",
        "sections": [
            {"section_id": "S01", "type": "Heading", "role": "supporting heading"},
            *[{"section_id": f"S0{i}", "type": "Paragraph", "role": "content"}
              for i in range(2, 5)],
        ],
        "unit_id": "U001",
    }


class DashboardData:
    """One shared immutable corpus, lock-serialized access, no detached evidence cache."""

    def __init__(self, root, corpus=None):
        self.root = Path(root).resolve()
        self._lock = RLock()
        start = perf_counter()
        self.corpus = corpus if corpus is not None else load_verified_corpus(self.root)
        # Public fingerprint manifest used ONCE, never full catalog export per render.
        files = self.corpus.binding_manifest()["files"]
        self.binding_fingerprints = files
        self._inspection = BoundFiles(self.root)
        self._types = {}
        self._parser = {}
        documents = self.corpus.catalog.list_documents()
        for document in documents:
            self._inspect_document(document, files)
        self.load_seconds = perf_counter() - start

    def _read_bound(self, path, files):
        if path not in files:
            return None
        return json.loads(self._inspection.bind(path, files[path]))

    def _inspect_document(self, doc, files):
        did, fmt = doc["document_id"], doc["format"]
        if fmt == "pdf":
            path = f"data/normalized/pdf/four-pdf-poc-v1/{did}/sections.json"
            component_path = f"data/parsed/pdf/four-pdf-poc-v1/{did}/component.json"
            component = self._read_bound(component_path, files)
            if component:
                self._parser[did] = {
                    "recorded_adapter": component["adapter_id"],
                    "adapter_version": component["version"],
                    "recorded_dependencies": component["dependencies"],
                    "provenance_ref": component_path,
                    "provenance_sha256": files[component_path],
                    "Docling": "Not recorded as selected text in this component record.",
                    "MinerU": "Not recorded as selected text in this component record.",
                    "comparison_scope": (
                        "Historical structural/model experiments do not establish that a model's "
                        "output was selected for a particular Section."
                    ),
                }
                blocks_path = f"data/parsed/pdf/four-pdf-poc-v1/{did}/blocks.json"
                blocks = self._read_bound(blocks_path, files)
                if blocks is not None:
                    self._parser[did]["observed_block_parser_versions"] = sorted({
                        b["parser_version"] for b in blocks if b.get("parser_version")})
                    self._parser[did]["block_provenance_ref"] = blocks_path
            records = self._read_bound(path, files)
            if records is None:
                return
            pairs = [(s, s.get("block_type")) for s in records]
        else:
            path = f"data/normalized/{fmt}/{did}.json"
            normalized = self._read_bound(path, files)
            if normalized is None:
                return
            pairs = [(r["section"], r.get("classification", r["section"].get("block_type")))
                     for r in normalized["records"]]
            self._parser[did] = {
                "recorded_adapter": UNRECORDED, "adapter_version": UNRECORDED,
                "normalization_version": normalized.get("normalization_version", UNRECORDED),
                "provenance_ref": path, "provenance_sha256": files[path],
                "comparison_scope": "Normalization evidence is not a parser execution record.",
            }
        for section, native_type in pairs:
            if (section["doc_id"] != did
                    or section["raw_sha256"] != doc["snapshot"]["sha256"]):
                raise ValueError("dashboard_inspection_source_identity_mismatch")
            self._types[section["section_id"]] = {
                "native_structural_type": native_type or UNRECORDED,
                "canonical_block_type": section.get("block_type", UNRECORDED),
                "metadata_ref": path,
            }
        # Neither text nor historical index_status is retained by the dashboard.

    def check(self):
        with self._lock:
            self.corpus.catalog.get_corpus_summary()  # public filesystem lease check
            self._inspection.check()

    def summary(self):
        with self._lock:
            self.check()
            return self.corpus.catalog.get_corpus_summary()

    def format_breakdown(self):
        """Display counts from the catalog; percentages refer to admitted Sections."""
        with self._lock:
            summary = self.summary()
            documents = self.corpus.catalog.list_documents()
            rows = []
            for fmt, label in [("html", "HTML"), ("markdown", "Markdown"), ("pdf", "PDF")]:
                counts = summary["formats"][fmt]
                classifications = {}
                for name in ["STANDARD", "ILLUSTRATIVE"]:
                    classifications[name] = self.corpus.catalog.list_sections(filters={
                        "format": fmt, "admission_status": "ADMITTED",
                        "reference_classification": f"{name}_REFERENCE",
                    }, limit=1)["total"]
                rows.append({
                    **counts, **classifications, "label": label,
                    "documents": sum(d["format"] == fmt for d in documents),
                    "admitted_percent": 100 * counts["ADMITTED"] / counts["sections"],
                })
            return rows

    def documents(self, *, fmt=None, query="", publisher=None, status=None):
        with self._lock:
            self.check()
            documents = self.corpus.catalog.list_documents()
            result = []
            for d in documents:
                source, count = d["source"], d["counts"]
                row = {
                    "Document": d["document_id"], "Title": source["title"],
                    "Publisher": source.get("publisher") or "Not recorded",
                    "Format": d["format"].upper(), "Sections": count["sections"],
                    "ADMITTED": count.get("ADMITTED", 0),
                    "EXCLUDED": count.get("EXCLUDED", 0), "HOLD": count.get("HOLD", 0),
                    "Units": len(d["unit_ids"]), "Source": source.get("canonical_url"),
                    "Frozen SHA-256": d["snapshot"]["sha256"],
                }
                if fmt and d["format"] != fmt:
                    continue
                if publisher and row["Publisher"] != publisher:
                    continue
                if status and not row[status]:
                    continue
                if query.casefold() not in " ".join(str(v) for v in row.values()).casefold():
                    continue
                result.append(row)
            return result

    def document(self, document_id):
        with self._lock:
            self.check()
            for d in self.corpus.catalog.list_documents():
                if d["document_id"] == document_id:
                    return d
            raise ValueError("Unknown document ID.")

    def sections(self, document_id, *, status=None, classification=None, query="",
                 offset=0, limit=25):
        if type(offset) is not int or offset < 0 or limit not in (10, 25, 50, 100):
            raise ValueError("Invalid dashboard pagination.")
        with self._lock:
            self.check()
            filters = {}
            if status:
                filters["admission_status"] = status
            if classification:
                filters["reference_classification"] = classification
            # Catalog pagination; never serialize/export the complete catalog.
            rows, cursor = [], 0
            while True:
                page = self.corpus.catalog.list_sections(
                    document_id, filters=filters, offset=cursor, limit=1000)
                for section in page["items"]:
                    row = self._section_table_row(section)
                    if query.casefold() in " ".join(str(v) for v in row.values()).casefold():
                        rows.append(row)
                if page["next_offset"] is None:
                    break
                cursor = page["next_offset"]
            return {"total": len(rows), "items": rows[offset:offset + limit]}

    def _section_table_row(self, s):
        return {
            "Section ID": s["section_id"],
            "Type": self._types.get(s["section_id"], {}).get("native_structural_type", UNRECORDED),
            "Status": s["admission_status"],
            "Classification": s["reference_classification"] or "—",
            "Issue / reason": s.get("reason") or "; ".join(s["issue_ids"]) or "—",
            "Linked units": len(s["unit_ids"]), "Context only": s["context_only"],
            "Scope limited": s["scope_limited_projection"],
            "Source locator": locator_label(s["citation_locators"]),
        }

    def section(self, section_id):
        with self._lock:
            self.check()
            s = self.corpus.catalog.get_section(section_id)
            # Drop nested issue evidence payloads, keeping typed observations only.
            s["issues"] = issue_metadata(s["issues"])
            s.update(self._types.get(section_id, {"native_structural_type": UNRECORDED}))
            qa = self.corpus.catalog.get_section_qa_details(section_id)
            s["unit_qualifications"] = qa["unit_qualifications"]
            for q in s["unit_qualifications"]:
                q["issues"] = issue_metadata(q["issues"])
            return s

    def document_profile(self, document_id):
        with self._lock:
            d = self.document(document_id)
            rows, cursor = [], 0
            while True:
                page = self.corpus.catalog.list_sections(document_id, offset=cursor, limit=1000)
                rows.extend(page["items"])
                if page["next_offset"] is None:
                    break
                cursor = page["next_offset"]
            return {
                "authority": "INSPECTION_ONLY", "document": d,
                "parser": self._parser.get(document_id, {"recorded_adapter": UNRECORDED}),
                "structural_types": dict(Counter(
                    self._types.get(s["section_id"], {}).get("native_structural_type", UNRECORDED)
                    for s in rows)),
                "classifications": dict(Counter(s["reference_classification"] or "Not applicable"
                                                 for s in rows)),
                "issue_categories": dict(Counter(i.get("issue_type", "Uncategorized")
                                                  for s in rows for i in s["issues"])),
                "locator_coverage": {
                    "with_source_locators": sum(bool(s["citation_locators"]) for s in rows),
                    "with_page": sum(any(l.get("page") is not None
                                         for l in s["citation_locators"]) for s in rows),
                    "with_bbox": sum(any(l.get("bbox") for l in s["citation_locators"])
                                     for s in rows),
                    "total_sections": len(rows),
                },
            }

    def hold_categories(self):
        with self._lock:
            self.check()
            rows = self.corpus.catalog.list_sections(
                filters={"admission_status": "HOLD"}, limit=1000)["items"]
            return dict(Counter(i["issue_type"] for s in rows for i in s["issues"]))

    def units(self, document_id=None):
        with self._lock:
            self.check()
            rows = self.corpus.catalog.list_units(document_id)
            for row in rows:
                row["issues"] = issue_metadata(row["issues"])
            return rows

    def relationships(self, unit_id):
        with self._lock:
            self.check()
            # Only this API defines actual membership. No heading/adjacency inference.
            edges = self.corpus.catalog.get_unit_sections(unit_id)
            result = []
            for edge in edges:
                section = self.section(edge["section_id"])
                result.append({
                    **edge, "native_structural_type": section["native_structural_type"],
                    "locator": locator_label(section["citation_locators"]),
                    "context_only_in_unit": edge["role"] in {"required_context", "supporting_heading"},
                    "context_only_in_all_units": section["context_only"],
                    "scope_limited_projection": section["scope_limited_projection"],
                    "admission_status": section["admission_status"],
                })
            return result

    def verified_unit(self, unit_id):
        with self._lock:
            self.check()
            value = self.corpus.evidence.get_verified_unit(unit_id)
            # Serialization validates the entire bundle again, including live expiry.
            return json.loads(self.corpus.evidence.serialize(value))

    def validate_unit(self, value):
        with self._lock:
            self.check()
            return self.corpus.evidence.validate(value)

    def assembly_evidence(self, verified_unit):
        """Recorded structure only, from an already authorized consumer bundle."""
        self.validate_unit(verified_unit)
        context = verified_unit["consumer"]["llm_context"]
        result = []
        for item in context["source_content"]:
            if item.get("structure"):
                result.append({"basis": "published source-content structure",
                               "recorded_structure": item["structure"]})
        for item in context["required_context"]:
            evidence = {k: item[k] for k in (
                "relationship_type", "role", "section_id", "unit_id", "source_span") if k in item}
            if evidence:
                result.append({"basis": "published required-context relationship", **evidence})
        return result or [{"basis": ASSEMBLY_UNRECORDED}]
