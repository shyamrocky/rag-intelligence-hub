"""Historical observation replay when current request dependencies have changed.

Never qualifies a request. The suite's strict current-input reader and execution
checks remain unchanged. Old measurement payloads must still be hash-intact.
"""
import re
from decimal import Decimal
from pathlib import Path

from tools.preflight_suite.artifacts import BASE, CONFIG, EXPANDED_SHA, VERSION, read_run
from tools.quality_dashboard.artifacts import ArtifactError, Store


def historical_runs(root):
    history = []
    for path in sorted((Path(root) / BASE).glob('*/MANIFEST.json')):
        name = path.relative_to(root).as_posix()
        try:
            read_run(root, name)
            continue  # Current-compatible history is already in the primary suite view.
        except (ArtifactError, ValueError, KeyError, TypeError, OSError):
            pass
        try:
            store = Store(root)
            manifest = store.manifest(name, schema=VERSION)
            if (manifest.get('status') != 'COMPLETED_SEALED_PENDING_OWNER_REVIEW'
                    or manifest.get('expanded_benchmark_manifest_sha256') != EXPANDED_SHA
                    or manifest.get('configuration') != CONFIG
                    or manifest.get('mode') not in {'local-check', 'model-preflight'}
                    or manifest.get('generation_authorized') is not False):
                raise ArtifactError('UNQUALIFIED_HISTORICAL_PUBLICATION')
            base = name.rsplit('/', 1)[0]
            values = store.json(base + '/RESULTS.json')
            rows = values['questions']
            ids = [r['question_id'] for r in rows]
            if (values.get('schema') != VERSION or ids != manifest['question_ids']
                    or len(ids) != len(set(ids))):
                raise ArtifactError('HISTORICAL_INVENTORY_MISMATCH')
            for row in rows:
                _safe_row(row)
                qid = row['question_id']
                # Verify internal sealed receipt/request identity. Historical source,
                # model and pricing bindings are observations, never current authority.
                qm = store.json(base + f'/questions/{qid}/QUESTION_MANIFEST.json')
                request = store.json(base + f'/questions/{qid}/REQUEST_PACKAGE.json')
                if (qm['question_id'] != qid or qm['request_sha256'] != row['request_sha256']
                        or request['request_sha256'] != row['request_sha256']):
                    raise ArtifactError('HISTORICAL_REQUEST_IDENTITY_MISMATCH')
                for child, fingerprint in qm['files'].items():
                    store.bind(base + f'/questions/{qid}/' + child, fingerprint)
            history.append({'run_id': manifest['run_id'], 'mode': manifest['mode'],
                            'manifest': name, 'status': 'HISTORICAL_NOT_CURRENTLY_QUALIFIED',
                            'questions': [_safe_row(r) for r in rows]})
        except (ArtifactError, ValueError, KeyError, TypeError, OSError):
            continue  # Tampered/unsealed records remain unavailable, not historical passes.
    return history


def render(st, root):
    with st.expander('Historical observations with changed dependencies'):
        st.caption('Changed prompt, settings, pricing or implementation bindings block reuse. '
                   'Intact historical observations remain inspectable without current qualification. '
                   'Historical pricing arithmetic is not recomputed using a newer policy.')
        records = historical_runs(root)
        if not records:
            st.info('No additional stale-dependency histories. Current-compatible runs appear above.')
            return
        selected = st.selectbox('Historical preflight run', range(len(records)),
                                format_func=lambda i: records[i]['run_id'])
        record = records[selected]
        st.warning(record['status'] + ' — NOT eligible for generation or model preflight reuse.')
        st.text('Hash-verified historical manifest: ' + record['manifest'])
        keys = ['question_id', 'cohort_id', 'status', 'prompt_version', 'schema_version',
                'request_sha256', 'included_parents', 'evidence_BGE_tokens', 'model',
                'pricing_version', 'input_tokens', 'context_fit', 'maximum_cost_usd']
        st.dataframe([{k: r.get(k) for k in keys} for r in record['questions']], hide_index=True)


def _safe_row(row):
    """Only typed source-free telemetry crosses into the historical UI."""
    if (not re.fullmatch(r'(?:M9-Q(?:0[1-9]|[12][0-9])|R0[1-5])', row['question_id'])
            or row['cohort_id'] not in set('ABCD')
            or row['status'] not in {'LOCAL_VALIDATED', 'MODEL_QUALIFIED', 'BLOCKED_INPUT',
                                    'BLOCKED_CONTEXT', 'BLOCKED_CONFIGURATION', 'BLOCKED_INTEGRITY'}
            or row.get('generation_executed') is not False):
        raise ArtifactError('INVALID_HISTORICAL_TELEMETRY')
    value = {k: row[k] for k in ('question_id', 'cohort_id', 'status')}
    fingerprint = row.get('request_sha256')
    if fingerprint is not None and not re.fullmatch(r'[0-9a-f]{64}', fingerprint):
        raise ArtifactError('INVALID_HISTORICAL_REQUEST_HASH')
    value['request_sha256'] = fingerprint
    for key in ('prompt_version', 'schema_version', 'model', 'pricing_version'):
        item = row.get(key)
        if item is not None and (not isinstance(item, str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,100}', item)):
            raise ArtifactError('INVALID_HISTORICAL_VERSION')
        value[key] = item
    for key in ('included_parents', 'evidence_BGE_tokens', 'input_tokens'):
        item = row.get(key)
        if item is not None and (type(item) is not int or item < 0):
            raise ArtifactError('INVALID_HISTORICAL_COUNT')
        value[key] = item
    cost = row.get('maximum_cost_usd')
    if cost is not None and (not isinstance(cost, str) or len(cost) > 40
                             or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', cost)
                             or not Decimal(cost).is_finite()):
        raise ArtifactError('INVALID_HISTORICAL_COST')
    value['maximum_cost_usd'] = cost
    fit = row.get('context_fit')
    if isinstance(fit, dict):
        if any(k not in {'fits', 'input_tokens', 'reserved_output_tokens', 'safety_margin_tokens',
                         'remaining_context_margin', 'context_window', 'maximum_input_tokens'} for k in fit):
            raise ArtifactError('INVALID_HISTORICAL_CONTEXT')
        if any(type(v) is not (bool if k == 'fits' else int) for k, v in fit.items()):
            raise ArtifactError('INVALID_HISTORICAL_CONTEXT')
    elif fit not in (None, 'UNVERIFIED'):
        raise ArtifactError('INVALID_HISTORICAL_CONTEXT')
    value['context_fit'] = fit
    return value
