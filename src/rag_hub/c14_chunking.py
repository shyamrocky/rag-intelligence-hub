"""Chunk only newly QA-qualified C14 scopes using published source witnesses.

Author-year references have no invented printed reference numbers. Heading text
is context; citations/qualifications remain in the complete verified parent.
"""
from rag_hub.chunk_inputs import ChunkInput, SourceContent
from rag_hub.structure_chunking import display_segments, mapped_lineage
from rag_hub.unified_models import sha

VERSION = 'm3-c14-qualified-scopes-1.0'


def chunk_c14(preparation, prepared, tokenizer, *, total_tokens=384):
    preparation.validate(prepared)
    record = ChunkInput.model_validate(prepared['record'])
    if record.document_id != 'C14' or total_tokens not in {256, 384}:
        raise ValueError('unsupported_c14_scope_or_budget')
    headings = prepared['headings']
    prefix = '\n'.join(h['text'] for h in headings) + '\n\n'
    chunks, unresolved = [], []
    for field in prepared['search_sources']:
        source = SourceContent.model_validate(field)
        structure = source.native_source.get('structure') or {}
        if (not headings or not record.qualification.get('complete_unit_only')
                or structure.get('scope') not in {'bibliographic_attribution', 'substantive_appendix'}):
            raise ValueError('unqualified_c14_scope')
        atoms = structure.get('reference_entries') if source.content_type == 'bibliography' else [
            {'start': 0, 'end': len(source.text)}]
        if not atoms:
            raise ValueError('missing_c14_reference_witnesses')
        pos = 0
        for atom in atoms:
            if atom['start'] != pos or not pos < atom['end'] <= len(source.text):
                raise ValueError('unverified_c14_partition')
            pos = atom['end']
        if pos != len(source.text):
            raise ValueError('unaccounted_c14_source_suffix')
        segments = display_segments(source)
        if not segments:
            raise ValueError('missing_c14_exact_source_span_map')

        def emit(a, b, budget, source=source, segments=segments):
            text = source.text[a:b]
            enc = tokenizer.encode(prefix + text)
            if len(enc.ids) > budget:
                raise ValueError('c14_token_budget_no_truncation')
            chunks.append({'unit_id': record.unit_id, 'document_id': record.document_id,
                'source_pointer': source.source_pointer, 'source_projection_sha256': sha(source.text.encode()),
                'display_start': a, 'display_end': b, 'source_text': text,
                'source_text_sha256': sha(text.encode()), 'content_type': source.content_type,
                'lineage': mapped_lineage(record, source, segments, a, b),
                'reference_classification': record.reference_classification, 'heading_context': headings,
                'token_count': len(enc.ids), 'body_token_count': tokenizer.count(text, special=False),
                'boundary_decision': 'source_geometry_witnessed_author_year_reference_entries'
                    if source.content_type == 'bibliography' else 'whole_source_qualified_appendix_section',
                'reference_numbers': [], 'unknown_token_offsets': [
                    {'embedding_start': a, 'embedding_end': b}
                    for token, (a, b) in zip(enc.ids, enc.offsets, strict=True) if token == 100],
                'review_notes': ['Search derivative only; complete authoritative parent mandatory.',
                    'Printed author-year references have no synthetic reference numbers.'],
                'budget_limit': budget})

        pending = []
        for atom in atoms:
            a, b = atom['start'], atom['end']
            count = tokenizer.count(prefix + source.text[a:b])
            if count > total_tokens:
                if pending:
                    emit(pending[0]['start'], pending[-1]['end'], total_tokens)
                    pending = []
                # Selective larger elements are allowed only for the 384 default.
                if total_tokens == 384 and count <= 512:
                    emit(a, b, 512)
                else:
                    unresolved.append({'source_pointer': source.source_pointer,
                        'display_start': a, 'display_end': b,
                        'reason': 'INDIVISIBLE_SOURCE_SCOPE_EXCEEDS_CONFIGURATION',
                        'tokens_including_heading_specials': count})
            else:
                if pending and tokenizer.count(prefix + source.text[pending[0]['start']:b]) > total_tokens:
                    emit(pending[0]['start'], pending[-1]['end'], total_tokens)
                    pending = []
                pending.append(atom)
        if pending:
            emit(pending[0]['start'], pending[-1]['end'], total_tokens)
    preparation.validate(prepared)
    return {'chunks': chunks, 'unresolved': unresolved, 'default_tokens': total_tokens}
