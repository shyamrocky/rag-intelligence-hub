"""Bounded M3 partitions of already admitted source, never QA or authorization.

Only explicit native rows, numbered reference labels, and Python top-level
statements provide cuts. No blank-line, hanging-indent or missing-text inference.
"""

import ast
import re
from itertools import pairwise

from rag_hub.chunk_inputs import ChunkInput
from rag_hub.structure_chunking import display_segments, heading_projection, mapped_lineage
from rag_hub.unified_models import encode, sha

VERSION = "m3-bounded-remediation-1.0"
MEDIA_LIMIT = ("Only the source media description is recovered. "
               "No embedded video content or transcript was inspected.")


def table_atoms(source):
    native = source.native_source
    html = bool(native.get("table"))
    structure = native.get("table") if html else native.get("structure")
    if not structure or not structure.get("headers") or not structure.get("rows"):
        raise ValueError("missing_verified_table_structure")
    if html:
        if structure.get("association_basis") != "explicit source TR and TH/TD; no inferred or merged cells":
            raise ValueError("unqualified_HTML_row_associations")
        rows, separator = structure["rows"], " "
        if [c["text"] for c in rows[0]] != structure["headers"]:
            raise ValueError("table_header_disagreement")
        for row in rows:
            for cell in row:
                a, b = cell["raw_character_span"]
                if (not cell.get("dom_path") or not 0 <= a < b
                        or not re.fullmatch(r"[0-9a-f]{64}", cell["raw_fragment_sha256"])
                        or cell["tag"] not in {"th", "td"}):
                    raise ValueError("missing_HTML_cell_provenance")
    else:
        if (structure.get("association_evidence") != "exact native baselines and aligned column centers"
                or structure.get("merged_cells_supported") is not False):
            raise ValueError("unqualified_PDF_row_associations")
        rows, separator = [structure["headers"], *structure["rows"]], "\n"
        for row in rows:
            for cell in row:
                members = cell.get("members") or [cell.get("member")]
                position = 0
                for i, member in enumerate(members):
                    if not member:
                        raise ValueError("missing_PDF_cell_provenance")
                    size = member["end"] - member["start"]
                    text = cell["text"][position:position + size]
                    if size <= 0 or sha(text.encode()) != member["span_sha256"]:
                        raise ValueError("PDF_cell_span_disagreement")
                    position += size
                    if i + 1 < len(members):
                        if cell["text"][position:position + 1] != "\n":
                            raise ValueError("PDF_header_joiner_disagreement")
                        position += 1
                if position != len(cell["text"]):
                    raise ValueError("incomplete_PDF_cell_accounting")
    if len(rows) < 2 or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("non_rectangular_or_header_only_table")
    parts = [separator.join(cell["text"] for cell in row) for row in rows]
    serial = separator.join(parts)
    # PDF native tables may retain an original caption after the final row.
    # Preserve the whole suffix with that row; do not invent a new caption type.
    if not source.text.startswith(serial) or (html and serial != source.text):
        raise ValueError("table_display_serialization_disagreement")
    ranges, pos = [], 0
    for i, part in enumerate(parts):
        end = pos + len(part) + (len(separator) if i + 1 < len(parts) else 0)
        ranges.append({"start": pos, "end": end, "row_indices": [i]})
        pos = end
    ranges[-1]["end"] = len(source.text)
    header_end = ranges[0]["end"]
    # Never emit a detached table header. All later rows still require the
    # complete original parent, including its verified headers and associations.
    atoms = [{"start": 0, "end": ranges[1]["end"], "row_indices": [0, 1]}, *ranges[2:]]
    return atoms, {"method": "native_verified_table_rows", "structure_sha256": sha(encode(structure)),
                   "row_ranges_including_header": ranges, "required_header_range": [0, header_end],
                   "original_suffix_range": [len(serial), len(source.text)],
                   "context_rule": "complete original table/header/qualification required via parent"}


