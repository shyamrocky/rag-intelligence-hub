"""Read-only M1 profiling, with unit totals distinct from unique source coverage.

Lexical tokens are diagnostics, not embedding-model tokens. No splitting occurs.
"""

import hashlib
import math
import re
from collections import Counter, defaultdict

TOKEN_PATTERN = r"[^\W_]+(?:['’][^\W_]+)*|[^\w\s]"
TOKEN_METHOD = "unicode-lexical-1.0"


def tokens(text):
    return len(re.findall(TOKEN_PATTERN, text, flags=re.UNICODE))


def distribution(values):
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {"n": len(values), "min": ordered[0], "max": ordered[-1],
            "mean": round(sum(values) / len(values), 2),
            **{f"p{p}": ordered[max(0, math.ceil(p / 100 * len(values)) - 1)]
               for p in [25, 50, 75, 90, 95]},
            "total": sum(values)}


def span_key(span):
    if not span.get("block_id") or type(span.get("start")) is not int:
        return None
    return (span["block_id"], span["start"], span["end"])


def context_spans(value):
    if isinstance(value, dict):
        if span_key(value):
            yield value
        else:
            for child in value.values():
                yield from context_spans(child)
    elif isinstance(value, list):
        for child in value:
            yield from context_spans(child)


def text_witnesses(source):
    """Only directly bound display or hash-verified source slices; no raw access."""
    item = source.native_source
    citations = source.source_spans
    structure = item.get("structure") or {}
    paragraphs = structure.get("paragraphs", [])
    if paragraphs:
        members = [p["source_member"] for p in paragraphs if "source_member" in p]
        offset, found = 0, []
        for member in members:
            size = member["end"] - member["start"]
            text = source.text[offset:offset + size]
            if hashlib.sha256(text.encode()).hexdigest() != member.get("span_sha256"):
                return []  # No invented per-Section token attribution from mixed display.
            found.append((member, text))
            offset += size
            if offset < len(source.text):
                if source.text[offset] != "\n":
                    return []
                offset += 1
        if offset == len(source.text):
            return found
        return []
    if source.content_type == "table":
        found = []
        for cell in structure.get("headers", []) + [
            cell for row in structure.get("rows", []) for cell in row
        ]:
            member, text = cell.get("member", {}), cell.get("text", "")
            if span_key(member) and hashlib.sha256(text.encode()).hexdigest() == member.get(
                "span_sha256"
            ):
                found.append((member, text))
        return found
    # A single citation binds one authorized display field to one source interval.
    # Math transcriptions and multi-span mixed views intentionally don't qualify.
    if len(citations) == 1 and len(source.text) == citations[0]["end"] - citations[0]["start"]:
        return [(citations[0], source.text)]
    return []


