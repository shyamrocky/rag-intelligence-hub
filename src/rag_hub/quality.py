"""Explicit, hash-bound review receipts. No blanket sample-to-document approval."""

from rag_hub.acquire import digest
from rag_hub.schemas import ReviewReceipt, Section


def apply_reviews(sections: list[Section], receipts: list[ReviewReceipt]) -> list[Section]:
    lookup = {s.section_id: s for s in sections}
    if len({r.section_id for r in receipts}) != len(receipts):
        raise ValueError("duplicate review receipt")
    approvals = {}
    for r in receipts:
        s = lookup.get(r.section_id)
        if s is None or s.normalized_sha256 != r.normalized_sha256 or s.raw_sha256 != r.raw_sha256:
            raise ValueError("review does not match exact source/normalized section hashes")
        if s.block_type not in ("prose", "code", "heading") or any(
            issue not in ("pdf_layout_and_reading_order_unreviewed",) for issue in s.issues
        ):
            raise ValueError("unsafe content requires corrected extraction; cannot approve")
        values = s.model_dump() | {
            "verification_status": "verified_sample",
            "index_status": "approved_for_index",
            "review_receipt": digest(r.model_dump_json().encode()),
        }
        approvals[s.section_id] = Section.model_validate(values)
    return [approvals.get(s.section_id, s) for s in sections]