def numbered_reference_atoms(source):
    segments = display_segments(source)
    matches = list(re.finditer(r"(?m)^\[(\d+)\][ \t]", source.text))
    if (source.content_type != "bibliography" or not segments or not matches
            or matches[0].start() != 0
            or [int(m[1]) for m in matches] != list(range(1, len(matches) + 1))):
        raise ValueError("unverified_numbered_reference_labels")
    atoms = []
    for i, match in enumerate(matches):
        # A printed label can start within a hash-verified block. Requiring it
        # at the block start was the older chunker's unnecessarily narrow rule.
        segment = next((s for s in segments if s["start"] <= match.start()
                        and match.end() <= s["end"]), None)
        if segment is None:
            raise ValueError("reference_label_without_exact_source_witness")
        atoms.append({"start": match.start(), "end": matches[i + 1].start()
                      if i + 1 < len(matches) else len(source.text),
                      "reference_numbers": [int(match[1])],
                      "marker_source_block": segment["source_span"]["block_id"],
                      "marker_raw_start": segment["source_span"]["start"]
                                          + match.start() - segment["start"]})
    return atoms, {"method": "explicit_source_numbered_reference_labels", "entries": atoms}


def python_statement_atoms(source):
    lines = source.text.splitlines(keepends=True)
    if (len(lines) < 3 or not re.fullmatch(r"```python[ \t]*\r?\n", lines[0])
            or lines[-1].strip() != "```"):
        raise ValueError("unverified_complete_Python_fence")
    body = "".join(lines[1:-1])
    tree = ast.parse(body)  # Parse only. Never evaluate or execute publisher code.
    if not tree.body:
        raise ValueError("empty_Python_statement_map")
    offsets, pos = [], len(lines[0])
    for line in lines[1:-1]:
        offsets.append(pos)
        pos += len(line)
    nodes, starts = [], []
    for node in tree.body:
        first = min([node.lineno, *[d.lineno for d in getattr(node, "decorator_list", [])]])
        if node.col_offset != 0:
            raise ValueError("unexpected_non_top_level_statement")
        # Use whole line starts: AST columns are UTF-8 byte offsets, not Unicode
        # character offsets. Never use them as codepoint positions.
        starts.append(offsets[first - 1])
        nodes.append({"kind": type(node).__name__, "start_line": first,
                      "end_line": node.end_lineno})
    cuts = [0, *sorted(set(starts))[1:], len(source.text)]
    atoms = [{"start": a, "end": b} for a, b in pairwise(cuts)]
    return atoms, {"method": "CPython_AST_top_level_statement_boundaries_only",
                   "nodes": nodes, "allowed_top_level_cuts": cuts,
                   "runtime_certification": False,
                   "context_rule": "fragment not standalone executable code; complete parent required"}