def profile(records):
    """Profile already prepared records; output is inspection-only, never admission."""
    sections, block_sections = {}, {}
    for record in records:
        for row in record.section_bindings:
            sid = row["section_id"]
            sections.setdefault(sid, {"section_id": sid, "unit_ids": set(), "roles": set(),
                                     "content_types": set(), "body": set(), "context": set()})
            for bid in row["provenance"].get("original_block_ids", []):
                if bid in block_sections and block_sections[bid] != sid:
                    raise ValueError("ambiguous_profile_block_section")
                block_sections[bid] = sid
    unit_rows, body_occurrences, context_occurrences = [], [], []
    witnesses = defaultdict(dict)
    for r in records:
        for edge in r.memberships:
            s = sections[edge["section_id"]]
            s["unit_ids"].add(r.unit_id)
            s["roles"].add(edge["role"])
        for role, spans in [
            ("body", [span for x in r.indexable_source_content for span in x.source_spans]),
            ("context", list(context_spans(r.required_context))),
        ]:
            for span in spans:
                key = span_key(span)
                if key:
                    sid = block_sections.get(key[0])
                    if not sid:
                        raise ValueError("profile_span_without_canonical_section")
                    sections[sid][role].update((key[0], p) for p in range(key[1], key[2]))
                    (body_occurrences if role == "body" else context_occurrences).append(key)
        for source in r.indexable_source_content:
            for sid in source.section_ids:
                sections[sid]["content_types"].add(source.content_type)
            for span, text in text_witnesses(source):
                sid = block_sections[span["block_id"]]
                for pos, char in enumerate(text, span["start"]):
                    key = (span["block_id"], pos)
                    previous = witnesses[sid].get(key)
                    if previous is not None and previous != char:
                        raise ValueError("conflicting_authorized_profile_witnesses")
                    witnesses[sid][key] = char
        n = sum(tokens(x.text) for x in r.indexable_source_content)
        types = [x.content_type for x in r.indexable_source_content]
        special = sorted({t for t in types if t in {"table", "mathematical_reference", "code"}})
        unit_rows.append({
            "unit_id": r.unit_id, "record_id": r.record_id, "content_types": types,
            "classification": r.reference_classification,
            "source_tokens": n,
            "source_characters": sum(len(x.text) for x in r.indexable_source_content),
            "explicit_context_text_tokens": sum(tokens(x["text"]) for x in r.required_context
                                                if isinstance(x.get("text"), str)),
            "context_entries": len(r.required_context),
            "context_entries_without_top_level_text": sum("text" not in x for x in r.required_context),
            "unique_section_count": len({m["section_id"] for m in r.memberships}),
            "membership_edges": len(r.memberships),
            "scope_limited": any(s["scope_limited_projection"] for s in r.section_bindings),
            "qa_observation_count": len(r.qa_observations),
            "mandatory_qualification": r.qualification,
            "source_token_size_screen": {str(budget): "within_proxy_budget" if n <= budget
                                         else "over_proxy_budget"
                                         for budget in [256, 384]},
            "handling": ("preserve typed structure; atomic or validated native boundaries only"
                         if special else "intact candidate" if n <= 256
                         else "inspect existing source boundaries for a future split"),
            "special_content": special,
        })
    section_rows = []
    for sid, s in sorted(sections.items()):
        # Reassemble only the union of witnessed codepoints, without counting an
        # overlap twice or joining non-contiguous blocks into invented source text.
        fragments, current, previous = [], [], None
        for key, char in sorted(witnesses[sid].items()):
            if previous and (key[0] != previous[0] or key[1] != previous[1] + 1):
                fragments.append("".join(current))
                current = []
            current.append(char)
            previous = key
        if current:
            fragments.append("".join(current))
        section_rows.append({
            "section_id": sid, "unit_ids": sorted(s["unit_ids"]),
            "unit_count": len(s["unit_ids"]), "roles": sorted(s["roles"]),
            "context_only": s["roles"] <= {"required_context", "supporting_heading"},
            "content_types": sorted(s["content_types"]),
            "unique_authorized_body_span_codepoints": len(s["body"]),
            "unique_context_span_codepoints": len(s["context"]),
            "unique_body_context_union_codepoints": len(s["body"] | s["context"]),
            "source_text_witness_codepoints": len(witnesses[sid]),
            "source_text_witness_tokens": sum(tokens(x) for x in fragments) if fragments else None,
            "witness_covers_all_body_spans": set(witnesses[sid]) == s["body"] if s["body"] else False,
            "note": "Tokens describe only gateway-backed witnessed intervals; null is not zero. "
                    "No unrestricted canonical Section text was read.",
        })
    return {
        "schema": "chunk-preparation-profile-1.0", "authority": "INSPECTION_ONLY",
        "token_method": {"id": TOKEN_METHOD, "pattern": TOKEN_PATTERN,
                         "model_tokens": False, "embedding_limit_validated": False,
                         "note": "Exact lexical counts under this regex; not BGE WordPiece counts."},
        "units": unit_rows, "sections": section_rows,
        "unit_statistics": {
            "units": len(records),
            "content_types": dict(Counter(t for u in unit_rows for t in u["content_types"])),
            "source_tokens": distribution([u["source_tokens"] for u in unit_rows]),
            "explicit_context_text_tokens": distribution([
                u["explicit_context_text_tokens"] for u in unit_rows]),
            "proxy_size_screen": {str(b): {
                "within": sum(u["source_tokens"] <= b for u in unit_rows),
                "over": sum(u["source_tokens"] > b for u in unit_rows)} for b in [256, 384]},
            "scope_limited_units": sum(u["scope_limited"] for u in unit_rows),
        },
        "unique_section_statistics": {
            "sections": len(section_rows),
            "context_only": sum(s["context_only"] for s in section_rows),
            "shared_by_multiple_units": sum(s["unit_count"] > 1 for s in section_rows),
            "membership_edges": sum(len(r.memberships) for r in records),
            "unique_unit_section_pairs": sum(s["unit_count"] for s in section_rows),
            "unique_body_span_codepoints": sum(len(s["body"]) for s in sections.values()),
            "unique_context_span_codepoints": sum(len(s["context"]) for s in sections.values()),
            "unique_body_context_union_codepoints": sum(
                len(s["body"] | s["context"]) for s in sections.values()),
            "body_span_codepoints_with_repetition": sum(e - b for _, b, e in body_occurrences),
            "context_span_codepoints_with_repetition": sum(e - b for _, b, e in context_occurrences),
            "unique_context_spans": len(set(context_occurrences)),
            "context_span_occurrences": len(context_occurrences),
            "sections_with_source_token_witnesses": sum(
                s["source_text_witness_tokens"] is not None for s in section_rows),
            "sections_with_complete_body_witnesses": sum(
                s["witness_covers_all_body_spans"] for s in section_rows),
            "source_token_witness_distribution": distribution([
                s["source_text_witness_tokens"] for s in section_rows
                if s["source_text_witness_tokens"] is not None]),
        },
    }
