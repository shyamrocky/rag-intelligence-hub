"""Bounded source partitions; no execution, claim validation or QA authority."""
import re
from itertools import pairwise

from rag_hub.chunk_inputs import ChunkInput, SourceContent
from rag_hub.structure_chunking import display_segments, mapped_lineage
from rag_hub.unified_models import sha

VERSION = "m3-qualified-structure-1.0"


def typescript_atoms(text):
    """Conservative lexical statement map for the documented TS subset only.

    Recognizes balanced (), [], {}, comments, quoted strings and whole templates.
    Interpolation is limited to simple property paths; regex literals and other
    slash operators abstain. This is not a TS parser or executability check.
    Never cuts functions, expressions, object literals, or template strings.
    """
    if not text.startswith("```typescript\n") or not text.endswith("\n```"):
        raise ValueError("unsupported_complete_TypeScript_fence")
    lo, hi = len("```typescript\n"), len(text) - len("\n```")
    stack, starts = [], []
    i, ended, function, statement = lo, True, False, False
    while i < hi:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                raise ValueError("unterminated_comment")
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise ValueError("unterminated_comment")
            i = end + 2
            continue
        at_line_start = i == lo or text[i - 1] == "\n"
        if at_line_start and not stack:
            m = re.match(r"(?:import\b|const\b|await\b|async function\b)", text[i:])
            if m:
                if not ended:
                    raise ValueError("ambiguous_TypeScript_statement_boundary")
                starts.append(i)
                function = text.startswith("async function", i)
                ended, statement = False, True
        if not statement:
            raise ValueError("unsupported_TypeScript_statement")
        if c in "'\"`":
            quote, start = c, i
            i += 1
            while i < hi:
                if text[i] == "\\":
                    i += 2
                elif text[i] == quote:
                    break
                elif text[i] == "\n" and quote != "`":
                    raise ValueError("newline_in_quoted_string")
                else:
                    i += 1
            if i >= hi:
                raise ValueError("unterminated_TypeScript_literal")
            if quote == "`":
                literal = text[start + 1:i]
                # No nested grammar inference inside a template interpolation.
                stripped = re.sub(r"\$\{[A-Za-z_$][\w$]*(?:(?:\?\.|\.)[A-Za-z_$][\w$]*)*\}", "", literal)
                if "${" in stripped:
                    raise ValueError("unsupported_template_interpolation")
            i += 1
            continue
        if c == "/":
            raise ValueError("unsupported_regex_or_slash_operator")
        if c in "([{":
            stack.append(c)
        elif c in ")]}":
            if not stack or stack.pop() != {")": "(", "]": "[", "}": "{"}[c]:
                raise ValueError("unbalanced_TypeScript_delimiters")
            if not stack and function and c == "}":
                ended = True
        elif c == ";" and not stack:
            ended = True
        i += 1
    if stack or not ended or not starts:
        raise ValueError("incomplete_TypeScript_statement_map")
    cuts = [0, *starts[1:], len(text)]
    return [{"start": a, "end": b} for a, b in pairwise(cuts)], {
        "method": "conservative_TS_lexical_top_level_statement_map",
        "cuts": cuts, "code_executed": False,
        "unsupported_syntax_abstains": True, "not_a_full_TypeScript_parser": True}


def prompt_atoms(source):
    segments = display_segments(source)
    matches = [s for s in segments if re.match(r"(?:\d+\s*)?Example:",
               source.text[s["start"]:s["end"]].strip())]
    if len(matches) != 1:
        raise ValueError("missing_or_ambiguous_source_Example_boundary")
    cut = matches[0]["start"]
    if not 0 < cut < len(source.text):
        raise ValueError("invalid_Example_boundary")
    return [{"start": 0, "end": cut}, {"start": cut, "end": len(source.text)}], {
        "method": "printed_Example_boundary_preserving_whole_example_response_and_rules",
        "cuts": [0, cut, len(source.text)], "source_witness": matches[0],
        "prompt_executed": False}


def source_lineage(record, source, start, end):
    segment = source.native_source.get("segment")
    if segment:
        # Markdown native segments are exact source codepoints/bytes. No guessed
        # PDF display/raw equivalence or reclassification of native QA roles.
        text = source.text[start:end]
        a = segment["chars_0based_end_exclusive"][0]
        byte = segment["bytes_0based_end_exclusive"][0]
        return {"precision": "AUTHORIZED_PROTECTED_QUOTATION_EXACT_SOURCE_SPAN",
            "source_spans": [{"section_id": segment["section_id"],
                "source_sha256": segment["source_sha256"],
                "chars_0based_end_exclusive": [a + start, a + end],
                "bytes_0based_end_exclusive": [byte + len(source.text[:start].encode()),
                                               byte + len(source.text[:end].encode())],
                "span_sha256": sha(text.encode()), "role": segment["role"]}],
            "section_ids": source.section_ids, "synthetic_joiners": [],
            "section_scope": "source quotation; whole qualified parent mandatory"}
    return mapped_lineage(record, source, display_segments(source), start, end)


