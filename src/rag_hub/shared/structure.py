"""Generic declared-parent conformance, not paragraph inference or chunking."""

from rag_hub.acquire import digest

from .evidence import GUARD


class ConformanceError(ValueError):
    def __init__(self, code, evidence):
        super().__init__(code)
        self.evidence = evidence


def span(block, start=0, end=None):
    end = len(block.content) if end is None else end
    return {
        "block_id": block.block_id,
        "start": start,
        "end": end,
        "block_content_sha256": block.content_sha256,
        "span_sha256": digest(block.content[start:end].encode()),
        "locator": block.locator.model_dump(mode="json"),
        "offset_unit": "Python Unicode code points; end exclusive",
    }


def parent(ident, kind, members, source, blocks, heading=None):
    text = "\n".join(blocks[m["block_id"]].content[m["start"] : m["end"]] for m in members)
    return {
        "id": ident,
        "kind": kind,
        "members": members,
        "doc_id": source.doc_id,
        "raw_sha256": source.raw_sha256,
        "snapshot_id": source.snapshot_id,
        "heading_block_id": heading,
        "text": text,
        "text_sha256": digest(text.encode()),
        "canonical_joiner": "one synthetic newline between exact original member spans",
        "experimental_eligibility": "HOLD",
    }


def atomic_parents(source, blocks, options):
    lookup = {b.block_id: b for b in blocks}
    return [
        parent(
            "parent:" + b.block_id,
            "section_parent" if b.block_type == "heading" else "paragraph",
            [span(b)],
            source,
            lookup,
        )
        for b in blocks
    ]


def assess(parents, blocks, audit):
    lookup = {b.block_id: b for b in blocks}
    guards, ledger = GUARD.assess(parents, lookup)
    bad = [g for g in guards if g["guard_status"] != "pass"]
    if bad:
        raise ConformanceError(
            "invalid_parent_spans_or_completeness", {"guards": guards, "source_accounting": ledger}
        )
    represented = {r["block_id"] for r in ledger}
    excluded = {
        r["block_id"]
        for r in audit
        if r.get("after") is None and r.get("before_sha256") == lookup[r["block_id"]].content_sha256
    }
    if set(lookup) - represented - excluded:
        raise ConformanceError(
            "unreferenced_source_blocks",
            {"block_ids": sorted(set(lookup) - represented - excluded)},
        )
    ids = {p["id"]: p for p in parents}
    if len(ids) != len(parents):
        raise ValueError("duplicate_parent_ids")
    first_positions = [
        min((lookup[m["block_id"]].sequence, m["start"]) for m in p["members"]) for p in parents
    ]
    if first_positions != sorted(first_positions):
        raise ValueError("invalid_parent_reading_order")
    flattened = [
        (lookup[m["block_id"]].sequence, m["start"]) for p in parents for m in p["members"]
    ]
    if flattened != sorted(flattened):
        raise ValueError("crossing_parent_reading_order")
    references = []
    for p in parents:
        order = [(lookup[m["block_id"]].sequence, m["start"]) for m in p["members"]]
        if order != sorted(order):
            raise ValueError("invalid_source_reading_order")
        heading = p.get("heading_block_id")
        if heading:
            targets = [
                u
                for u in parents
                if u["kind"] == "section_parent"
                and any(m["block_id"] == heading for m in u["members"])
            ]
            if (
                heading not in lookup
                or lookup[heading].block_type != "heading"
                or len(targets) != 1
                or p["id"] == targets[0]["id"]
            ):
                raise ValueError("unresolved_heading_reference")
            if lookup[heading].sequence >= min(
                lookup[m["block_id"]].sequence for m in p["members"]
            ):
                raise ValueError("heading_follows_child")
            references.append(
                {
                    "type": "section_membership",
                    "from": p["id"],
                    "to": targets[0]["id"],
                    "source_sha256": p["raw_sha256"],
                    "snapshot_id": p["snapshot_id"],
                }
            )
    return {
        "guards": guards,
        "source_accounting": ledger,
        "source_blocks": len(blocks),
        "represented_blocks": len(represented),
        "audited_exclusions": sorted(excluded - represented),
        "relationships": references,
    }
