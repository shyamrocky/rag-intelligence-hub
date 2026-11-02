"""Phase1A evidence only: exact original PDF spans, never repair or approve content."""

from collections import defaultdict

from rag_hub.acquire import digest
from rag_hub.schemas import ParsedBlock

VERSION = "source-span-completeness-1.0"


def issue(code, unit, detail, *, block=None, start=None, end=None, text=None):
    evidence = {
        "unit_id": unit["id"],
        "block_id": block.block_id if block else None,
        "start": start,
        "end": end,
        "text": text,
        "locator": block.locator.model_dump(mode="json") if block else None,
        "block_content_sha256": block.content_sha256 if block else None,
        "raw_sha256": unit.get("raw_sha256"),
    }
    return {
        "issue_id": digest(f"{unit['id']}:{code}:{evidence}:{detail}".encode())[:24],
        "code": code,
        "severity": "error" if code != "unaccounted_span" else "warning",
        "dimension": "source_accounting",
        "detail": detail,
        "evidence": evidence,
        "artifact_refs": ["unit-results.json"],
    }


def validate_unit(unit, blocks):
    """Validate claimed text/identity before its spans can account for any source bytes."""
    problems, pieces, text = [], [], []
    members = unit.get("members", [])
    if not members:
        problems.append(issue("missing_members", unit, "No source spans supplied."))
    for member in members:
        block = blocks.get(member.get("block_id"))
        if block is None:
            problems.append(issue("missing_block", unit, "Original block ID does not resolve."))
            continue
        start, end = member.get("start"), member.get("end")
        if not (type(start) is int and type(end) is int and 0 <= start < end <= len(block.content)):
            problems.append(
                issue("invalid_offsets", unit, "Invalid Unicode interval.", block=block)
            )
            continue
        span = block.content[start:end]
        if (
            unit.get("doc_id") != block.doc_id
            or unit.get("raw_sha256") != block.raw_sha256
            or unit.get("snapshot_id") != block.snapshot_id
            or member.get("block_content_sha256") != block.content_sha256
            or member.get("span_sha256") != digest(span.encode())
            or member.get("locator") != block.locator.model_dump(mode="json")
            or member.get("offset_unit") != "Python Unicode code points; end exclusive"
        ):
            problems.append(
                issue(
                    "span_identity_mismatch",
                    unit,
                    "Hash, identity or locator mismatch.",
                    block=block,
                )
            )
        pieces.append((block.block_id, start, end))
        text.append(span)
    reconstructed = "\n".join(text)
    if unit.get("text") != reconstructed or unit.get("text_sha256") != digest(
        reconstructed.encode()
    ):
        problems.append(
            issue("parent_text_mismatch", unit, "Parent differs from exact source spans.")
        )
    return pieces if not problems else [], problems


def complement(length, intervals):
    """Exact union/complement; whitespace, punctuation and symbols are all characters."""
    cursor, gaps = 0, []
    for start, end in sorted(intervals):
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < length:
        gaps.append((cursor, length))
    return gaps


def assess(units: list[dict], blocks: dict[str, ParsedBlock]):
    """Peer spans may account for a legitimate block split; overlapping claims stay explicit.

    Only supplied/touched blocks are in the completeness universe. This cannot find
    entirely unreferenced blocks, source/PDF extraction errors or wrong paragraph order.
    No exclusions or dehyphenation dispositions are inferred in this checkpoint.
    """
    ids = [u["id"] for u in units]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate parent IDs")
    records, claims = {}, defaultdict(list)
    for unit in units:
        pieces, problems = validate_unit(unit, blocks)
        records[unit["id"]] = {
            "unit_id": unit["id"],
            "doc_id": unit["doc_id"],
            "issues": problems,
            "text_sha256": unit.get("text_sha256"),
            "members": unit.get("members", []),
            "guard_status": "fail" if problems else "pass",
            "scope": "exact completeness of referenced original blocks; not paragraph correctness",
        }
        for block_id, start, end in pieces:
            claims[block_id].append((start, end, unit["id"]))
    lookup = {u["id"]: u for u in units}
    ledger = []
    for block_id, spans in sorted(claims.items()):
        block = blocks[block_id]
        gaps = complement(len(block.content), [(s, e) for s, e, _ in spans])
        owners = sorted({owner for _, _, owner in spans})
        for start, end in gaps:
            for owner in owners:
                records[owner]["issues"].append(
                    issue(
                        "unaccounted_span",
                        lookup[owner],
                        "No exact owner span or reviewed disposition accounts for this interval.",
                        block=block,
                        start=start,
                        end=end,
                        text=block.content[start:end],
                    )
                )
                if records[owner]["guard_status"] != "fail":
                    records[owner]["guard_status"] = "unresolved"
        for i, (start, end, owner) in enumerate(spans):
            for other_start, other_end, other in spans[i + 1 :]:
                if max(start, other_start) < min(end, other_end):
                    for target in {owner, other}:
                        records[target]["issues"].append(
                            issue(
                                "overlapping_claims",
                                lookup[target],
                                f"Claims overlap between {owner} and {other}.",
                                block=block,
                                start=max(start, other_start),
                                end=min(end, other_end),
                            )
                        )
                        records[target]["guard_status"] = "fail"
        ledger.append(
            {
                "block_id": block_id,
                "doc_id": block.doc_id,
                "owners": owners,
                "source_characters": len(block.content),
                "accounted_characters": len(block.content) - sum(e - s for s, e in gaps),
                "unaccounted_intervals": [
                    {"start": s, "end": e, "text": block.content[s:e]} for s, e in gaps
                ],
                "block_content_sha256": block.content_sha256,
            }
        )
    return list(records.values()), ledger
