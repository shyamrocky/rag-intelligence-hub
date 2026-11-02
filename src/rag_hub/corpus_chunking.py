"""Necessary M3 format extensions over M2 helpers; upstream contracts stay unchanged."""

from rag_hub.chunk_inputs import ChunkInput
from rag_hub.structure_chunking import (
    ATOMIC,
    StructureAwarePilot,
    bibliography_entries,
    display_segments,
    heading_projection,
    mapped_lineage,
)
from rag_hub.unified_models import sha

VERSION = "m3-corpus-partition-1.0"
PROSE = {"prose", "paragraph", "section", "section_body", "text", "list", "list_item",
         "definition", "document_citation", "bibliography", "section_text", "prose_projection",
         "historical_reviewed_paragraph", "residual_context_bound", "residual_inline_notation_prose",
         "residual_prose", "residual_prose_projection"}
SPECIALIZED = ATOMIC | {"code_block", "math", "formula", "table_projection", "printed_code",
                       "code_example", "figure", "ordered_list", "unordered_list"}


class CorpusChunker:
    """C01 delegates unchanged to M2; other formats use exact authorized source fields.

    Specialized elements are atomic. A source pointer with a warning-bearing native
    projection has no independent indexable field under the accepted M0 contract.
    """

    def __init__(self, preparation, tokenizer):
        self.preparation, self.tokenizer = preparation, tokenizer
        self.pilot = StructureAwarePilot(preparation, tokenizer)

    def chunk(self, record, *, total_tokens):
        record = ChunkInput.model_validate(record)
        if record.document_id == "C01":
            return self.pilot.chunk(record, total_tokens=total_tokens)
        self.preparation.validate(record)
        result = self._partition_verified(record, total_tokens=total_tokens)
        self.preparation.validate(record)
        return result

    def _partition_verified(self, record, *, total_tokens):
        if type(total_tokens) is not int or not 8 <= total_tokens <= self.tokenizer.max_length:
            raise ValueError("invalid_m3_token_budget")
        headings = heading_projection(record)
        heading = "\n".join(h["text"] for h in headings)
        prefix = heading + "\n\n" if heading else ""
        chunks, unresolved, coverage = [], [], []

        def blocked(source, a, b, reason):
            unresolved.append({"source_pointer": source.source_pointer,
                               "display_start": a, "display_end": b,
                               "source_text_sha256": sha(source.text[a:b].encode()),
                               "reason": reason, "source_spans": source.source_spans,
                               "section_ids": source.section_ids})

        def emit(source, segments, a, b, boundary, references=None):
            text = source.text[a:b]
            encoded = self.tokenizer.encode(prefix + text)
            if len(encoded.ids) > total_tokens:
                blocked(source, a, b, "EXACT_TOKEN_BUDGET_EXCEEDED_NO_TRUNCATION")
                return
            unknown = [{"embedding_start": x, "embedding_end": y}
                       for token, (x, y) in zip(encoded.ids, encoded.offsets, strict=True)
                       if token == 100]
            chunks.append({
                "unit_id": record.unit_id, "document_id": record.document_id,
                "source_pointer": source.source_pointer,
                "source_projection_sha256": sha(source.text.encode()),
                "display_start": a, "display_end": b, "source_text_sha256": sha(text.encode()),
                "source_text": text, "content_type": source.content_type,
                "lineage": mapped_lineage(record, source, segments, a, b),
                "reference_classification": record.reference_classification,
                "heading_context": headings, "token_count": len(encoded.ids),
                "body_token_count": self.tokenizer.count(text, special=False),
                "boundary_decision": boundary, "reference_numbers": references or [],
                "unknown_token_offsets": unknown,
                "review_notes": (["Exact authorized display offsets; finer raw offsets not claimed."]
                                 if not segments else [])
                                + (["BGE UNK tokens; original source characters retained."]
                                   if unknown else []),
            })

        for source in record.indexable_source_content:
            initial_chunks, initial_blocked = len(chunks), len(unresolved)
            n, kind = len(source.text), source.content_type.lower()
            segments = display_segments(source)
            if self.tokenizer.count(prefix) >= total_tokens:
                blocked(source, 0, n, "REQUIRED_HEADING_EXHAUSTS_TOKEN_BUDGET")
            elif kind in SPECIALIZED:
                if self.tokenizer.count(prefix + source.text) <= total_tokens:
                    emit(source, segments, 0, n, "whole_typed_element_preserved")
                else:
                    blocked(source, 0, n, "OVERSIZED_ATOMIC_ELEMENT_REQUIRES_REVIEW")
            elif kind not in PROSE:
                blocked(source, 0, n, "UNSUPPORTED_NATIVE_STRUCTURE_NOT_FORCED_INTO_PROSE")
            elif self.tokenizer.count(prefix + source.text) <= total_tokens:
                emit(source, segments, 0, n, "whole_authorized_source_field_preserved")
            elif kind == "bibliography":
                try:
                    entries = bibliography_entries(source, segments)
                except ValueError:
                    blocked(source, 0, n, "UNVERIFIED_REFERENCE_BOUNDARIES")
                else:
                    pending = []

                    def flush(source=source, segments=segments, pending=pending):
                        if pending:
                            emit(source, segments, pending[0]["start"], pending[-1]["end"],
                                 "verified_reference_entry_boundaries",
                                 [a["reference_number"] for a in pending])
                            pending.clear()

                    for atom in entries:
                        a, b = atom["start"], atom["end"]
                        if self.tokenizer.count(prefix + source.text[a:b]) > total_tokens:
                            flush()
                            blocked(source, a, b, "OVERSIZED_REFERENCE_ENTRY")
                        else:
                            if pending and self.tokenizer.count(
                                    prefix + source.text[pending[0]["start"]:b]) > total_tokens:
                                flush()
                            pending.append(atom)
                    flush()
            else:
                from langchain_text_splitters import RecursiveCharacterTextSplitter

                # Reuse M2's lossless splitter policy. Counting the complete prefix
                # in the length function is conservative; exact emit checks remain.
                allowance = total_tokens - self.tokenizer.count(prefix)
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=allowance, chunk_overlap=0,
                    length_function=lambda t: self.tokenizer.count(t, special=False),
                    keep_separator="end", strip_whitespace=False,
                    separators=[r"\n\n", r"(?<=[.!?])\s+", r"\s+"], is_separator_regex=True)
                pieces = splitter.split_text(source.text)
                if "".join(pieces) != source.text:
                    blocked(source, 0, n, "SPLITTER_NON_LOSSLESS_PARTITION")
                else:
                    pos = 0
                    for piece in pieces:
                        emit(source, segments, pos, pos + len(piece),
                             "m2_lossless_sentence_then_whitespace_policy")
                        pos += len(piece)
            outcomes = chunks[initial_chunks:] + unresolved[initial_blocked:]
            pos = 0
            for item in sorted(outcomes, key=lambda i: i["display_start"]):
                if item["display_start"] != pos or item["display_end"] <= pos:
                    raise ValueError("m3_duplicated_or_missing_display_interval")
                pos = item["display_end"]
            if pos != n:
                raise ValueError("m3_incomplete_source_field_accounting")
            coverage.append({"source_pointer": source.source_pointer,
                             "content_type": source.content_type, "source_characters": n,
                             "chunked_characters": sum(c["display_end"] - c["display_start"]
                                                       for c in chunks[initial_chunks:]),
                             "unresolved_characters": sum(u["display_end"] - u["display_start"]
                                                          for u in unresolved[initial_blocked:]),
                             "exact_display_coverage_accounted": True})
        return {"version": VERSION, "chunks": chunks, "unresolved": unresolved,
                "source_results": coverage,
                "non_indexable": [{"source_pointer": p["source_pointer"],
                    "reason": "PROTECTED_WARNING_BEARING_NATIVE_PROJECTION_NO_INDEPENDENT_INDEXABLE_FIELD",
                    "obligation": "Use unchanged complete verified parent; never strip warnings or "
                                  "index alternative native fields."}
                    for p in record.protected_consumable_projections]}
