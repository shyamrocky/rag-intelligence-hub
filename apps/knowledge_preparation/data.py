"""Preparation inspection over existing native readers. Never builds derivatives."""

import json
from collections import Counter
from pathlib import Path

from rag_hub.dashboard_data import locator_label
from rag_hub.operational_selection import (
    DURABLE,
    EmbeddingMetadata,
    construct_catalog,
    construct_dashboard,
    resolve_selection,
)
from rag_hub.unified_bindings import BoundFiles
from rag_hub.unified_models import sha

# Exact accepted selectors, also recorded in trust v64 CRITICAL_BINDINGS.json.
INDEXES = {
    "Vector index": ("config/vector-index-m5-v1-1.json",
                     "3ee50fc59ee126f0473332a7ca7d40ed35fd4b88baf3254cfd3b19a19d52503b"),
    "BM25 index": ("config/keyword-index-m6-v1.json",
                   "d9d8125ee77b4c88c0480526de9ed8da7c0b90cde37d235cc0c5da0744d65df0"),
}


def verify_index(bound, label, chunks, embeddings):
    """Verify sealed export bindings, not database health or retrieval quality."""
    selector, expected = INDEXES[label]
    selection = json.loads(bound.bind(selector, expected))
    manifest = json.loads(bound.bind(selection["manifest_path"], selection["manifest_sha256"]))
    vector = label == "Vector index"
    schema = "m5-chroma-1.1" if vector else "m6-bm25-1.0"
    if manifest["schema"] != schema:
        raise ValueError("unsupported_index_manifest")
    spec = manifest["spec"]
    payload = json.loads(bound.bind(manifest["payload_path"], spec["payload_sha256"]))
    bindings = manifest["upstream_bindings"] if vector else spec["bindings"]
    if payload["bindings"] != bindings:
        raise ValueError("index_export_binding_mismatch")
    for path, digest in bindings.items():
        bound.bind(path, digest)
    for path, digest in spec["components"].items():
        bound.bind(path, digest)
    rows = payload["rows"]
    expected_count = manifest["records"] if vector else spec["records"]
    identifiers = [r["id"] if vector else r["chunk_id"] for r in rows]
    if len(rows) != expected_count or len(set(identifiers)) != len(rows):
        raise ValueError("index_export_duplicate_or_missing_rows")
    selected = {}
    document_ids = {row["document_id"] for row in chunks.values()}
    for row in rows:
        metadata = row["metadata"] if vector else row
        if metadata["document_id"] not in document_ids:
            continue
        cid = row["id"] if vector else row["chunk_id"]
        if cid not in chunks or cid not in embeddings:
            raise ValueError("index_export_unknown_pdf_chunk")
        embedding = embeddings[cid]
        if (metadata["document_id"] != chunks[cid]["document_id"]
                or metadata["unit_id"] != chunks[cid]["unit_id"]
                or metadata["input_text_sha256"] != embedding["input_text_sha256"]
                or metadata["qualification_sha256"] != embedding["qualification_sha256"]):
            raise ValueError("index_export_pdf_lineage_mismatch")
        if vector and any(metadata[k] != embedding[k] for k in
                          ["embedding_id", "vector_sha256", "row_index", "chunk_sha256"]):
            raise ValueError("index_export_embedding_mismatch")
        if not vector and sha(row["text"].encode()) != metadata["input_text_sha256"]:
            raise ValueError("keyword_export_text_mismatch")
        selected[cid] = {"chunk_id": cid, "unit_id": metadata["unit_id"],
                         "input_text_sha256": metadata["input_text_sha256"]}
    if set(selected) != set(chunks):
        raise ValueError("incomplete_pdf_index_export")
    return {"label": label, "selector": selector, "manifest_sha256": selection["manifest_sha256"],
            "records": selected, "status": "HASH_VERIFIED_SAVED_EXPORT",
            "collection": manifest.get("collection"), "schema": manifest["schema"]}


