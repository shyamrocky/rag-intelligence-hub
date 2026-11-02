"""Bounded M2 C01 pilot, not an index, admission path or M3 retrieval catalog."""

import copy
import re

from rag_hub.chunk_inputs import ChunkInput
from rag_hub.unified_models import encode, sha

VERSION = "m2-structure-aware-1.1"
ATOMIC = {"table", "mathematical_reference", "caption", "figure_caption", "code", "equation"}


def display_segments(source):
    """Map only hash-verified native source members into the approved display.

    No raw Section access, new normalization or guessed display/raw equivalence.
    """
    paragraphs = (source.native_source.get("structure") or {}).get("paragraphs", [])
    segments, position = [], 0
    for paragraph in paragraphs:
        if "source_member" not in paragraph:
            return []
        member = paragraph["source_member"]
        n = member["end"] - member["start"]
        text = source.text[position:position + n]
        if sha(text.encode()) != member["span_sha256"]:
            return []
        segments.append({"start": position, "end": position + n, "source_span": member})
        position += n
        if position < len(source.text):
            if source.text[position] != "\n":
                return []
            position += 1
    return segments if segments and position == len(source.text) else []


def bibliography_entries(source, segments):
    """Numbered entry markers must start exact native members in declared bibliography."""
    if source.content_type != "bibliography" or not segments:
        raise ValueError("unverified_bibliography_structure")
    matches = list(re.finditer(r"(?m)^\[(\d+)\]\s", source.text))
    starts = {s["start"] for s in segments}
    if (not matches or matches[0].start() != 0
            or [int(m[1]) for m in matches] != list(range(1, len(matches) + 1))
            or any(m.start() not in starts for m in matches)):
        raise ValueError("unverified_bibliography_reference_boundaries")
    return [{"start": m.start(), "end": matches[i + 1].start()
             if i + 1 < len(matches) else len(source.text), "reference_number": int(m[1])}
            for i, m in enumerate(matches)]


def heading_projection(record):
    """Only literal source-backed required headings, never arbitrary envelope fields."""
    values, seen = [], set()
    heading_ids = {m["section_id"] for m in record.memberships if m["role"] == "supporting_heading"}
    for context in record.required_context:
        role = context.get("role", "")
        is_heading = "heading" in role or context.get("section_id") in heading_ids
        if (context.get("kind") == "SOURCE_CONTENT" and is_heading
                and isinstance(context.get("text"), str)
                and (context.get("source_span") or context.get("section_id"))):
            key = encode(context)
            if key not in seen:
                seen.add(key)
                values.append(copy.deepcopy(context))
    return values


def mapped_lineage(record, source, segments, start, end):
    blocks = {bid: s["section_id"] for s in record.section_bindings
              for bid in s["provenance"].get("original_block_ids", [])}
    if not segments:
        return {"precision": "AUTHORIZED_DISPLAY_PROJECTION_WITH_PARENT_SOURCE_CITATIONS",
                "source_spans": copy.deepcopy(source.source_spans),
                "section_ids": source.section_ids,
                "section_scope": "parent source membership; finer allocation not claimed",
                "synthetic_joiners": [],
                "note": "Exact display offsets; partial raw offsets are not inferred."}
    spans, covered = [], set()
    for segment in segments:
        a, b = max(start, segment["start"]), min(end, segment["end"])
        if a >= b:
            continue
        original = segment["source_span"]
        text = source.text[a:b]
        spans.append({**original, "section_id": blocks[original["block_id"]],
                      "start": original["start"] + a - segment["start"],
                      "end": original["start"] + b - segment["start"],
                      "span_sha256": sha(text.encode()),
                      "parent_member_span_sha256": original["span_sha256"],
                      "display_start": a, "display_end": b})
        covered.update(range(a, b))
    joins = [p for p in range(start, end) if p not in covered]
    if any(source.text[p] != "\n" for p in joins):
        raise ValueError("unaccounted_non_source_display_characters")
    return {"precision": "HASH_VERIFIED_DISPLAY_TO_ORIGINAL_SOURCE_SLICES",
            "source_spans": spans, "section_ids": sorted({s["section_id"] for s in spans}),
            "section_scope": "exact intersecting source members",
            "synthetic_joiners": [{"display_start": p, "display_end": p + 1, "text": "\n",
                                   "origin": "existing_approved_unit_source_member_joiner"}
                                  for p in joins]}


