"""M1 preparation through the accepted gateway, without splitting or QA decisions.

Use ChunkPreparation.validate before downstream use. Loading JSON or constructing a
Pydantic object does not establish authority. Native complete-unit obligations remain.
"""

import argparse
import json
from pathlib import Path

from rag_hub.chunk_inputs import ChunkInput, SourceContent
from rag_hub.unified_models import encode, sha


def source_sections(item, bindings, memberships):
    """Resolve only explicit Section IDs/block citations, never adjacency or text."""
    allowed = {m["section_id"] for m in memberships if m["role"] in {"content", "projection"}}
    found = set()
    if item.get("section_id"):
        found.add(item["section_id"])
    for c in item.get("citations", []):
        if c.get("block_id"):
            matched = [s["section_id"] for s in bindings
                       if c["block_id"] in s["provenance"].get("original_block_ids", [])]
            if len(matched) != 1:
                raise ValueError("unresolved_preparation_source_span")
            found.update(matched)
    if not found or not found <= allowed:
        raise ValueError("context_or_unbound_source_cannot_be_indexable")
    return sorted(found)


class ChunkPreparation:
    """A live verified gateway is the only authority behind preparation validation."""

    def __init__(self, corpus):
        self.corpus = corpus
        self._section_metadata = {}

    def _section_rows(self, document_id):
        # Metadata-only cache tied to the original live gateway's integrity lease.
        # Evidence is always fetched/validated anew; no detached authorizations.
        if document_id not in self._section_metadata:
            rows, offset = {}, 0
            while True:
                page = self.corpus.catalog.list_sections(document_id, offset=offset, limit=1000)
                rows.update((r["section_id"], r) for r in page["items"])
                if page["next_offset"] is None:
                    break
                offset = page["next_offset"]
            self._section_metadata[document_id] = rows
        return self._section_metadata[document_id]

    def prepare(self, unit_id):
        value = self.corpus.evidence.get_verified_unit(unit_id)
        self.corpus.evidence.validate(value)
        memberships = self.corpus.catalog.get_unit_sections(unit_id)
        if memberships != value["memberships"] or value["admission_status"] != "ADMITTED":
            raise ValueError("preparation_membership_disagreement")
        rows = self._section_rows(value["document_id"])
        bindings = []
        for sid in sorted({m["section_id"] for m in memberships}):
            row = rows[sid]
            if row["admission_status"] != "ADMITTED" or row["document_id"] != value["document_id"]:
                raise ValueError("unauthorized_preparation_section")
            bindings.append({k: row[k] for k in (
                "section_id", "document_id", "format", "provenance", "citation_locators",
                "context_only", "scope_limited_projection", "reference_classification")})
        consumer = value["consumer"]
        context = consumer["llm_context"]
        if (not context["qualification"].get("mandatory")
                or not context["qualification"].get("complete_unit_only")):
            raise ValueError("missing_preparation_qualification")
        content, protected, limits = [], [], []
        for i, item in enumerate(context["source_content"]):
            if item.get("kind") != "SOURCE_CONTENT":
                raise ValueError("non_source_in_source_content")
            pointer = f"/consumer/llm_context/source_content/{i}"
            if "restricted_projection" in item:
                # This native consumable rendering intentionally includes warnings.
                # Do not try to strip those warnings or index its alternate segments.
                protected.append({"source_pointer": pointer, "native_source": item})
                limits.append("Native warning-bearing projection retained intact; no independent "
                              "indexable source field is exposed by M0/M1 for this item.")
                continue
            if not isinstance(item.get("text"), str) or not item["text"].strip():
                raise ValueError("missing_explicit_authorized_source_text")
            citations = item.get("citations", [])
            if not citations:
                raise ValueError("missing_preparation_source_citation")
            for c in citations:
                if ("start" in c or "end" in c) and (
                    type(c.get("start")) is not int or type(c.get("end")) is not int
                    or not 0 <= c["start"] < c["end"]
                ):
                    raise ValueError("invalid_preparation_span")
            content.append(SourceContent(
                source_pointer=pointer, content_type=item.get("content_type", "not_recorded"),
                text=item["text"], section_ids=source_sections(item, bindings, memberships),
                source_spans=citations, native_source=item,
            ))
        payload = {
            "unit_id": unit_id, "document_id": value["document_id"], "format": value["format"],
            "reference_classification": value["reference_classification"],
            "indexable_source_content": [c.model_dump(mode="json") for c in content],
            "required_context": context["required_context"],
            "qa_observations": context["qa_observations"], "qualification": context["qualification"],
            "protected_consumable_projections": protected, "preparation_limits": limits,
            "memberships": memberships, "section_bindings": bindings,
            "citation_locators": value["citation_locators"],
            "publication_identity": value["publication_identity"],
            "consumer_metadata": {k: v for k, v in consumer.items() if k != "llm_context"},
            "evidence_sha256": sha(encode(value)),
        }
        record = ChunkInput(record_id="prepared:" + sha(encode(payload)), **payload)
        # Recheck after building the record, including clock-dependent warnings.
        self.corpus.evidence.validate(value)
        return record

    def validate(self, record):
        candidate = ChunkInput.model_validate(record)
        expected = self.prepare(candidate.unit_id)
        if encode(candidate.model_dump(mode="json")) != encode(expected.model_dump(mode="json")):
            raise ValueError("altered_stale_or_scope_expanded_chunk_input")
        return True

    def serialize(self, record):
        self.validate(record)
        return encode(record.model_dump(mode="json"))

    def prepare_document(self, document_id):
        return [self.prepare(u["unit_id"])
                for u in self.corpus.catalog.list_units(document_id=document_id)]


def write_once(path, raw):
    """Versioned outputs cannot silently overwrite earlier preparation evidence."""
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"preparation_output_already_exists: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--document", default="C01")
    args = parser.parse_args()
    from rag_hub.unified_consumption import load_verified_corpus

    preparation = ChunkPreparation(load_verified_corpus(args.root))
    records = preparation.prepare_document(args.document)
    raw = b"".join(preparation.serialize(r) + b"\n" for r in records)
    write_once(args.output, raw)
    print(json.dumps({"document": args.document, "units": len(records),
                      "sha256": sha(raw), "authority": "DERIVED_PREPARATION_NOT_AUTHORIZATION"}))


if __name__ == "__main__":
    main()