def _partition_verified(prepared, source_data, tokenizer):
    record = ChunkInput.model_validate(prepared["record"])
    source = SourceContent.model_validate(source_data)
    headings = prepared["headings"]
    prefix = "\n".join(h["text"] for h in headings)
    prefix = prefix + "\n\n" if prefix else ""
    if record.document_id == "C14":
        raise ValueError("C14_deferred_not_authorized")
    evidence = {"method": "whole_explicit_authorized_source_segment"}
    count = tokenizer.count(prefix + source.text)
    if count <= 512:
        atoms = [{"start": 0, "end": len(source.text)}]
    elif record.document_id == "C16" and source.content_type == "code_block":
        atoms, evidence = typescript_atoms(source.text)
    elif record.document_id == "C06" and source.content_type == "code_example":
        atoms, evidence = prompt_atoms(source)
    else:
        raise ValueError("no_defensible_source_boundary")
    chunks, unresolved = [], []

    def emit(a, b, limit):
        text = source.text[a:b]
        enc = tokenizer.encode(prefix + text)
        if len(enc.ids) > limit or limit not in {384, 512}:
            raise ValueError("token_budget_exceeded_no_truncation")
        chunks.append({"unit_id": record.unit_id, "document_id": record.document_id,
            "source_pointer": source.source_pointer, "source_projection_sha256": sha(source.text.encode()),
            "display_start": a, "display_end": b, "source_text": text,
            "source_text_sha256": sha(text.encode()), "content_type": source.content_type,
            "lineage": source_lineage(record, source, a, b),
            "reference_classification": record.reference_classification,
            "heading_context": headings, "token_count": len(enc.ids),
            "body_token_count": tokenizer.count(text, special=False),
            "boundary_decision": evidence["method"], "reference_numbers": [],
            "unknown_token_offsets": [{"embedding_start": x, "embedding_end": y}
                for t, (x, y) in zip(enc.ids, enc.offsets, strict=True) if t == 100],
            "review_notes": ["Search representation only; complete authoritative parent mandatory.",
                "Source examples/claims are not independently validated executable guidance.",
                "QA commentary is not embedding source text."],
            "budget_limit": limit})

    pending = []
    for atom in atoms:
        a, b = atom["start"], atom["end"]
        tokens = tokenizer.count(prefix + source.text[a:b])
        if tokens > 512:
            if pending:
                emit(pending[0]["start"], pending[-1]["end"], 384)
                pending = []
            unresolved.append({"source_pointer": source.source_pointer, "display_start": a,
                "display_end": b, "source_text_sha256": sha(source.text[a:b].encode()),
                "reason": "INDIVISIBLE_SOURCE_STATEMENT_EXCEEDS_512",
                "tokens_including_headings_specials": tokens,
                "section_ids": source.section_ids, "source_spans": source.source_spans})
        elif tokens > 384:
            if pending:
                emit(pending[0]["start"], pending[-1]["end"], 384)
                pending = []
            emit(a, b, 512)
        else:
            if pending and tokenizer.count(prefix + source.text[pending[0]["start"]:b]) > 384:
                emit(pending[0]["start"], pending[-1]["end"], 384)
                pending = []
            pending.append(atom)
    if pending:
        emit(pending[0]["start"], pending[-1]["end"], 384)
    pos = 0
    for x in sorted(chunks + unresolved, key=lambda r: r["display_start"]):
        if x["display_start"] != pos or x["display_end"] <= pos:
            raise ValueError("incomplete_or_overlapping_source_partition")
        pos = x["display_end"]
    if pos != len(source.text):
        raise ValueError("incomplete_source_partition")
    return {"chunks": chunks, "unresolved": unresolved, "evidence": evidence,
            "source_characters": len(source.text)}


class QualifiedChunker:
    def __init__(self, preparation, tokenizer):
        self.preparation, self.tokenizer = preparation, tokenizer

    def chunk(self, prepared, pointer):
        self.preparation.validate(prepared)
        source = next((s for s in prepared["search_sources"]
                       if s["source_pointer"] == pointer), None)
        if source is None:
            raise ValueError("not_an_authorized_search_source")
        result = _partition_verified(prepared, source, self.tokenizer)
        self.preparation.validate(prepared)
        return result