class StructureAwarePilot:
    def __init__(self, preparation, tokenizer):
        self.preparation = preparation
        self.tokenizer = tokenizer

    def chunk(self, record, *, total_tokens):
        record = ChunkInput.model_validate(record)
        self.preparation.validate(record)
        result = self._chunk_verified(record, total_tokens=total_tokens)
        self.preparation.validate(record)
        return result

    def _chunk_verified(self, record, *, total_tokens):
        if (type(total_tokens) is not int or not 8 <= total_tokens <= self.tokenizer.max_length
                or record.document_id != "C01" or record.format != "pdf"):
            raise ValueError("unsupported_m2_pilot_scope_or_token_budget")
        heading_context = heading_projection(record)
        heading_text = "\n".join(h["text"] for h in heading_context)
        prefix = heading_text + "\n\n" if heading_text else ""
        prefix_tokens = self.tokenizer.count(prefix, special=False)
        body_budget = total_tokens - self.tokenizer.special_tokens - prefix_tokens
        config = {"version": VERSION, "total_tokens": total_tokens, "chunk_overlap": 0,
                  "tokenizer": self.tokenizer.metadata(),
                  "prefix_policy": "literal_required_source_headings_only",
                  "document_instruction": "", "special_tokens": self.tokenizer.special_tokens}
        chunks, unresolved, source_results = [], [], []

        def unresolved_region(source, start, end, reason, detail=None):
            unresolved.append({"source_pointer": source.source_pointer, "display_start": start,
                               "display_end": end, "source_text_sha256": sha(source.text[start:end].encode()),
                               "reason": reason, "detail": detail,
                               "source_spans": copy.deepcopy(source.source_spans),
                               "section_ids": source.section_ids})

        def emit(source, segments, start, end, decision, reference_numbers=None):
            text = source.text[start:end]
            embedding_text = prefix + text
            encoding = self.tokenizer.encode(embedding_text)
            if len(encoding.ids) > total_tokens:
                unresolved_region(source, start, end, "EXACT_TOKEN_BUDGET_EXCEEDED",
                                  {"actual_tokens": len(encoding.ids), "limit": total_tokens})
                return
            lineage = mapped_lineage(record, source, segments, start, end)
            unknowns = [{"embedding_start": a, "embedding_end": b}
                        for token, (a, b) in zip(encoding.ids, encoding.offsets, strict=True)
                        if token == 100]
            value = {
                "schema": "m2-chunk-proposal-1.0", "authority": "DERIVED_CANDIDATE_NOT_EVIDENCE",
                "unit_id": record.unit_id, "document_id": record.document_id,
                "preparation_record_id": record.record_id, "evidence_sha256": record.evidence_sha256,
                "source_pointer": source.source_pointer, "source_projection_sha256": sha(source.text.encode()),
                "display_start": start, "display_end": end, "source_text": text,
                "source_text_sha256": sha(text.encode()), "content_type": source.content_type,
                "embedding_text": embedding_text, "token_count": len(encoding.ids),
                "body_token_count": self.tokenizer.count(text, special=False),
                "heading_prefix": prefix, "heading_context": heading_context,
                "lineage": lineage, "boundary_decision": decision,
                "reference_numbers": reference_numbers or [],
                "reference_classification": record.reference_classification,
                "required_context": record.required_context, "qualification": record.qualification,
                "qa_observations": record.qa_observations,
                "memberships": record.memberships, "citation_locators": record.citation_locators,
                "publication_identity": record.publication_identity,
                "consumer_metadata": record.consumer_metadata,
                "consumer_rule": "Revalidate the complete original unit through the gateway; "
                                 "a pilot piece never independently authorizes source evidence.",
                "unknown_token_offsets": unknowns,
                "review_notes": (["Partial raw offsets not claimed; resolve via exact parent display."]
                                 if not segments else []) + (
                                     ["BGE emits UNK tokens; original source characters remain intact."]
                                     if unknowns else []),
            }
            value["proposal_id"] = "m2-piece:" + sha(encode({"config": config, "piece": value}))
            chunks.append(value)

        def split_prose(source, segments, start, end):
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=body_budget, chunk_overlap=0,
                length_function=lambda t: self.tokenizer.count(t, special=False),
                keep_separator="end", strip_whitespace=False,
                separators=[r"\n\n", r"(?<=[.!?])\s+", r"\s+"], is_separator_regex=True)
            pieces = splitter.split_text(source.text[start:end])
            if "".join(pieces) != source.text[start:end]:
                unresolved_region(source, start, end, "SPLITTER_NON_LOSSLESS_PARTITION")
                return
            offset = start
            for piece in pieces:
                emit(source, segments, offset, offset + len(piece),
                     "langchain_sentence_then_whitespace_budget_split")
                offset += len(piece)

        for source in record.indexable_source_content:
            segments = display_segments(source)
            entries = None
            n = len(source.text)
            initial_chunks, initial_unresolved = len(chunks), len(unresolved)
            if body_budget <= 0:
                unresolved_region(source, 0, n, "REQUIRED_HEADING_EXHAUSTS_TOKEN_BUDGET")
            elif source.content_type in ATOMIC:
                if self.tokenizer.count(prefix + source.text) <= total_tokens:
                    emit(source, segments, 0, n, "whole_typed_element_preserved")
                else:
                    unresolved_region(source, 0, n, "OVERSIZED_ATOMIC_ELEMENT_REQUIRES_REVIEW")
            else:
                if source.content_type == "bibliography":
                    try:
                        entries = bibliography_entries(source, segments)
                    except ValueError as error:
                        unresolved_region(source, 0, n, "UNVERIFIED_REFERENCE_BOUNDARIES", str(error))
                if source.content_type != "bibliography" or entries is not None:
                    if entries is not None:
                        atoms = entries
                    elif self.tokenizer.count(prefix + source.text) <= total_tokens:
                        atoms = [{"start": 0, "end": n}]
                    elif segments:
                        atoms = [{"start": s["start"], "end": segments[i + 1]["start"]
                                  if i + 1 < len(segments) else n}
                                 for i, s in enumerate(segments)]
                    else:
                        atoms = [{"start": 0, "end": n}]
                    pending = []

                    def flush(source=source, segments=segments, pending=pending, entries=entries):
                        if pending:
                            emit(source, segments, pending[0]["start"], pending[-1]["end"],
                                 "verified_reference_entry_boundaries" if entries is not None
                                 else "intact_or_native_source_member_boundary",
                                 [a["reference_number"] for a in pending] if entries is not None else [])
                            pending.clear()

                    for atom in atoms:
                        a, b = atom["start"], atom["end"]
                        if self.tokenizer.count(prefix + source.text[a:b]) > total_tokens:
                            if entries is not None:
                                flush()
                                unresolved_region(source, a, b, "OVERSIZED_REFERENCE_ENTRY",
                                                  {"reference_number": atom["reference_number"]})
                            else:
                                # Carry pending source context into prose splitting.
                                # Flushing it first could manufacture a heading-only
                                # candidate immediately before its oversized body.
                                split_start = pending[0]["start"] if pending else a
                                pending.clear()
                                split_prose(source, segments, split_start, b)
                        elif pending and self.tokenizer.count(
                            prefix + source.text[pending[0]["start"]:b]
                        ) > total_tokens:
                            if entries is None and len(pending) == 1 and pending[0]["start"] == 0:
                                # Do not isolate a leading source member merely
                                # because the next member fits only on its own.
                                # This preserves source continuity without guessing
                                # that the leading member is a typed heading.
                                split_start = pending[0]["start"]
                                pending.clear()
                                split_prose(source, segments, split_start, b)
                            else:
                                flush()
                                pending.append(atom)
                        else:
                            pending.append(atom)
                    flush()
            outcomes = [c for c in chunks[initial_chunks:]] + [
                u for u in unresolved[initial_unresolved:]]
            intervals = sorted((x["display_start"], x["display_end"]) for x in outcomes)
            position = 0
            for a, b in intervals:
                if a != position or b <= a:
                    raise ValueError("m2_unaccounted_or_duplicated_source_display")
                position = b
            if position != n:
                raise ValueError("m2_source_display_coverage_incomplete")
            source_results.append({"source_pointer": source.source_pointer,
                                   "content_type": source.content_type, "source_characters": n,
                                   "chunked_characters": sum(c["display_end"] - c["display_start"]
                                                             for c in chunks[initial_chunks:]),
                                   "unresolved_characters": sum(u["display_end"] - u["display_start"]
                                                                for u in unresolved[initial_unresolved:]),
                                   "reference_entries": len(entries) if source.content_type not in ATOMIC
                                   and entries is not None else None,
                                   "exact_display_coverage_accounted": True})
        # Restricted projections are never flattened into this PDF-only pilot.
        if record.protected_consumable_projections:
            raise ValueError("protected_native_projection_outside_m2_pdf_pilot")
        return {"schema": "m2-unit-chunking-result-1.0", "version": VERSION,
                "unit_id": record.unit_id, "preparation_record_id": record.record_id,
                "config": config, "heading_prefix_tokens": prefix_tokens,
                "effective_body_budget": body_budget, "chunks": chunks, "unresolved": unresolved,
                "source_results": source_results,
                "authority": "DERIVED_CANDIDATES_NOT_QA_OR_RETRIEVAL_AUTHORIZATION"}

    def validate(self, result):
        record = self.preparation.prepare(result["unit_id"])
        expected = self.chunk(record, total_tokens=result["config"]["total_tokens"])
        if encode(expected) != encode(result):
            raise ValueError("altered_or_stale_m2_chunking_result")
        return True