class BoundedRemediator:
    def __init__(self, preparation, tokenizer):
        self.preparation, self.tokenizer = preparation, tokenizer

    def remediate(self, record, pointer, *, total_tokens=384):
        record = ChunkInput.model_validate(record)
        self.preparation.validate(record)
        source = next((s for s in record.indexable_source_content if s.source_pointer == pointer), None)
        if source is None:
            raise ValueError("protected_or_unbound_source_is_not_indexable")
        result = self._remediate_verified(record, source, total_tokens=total_tokens)
        self.preparation.validate(record)
        return result

    def _remediate_verified(self, record, source, *, total_tokens=384):
        if total_tokens != 384:
            raise ValueError("bounded_remediation_requires_384_total_tokens")
        q = record.qualification
        if not q.get("mandatory") or not q.get("complete_unit_only"):
            raise ValueError("missing_complete_parent_qualification")
        chunks, unresolved, context = [], [], []
        n = len(source.text)

        def block(a, b, reason):
            unresolved.append({"source_pointer": source.source_pointer, "display_start": a,
                "display_end": b, "source_text_sha256": sha(source.text[a:b].encode()),
                "reason": reason, "section_ids": source.section_ids,
                "source_spans": source.source_spans})

        evidence = {}
        try:
            if source.content_type == "heading":
                if len(record.indexable_source_content) < 2:
                    raise ValueError("heading_has_no_published_body_in_parent")
                context.append({"source_pointer": source.source_pointer, "display_start": 0,
                    "display_end": n, "source_text_sha256": sha(source.text.encode()),
                    "reason": "SOURCE_HEADING_RETAINED_IN_COMPLETE_PARENT_NOT_STANDALONE",
                    "section_ids": source.section_ids, "native_membership_roles_unchanged": True})
                atoms = []
                evidence = {"method": "native_heading_retained_as_parent_context_only"}
            elif source.content_type == "unknown":
                if MEDIA_LIMIT not in q.get("limitations", []):
                    raise ValueError("unknown_structure_without_explicit_media_description_scope")
                atoms = [{"start": 0, "end": n}]
                evidence = {"method": "whole_already_qualified_source_media_description",
                            "required_qualification": MEDIA_LIMIT, "video_inspected": False}
            elif source.content_type == "table":
                atoms, evidence = table_atoms(source)
            elif source.content_type == "bibliography":
                atoms, evidence = numbered_reference_atoms(source)
            elif source.content_type == "code_block":
                atoms, evidence = python_statement_atoms(source)
            else:
                raise ValueError("no_verified_specialized_boundary_map")
        except (ValueError, SyntaxError, KeyError, TypeError, IndexError) as exc:
            block(0, n, "OWNER_REVIEW_REQUIRED:" + str(exc).split("\n")[0])
            atoms = []
            evidence = {"method": "ABSTAIN", "reason": unresolved[0]["reason"]}
        headings = heading_projection(record)
        prefix = "\n".join(h["text"] for h in headings)
        prefix = prefix + "\n\n" if prefix else ""
        segments = display_segments(source)

        def emit(pending):
            a, b = pending[0]["start"], pending[-1]["end"]
            text = source.text[a:b]
            enc = self.tokenizer.encode(prefix + text)
            if len(enc.ids) > total_tokens:
                raise ValueError("packed_source_exceeds_exact_budget")
            unknown = [{"embedding_start": x, "embedding_end": y}
                       for t, (x, y) in zip(enc.ids, enc.offsets, strict=True) if t == 100]
            chunks.append({"unit_id": record.unit_id, "document_id": record.document_id,
                "source_pointer": source.source_pointer, "source_projection_sha256": sha(source.text.encode()),
                "display_start": a, "display_end": b, "source_text": text,
                "source_text_sha256": sha(text.encode()), "content_type": source.content_type,
                "lineage": mapped_lineage(record, source, segments, a, b),
                "reference_classification": record.reference_classification,
                "heading_context": headings, "token_count": len(enc.ids),
                "body_token_count": self.tokenizer.count(text, special=False),
                "boundary_decision": evidence["method"],
                "reference_numbers": [i for p in pending for i in p.get("reference_numbers", [])],
                "unknown_token_offsets": unknown,
                "review_notes": ["Complete original verified parent, context and qualifications required.",
                    "Structure witnesses: catalog-bound STRUCTURE_EVIDENCE.json by Unit ID/source pointer."]
                    + ([("Original table headers/cell associations required from the complete parent; "
                         "no reconstructed or independently usable subtable.")]
                       if source.content_type == "table" else [])
                    + (["Code fragment is not independently executable; no runtime verification."]
                       if source.content_type == "code_block" else [])
                    + (["Exact display offsets; finer raw offsets not claimed."] if not segments else [])
                    + (["Tokenizer UNK; original characters retained."] if unknown else [])})

        pending = []
        for atom in atoms:
            a, b = atom["start"], atom["end"]
            if self.tokenizer.count(prefix + source.text[a:b]) > total_tokens:
                if pending:
                    emit(pending)
                    pending = []
                block(a, b, "VERIFIED_ATOMIC_BOUNDARY_EXCEEDS_384_NO_INTERNAL_SPLIT")
            else:
                if pending and self.tokenizer.count(prefix + source.text[pending[0]["start"]:b]) > total_tokens:
                    emit(pending)
                    pending = []
                pending.append(atom)
        if pending:
            emit(pending)
        position = 0
        for item in sorted(chunks + unresolved + context, key=lambda r: r["display_start"]):
            if item["display_start"] != position or item["display_end"] <= position:
                raise ValueError("remediation_source_partition_missing_or_duplicated")
            position = item["display_end"]
        if position != n:
            raise ValueError("incomplete_remediation_source_accounting")
        return {"chunks": chunks, "unresolved": unresolved, "context_intervals": context,
                "evidence": {"unit_id": record.unit_id, "source_pointer": source.source_pointer,
                    "source_text_sha256": sha(source.text.encode()),
                    "native_source_sha256": sha(encode(source.native_source)), **evidence}}