class PDFWalkthrough:
    """A shared native snapshot with live invalidation; evidence is opened on demand."""

    def __init__(self, root, *, formats=("pdf",)):
        # Keep the historical PDF-only default for callers; UI opts into the connected formats explicitly.
        if not formats or not set(formats) <= {"pdf", "markdown", "html"}:
            raise ValueError("unsupported_preparation_format")
        self.root = Path(root).resolve()
        self.selection = resolve_selection(self.root, DURABLE)
        self.data = construct_dashboard(self.root, self.selection)
        self.catalog = construct_catalog(self.root, self.data, self.selection)
        self.documents = sorted([d for d in self.data.corpus.catalog.list_documents()
                                 if d["format"] in formats], key=lambda d: d["document_id"])
        self.document_ids = {d["document_id"] for d in self.documents}
        if not self.documents:
            raise ValueError("no_verified_pdf_sources")
        self.units = [u for u in self.data.units() if u["document_id"] in self.document_ids]
        self.unit_ids = {u["unit_id"] for u in self.units}
        page = self.catalog.list_chunks(limit=1000)
        if page["total"] != len(page["items"]):
            raise ValueError("incomplete_pdf_chunk_inventory")
        self.chunks = {r["chunk_id"]: r for r in page["items"]
                       if r["document_id"] in self.document_ids}
        self.embedding_reader = EmbeddingMetadata(self.root, self.catalog)
        self.model = self.embedding_reader.export()
        self.bound = BoundFiles(self.root)
        self.profiles = {d["document_id"]: self.data.document_profile(d["document_id"])
                         for d in self.documents}
        self.parsed = {did: self._parsed_metadata(did) for did in self.document_ids}
        selected = json.loads(self.bound.bind(EmbeddingMetadata.SELECTOR, EmbeddingMetadata.SELECTOR_SHA))
        manifest = json.loads(self.bound.bind(selected["manifest_path"], EmbeddingMetadata.MANIFEST_SHA))
        records = self.bound.bind(manifest["records_path"], manifest["files"][manifest["records_path"]])
        self.embeddings = {r["chunk_id"]: r for line in records.splitlines()
                           if (r := json.loads(line))["document_id"] in self.document_ids}
        if set(self.embeddings) != set(self.chunks):
            raise ValueError("pdf_embedding_coverage_mismatch")
        self.indexes = {label: verify_index(self.bound, label, self.chunks, self.embeddings)
                        for label in INDEXES}
        self.check()

    def _parsed_metadata(self, document_id):
        """Bound parser metadata only; never expose raw or held block content."""
        document = next(d for d in self.documents if d["document_id"] == document_id)
        fmt = document["format"]
        markdown = fmt == "markdown"
        structured = fmt in {"markdown", "html"}
        path = (f"data/parsed/{fmt}/{document_id}.json" if structured
                else self.profiles[document_id]["parser"].get("block_provenance_ref"))
        if not path or path not in self.data.binding_fingerprints:
            return {"status": "UNAVAILABLE", "rows": [], "total": None, "types": {}}
        expected = self.data.binding_fingerprints[path]
        parsed = json.loads(self.bound.bind(path, expected))
        source_details = None
        if structured:
            if markdown:
                source_details = parsed["source"]
            else:
                source_path = f"data/parsed/html/{document_id}.source.json"
                source_sha = self.data.binding_fingerprints.get(source_path)
                if source_sha:
                    source_details = json.loads(self.bound.bind(source_path, source_sha))
                # HTML source_metadata is untrusted page meta tags, not acquisition metadata.
            if source_details is not None and (
                    source_details["doc_id"] != document_id
                    or source_details["raw_sha256"] != document["snapshot"]["sha256"]):
                raise ValueError(f"{fmt}_parser_source_mismatch")
            blocks = [r["block"] for r in parsed["records"]]
            versions = sorted({b["parser_version"] for b in blocks})
            self.profiles[document_id]["parser"] = {
                "recorded_adapter": "Markdown / bounded MDX parser" if markdown else "Non-executing semantic HTML adapter",
                "adapter_version": ", ".join(versions),
                "observed_block_parser_versions": versions,
                "provenance_ref": path, "provenance_sha256": expected,
                "block_provenance_ref": path,
                "comparison_scope": "Saved source/structure metadata only; no code or HTML execution.",
            }
        else:
            blocks = parsed
        if (len({b["block_id"] for b in blocks}) != len(blocks)
                or any(b["doc_id"] != document_id or b["raw_sha256"] != document["snapshot"]["sha256"]
                       for b in blocks)):
            raise ValueError("parsed_metadata_identity_mismatch")
        rows = [{"Block ID": b["block_id"], "Type": b["block_type"], "Sequence": b["sequence"],
                 "Source location": locator_label([b["locator"]])} for b in blocks]
        if markdown:
            for row, block in zip(rows, blocks):
                row.update({"Language": block.get("language") or "—",
                            "Provider / tab": block.get("provider_tab") or "—",
                            "Code group": block.get("code_group") or "—"})
        if fmt == "html":
            for row, record in zip(rows, parsed["records"]):
                row.update({"DOM path": record.get("dom_path") or "Not recorded",
                            "Classification": record.get("classification") or "Not recorded",
                            "Anchor": record["block"]["locator"].get("anchor") or "—"})
        result = {"status": "HASH_VERIFIED_METADATA", "rows": rows, "total": len(rows),
                  "types": dict(Counter(b["block_type"] for b in blocks)), "path": path, "sha256": expected}
        if source_details is not None:
            fields = ("doc_id", "title", "canonical_url", "original_url", "publisher", "raw_sha256",
                      "snapshot_id", "source_version", "source_format", "language", "byte_size",
                      "rights_status", "captured_at", "acquisition_basis")
            details = {k: source_details[k] for k in fields if k in source_details}
            if any(k in document["source"] and document["source"][k] != v for k, v in details.items()):
                raise ValueError(f"{fmt}_source_metadata_mismatch")
            result["source_metadata"] = details
        return result

    def check(self):
        self.selection.check()
        self.data.check()
        self.catalog.check()
        self.embedding_reader.check()
        self.bound.check()

    def unit(self, uid):
        self.check()
        if uid not in self.unit_ids:
            raise ValueError("unit_outside_pdf_scope")
        value = self.data.verified_unit(uid)
        self.data.validate_unit(value)
        if value["document_id"] not in self.document_ids:
            raise ValueError("unit_document_mismatch")
        return value

    def chunk(self, cid):
        self.check()
        if cid not in self.chunks:
            raise ValueError("chunk_outside_pdf_scope")
        value = self.catalog.open_chunk(cid)
        self.catalog.validate_view(value)
        if value["verified_parent"]["unit_id"] not in self.unit_ids:
            raise ValueError("chunk_parent_outside_pdf_scope")
        return value

    def for_document(self, document_id):
        self.check()
        if document_id not in self.document_ids:
            raise ValueError("document_outside_pdf_scope")
        return PDFDocument(self, document_id)

    def receipts(self, document_id):
        self.check()
        document = next(d for d in self.documents if d["document_id"] == document_id)
        return {"source_sha256": document["snapshot"]["sha256"],
                "chunk_selector": DURABLE, "chunk_manifest_sha256": self.selection.spec["manifest_sha"],
                "embedding_manifest_sha256": self.model["manifest_sha256"],
                "indexes": [{k: v for k, v in i.items() if k != "records"}
                            for i in self.indexes.values()]}


class PDFDocument:
    """Per-session document projection; never mutates a shared source selection."""

    def __init__(self, library, document_id):
        self.library = library
        self.root, self.data, self.catalog = library.root, library.data, library.catalog
        self.document = next(d for d in library.documents if d["document_id"] == document_id)
        self.units = [u for u in library.units if u["document_id"] == document_id]
        self.unit_ids = {u["unit_id"] for u in self.units}
        self.chunks = {cid: r for cid, r in library.chunks.items() if r["document_id"] == document_id}
        self.embeddings = {cid: library.embeddings[cid] for cid in self.chunks}
        self.model = library.model
        self.indexes = {label: index | {"records": {cid: index["records"][cid] for cid in self.chunks}}
                        for label, index in library.indexes.items()}

    @property
    def source_metadata(self):
        self.check()
        return self.parsed.get("source_metadata", self.document["source"])

    @property
    def profile(self):
        self.check()
        return self.library.profiles[self.document["document_id"]]

    @property
    def parsed(self):
        self.check()
        return self.library.parsed[self.document["document_id"]]

    def check(self):
        self.library.check()

    def unit(self, uid):
        if uid not in self.unit_ids:
            raise ValueError("unit_outside_selected_document")
        return self.library.unit(uid)

    def chunk(self, cid):
        if cid not in self.chunks:
            raise ValueError("chunk_outside_selected_document")
        return self.library.chunk(cid)

    def receipts(self):
        return self.library.receipts(self.document["document_id"])

    def related_items(self, *, block_id=None, section_id=None):
        """Inspection-only saved memberships. Never infer links from ID spelling."""
        self.check()
        if (block_id is None) == (section_id is None):
            raise ValueError("select_one_relationship_origin")
        did = self.document["document_id"]
        if block_id is not None and block_id not in {r["Block ID"] for r in self.parsed["rows"]}:
            raise ValueError("block_outside_selected_document")
        if section_id is not None and self.data.section(section_id)["document_id"] != did:
            raise ValueError("section_outside_selected_document")
        fmt = self.document["format"]
        structured = fmt in {"markdown", "html"}
        path = (f"data/normalized/{fmt}/{did}.json" if structured else
                f"data/normalized/pdf/four-pdf-poc-v1/{did}/sections.json")
        digest = self.data.binding_fingerprints.get(path)
        normalized = json.loads(self.library.bound.bind(path, digest)) if digest else None
        if structured and normalized is not None:
            if fmt == "markdown" and (normalized["source"]["doc_id"] != did
                    or normalized["source"]["raw_sha256"] != self.document["snapshot"]["sha256"]):
                raise ValueError("markdown_normalization_source_mismatch")
            records = [r["section"] for r in normalized["records"]]
        else:
            records = normalized or []
        if (len({r["section_id"] for r in records}) != len(records)
                or any(r["doc_id"] != did or r["raw_sha256"] != self.document["snapshot"]["sha256"]
                       for r in records)):
            raise ValueError("related_mapping_identity_mismatch")
        # Retain metadata only. Unverified/HOLD normalized text is never returned.
        mapping = {r["section_id"]: {"number": n, "blocks": r.get("block_ids", [])}
                   for n, r in enumerate(records, 1)}
        selected = [section_id] if section_id else [
            sid for sid, row in mapping.items() if block_id in row["blocks"]]
        rows = []
        for sid in selected:
            section = self.data.section(sid)
            if section["document_id"] != did:
                raise ValueError("related_section_document_mismatch")
            edges = self.catalog.get_section_chunks(sid)
            units = sorted(set(section["unit_ids"]))
            chunks = sorted({cid for edge in edges for cid in edge["chunk_ids"]})
            if any(uid not in self.unit_ids for uid in units) or any(cid not in self.chunks for cid in chunks):
                raise ValueError("related_membership_outside_selected_document")
            reason = section.get("reason") or "; ".join(section.get("issue_ids", []))
            if not units:
                explanation = f"No authorized evidence unit: {section['admission_status']}."
                explanation += f" Recorded reason: {reason}" if reason else " Detailed reason not recorded."
            elif not chunks:
                explanation = "Authorized parent exists; no saved retrieval chunks linked. Detailed reason unavailable."
            elif section["context_only"]:
                explanation = "Supporting heading/context only; chunks link through the complete parent."
            else:
                explanation = "Published parent membership; exact overlap with each chunk is not implied."
            rows.append({"section_id": sid, "section_number": mapping.get(sid, {}).get("number"),
                         "block_ids": mapping.get(sid, {}).get("blocks", []),
                         "status": section["admission_status"], "unit_ids": units, "chunk_ids": chunks,
                         "reason": explanation})
        self.check()
        message = ""
        if not rows:
            if digest:
                audit = normalized.get("audit", []) if structured else []
                reasons = [a.get("reason") or a.get("action") for a in audit if a.get("block_id") == block_id]
                message = "No downstream canonical Section is recorded for this block. "
                message += "; ".join(str(r) for r in reasons if r) or "Detailed reason not recorded."
            else:
                message = "Mapping unavailable: no saved block-to-Section link found."
        return {"mapping_status": "AVAILABLE" if digest else "UNAVAILABLE", "rows": rows,
                "message": message}
