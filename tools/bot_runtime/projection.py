"""One read-only source projection for every Bot operational page. No runner imports."""
from datetime import UTC, datetime
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, digest

from .store import ID, QUESTIONS, RUNS, load, question_record, read, verify_reference


def discover(root, *, include_native=True):
    root = Path(root)
    questions, rejected, attempts = {}, [], {}
    for folder in sorted((root / QUESTIONS).glob('BOT-*')):
        try:
            questions[folder.name] = question_record(root, folder.name)
        except (ArtifactError, OSError, ValueError, TypeError, KeyError):
            rejected.append({'question_id': folder.name, 'reason': 'UNVERIFIED_QUESTION'})
    for run in sorted((root / RUNS).glob('bot-*')):
        try:
            start = read(run / 'START.json')
            qid = start['question_id']
            q = verify_reference(root, qid, start['question_reference'])
            claim = read(root / RUNS / 'claims' / (qid + '-' + start['mode'] + '.json'))
            if (start.get('schema') != 'runtime-start-1.0' or start['run_id'] != run.name
                    or not ID.fullmatch(qid) or start.get('mode') not in {'mock', 'local-check'}
                    or claim != {'question_id': qid, 'run_id': run.name, 'mode': start['mode'],
                                 'question_reference': start['question_reference']}
                    or start.get('generation_authorized') is not False):
                raise ArtifactError('INVALID_RUNTIME_START')
            if not (run / 'MANIFEST.json').exists():
                value = {'question_id': qid, 'run_id': run.name, 'mode': start['mode'],
                         'execution_status': 'INCOMPLETE', 'application_outcome': 'RECOVERY_REQUIRED',
                         'response': None, 'model_status': None, 'response_contract_status': 'NOT_RUN',
                         'validation_status': 'NOT_RUN', 'cost_usd': None, 'provider_calls': 0,
                         'diagnostics': ['NO_COMPLETED_SEAL_NO_AUTOMATIC_REPLAY']}
            else:
                manifest = load(run, 'runtime-execution-1.0')
                if not {'START.json', 'RESULT.json', 'STAGE_TIMINGS.json'} <= set(manifest['files']):
                    raise ArtifactError('INCOMPLETE_RUNTIME_MANIFEST')
                value = read(run / 'RESULT.json')
                if (manifest.get('run_id') != run.name or manifest.get('question_id') != qid
                        or manifest.get('mode') != start['mode'] or value.get('question_id') != qid
                        or value.get('run_id') != run.name or value.get('mode') != start['mode']
                        or value.get('question_reference') != start['question_reference']
                        or value.get('question_sha256') != q['question_sha256']
                        or value.get('provider_calls') != 0 or value.get('generation_executed') is not False
                        or value.get('fixture_only') is not (start['mode'] == 'mock')
                        or manifest.get('generation_authority') is not False):
                    raise ArtifactError('INVALID_RUNTIME_RESULT_BINDINGS')
                from tools.generation_runner.bot_timing import validate
                value['timings'] = validate(read(run / 'STAGE_TIMINGS.json'))
                if (value['timings']['question_id'] != qid or value['timings']['run_id'] != run.name
                        or value['timings']['request_sha256'] != value['request_sha256']
                        or value['timings']['M8_package_sha256'] != value['M8_package_sha256']):
                    raise ArtifactError('INVALID_RUNTIME_TIMING_BINDINGS')
                for file, key in [('CANDIDATES.json', 'M7_result_sha256'), ('EVIDENCE_PACKAGE.json', 'M8_package_sha256')]:
                    if value.get(key) and digest(read(run / file)) != value[key]:
                        raise ArtifactError('RUNTIME_STAGE_IDENTITY_CHANGED')
                if value.get('response') and digest(value['response']) != value.get('response_sha256'):
                    raise ArtifactError('RUNTIME_RESPONSE_CHANGED')
                if value.get('raw_capture'):
                    from tools.generation.response_capture import verify_capture
                    verify_capture(root, value['raw_capture'], value, run_id=run.name)
                if value.get('request_sha256'):
                    request_file = 'WIRE_REQUEST.json' if value['mode'] == 'mock' and 'WIRE_REQUEST.json' in manifest['files'] else 'REQUEST_PACKAGE.json'
                    request = read(run / request_file)
                    if request_file == 'REQUEST_PACKAGE.json':
                        request = request['request']
                    if digest(request) != value['request_sha256']:
                        raise ArtifactError('RUNTIME_REQUEST_CHANGED')
                value['manifest_path'] = (run / 'MANIFEST.json').relative_to(root).as_posix()
            value['artifacts'] = {name: read(run / name) for name in (
                'CANDIDATES.json', 'RETRIEVAL_OBSERVATIONS.json', 'LOCAL_VALIDATION.json',
                'POST_VALIDATION.json', 'RESPONSE_OBSERVATION.json')
                if (run / 'MANIFEST.json').exists() and name in manifest['files']}
            # Full request/evidence/raw publisher bytes deliberately not loaded here.
            value['created_at'] = start['created_at']
            attempts.setdefault(qid, []).append(value)
        except (ArtifactError, OSError, ValueError, TypeError, KeyError):
            rejected.append({'run_id': run.name, 'reason': 'UNVERIFIED_RUNTIME_RESULT'})
    for values in attempts.values():
        values.sort(key=lambda a: (datetime.fromisoformat(a['created_at']).astimezone(UTC), a['run_id']))
    records = {qid: {'question_id': qid, 'question': q['question'], 'reference': q,
                      'question_source': 'BOT', 'attempts': attempts.get(qid, [])}
               for qid, q in questions.items()}
    if include_native:
        from .qualification import discover as qualifications
        observations, bad = qualifications(root)
        rejected.extend(bad)
        for qid, values in observations.items():
            if qid in records:
                records[qid]['attempts'].extend(values)
    native_count = 0
    if include_native and (root / 'data/evals/generation-runner').exists():
        from .native import operational
        from .native import records as native_records
        native, bad = native_records(root, records)
        rejected.extend(bad)
        for qid, record in native.items():
            projected=[]
            for attempt in record['attempts']:
                try:
                    projected.append(operational(root,record,attempt))
                except (ArtifactError,ValueError,KeyError,TypeError,OSError):
                    rejected.append({'question_id':qid,'status':'INVALID_NATIVE_BOT_PROJECTION'})
            native_count += sum(bool(a.get('generation_attempted') or a.get('generation_executed')) for a in projected)
            records[qid]['attempts'].extend(projected)
            records[qid]['attempts'].sort(key=lambda a: (datetime.fromisoformat(a['created_at']).astimezone(UTC), a['run_id']))
    unresolved=0
    if include_native:
        from .native import incomplete
        known={a['run_id'] for r in records.values() for a in r['attempts'] if a.get('native_attempt')}
        pending,bad=incomplete(root,records,known)
        rejected.extend(bad)
        for qid,rows in pending.items():
            records[qid]['attempts'].extend(rows)
            records[qid]['attempts'].sort(key=lambda a:(datetime.fromisoformat(a['created_at']).astimezone(UTC),a['run_id']))
            unresolved+=len(rows)
            native_count+=sum(bool(r.get('generation_attempted')) for r in rows)
    from .disposition import read as read_disposition
    for qid,record in records.items():
        try:
            from .chat_records import record as chat_record
            record['chat_execution'] = chat_record(root, qid)
        except (ArtifactError,OSError,ValueError,KeyError,TypeError):
            record['chat_execution'] = None
            rejected.append({'question_id':qid,'reason':'UNVERIFIED_CHAT_EXECUTION'})
        try:
            disposition=read_disposition(root,qid)
            record['disposition']='DISCARDED' if disposition else 'ACTIVE'
            record['disposition_record']=disposition
            if disposition:
                for attempt in record['attempts']:
                    attempt['question_disposition']='DISCARDED'
        except (ArtifactError,OSError,ValueError,KeyError,TypeError):
            record['disposition']='UNVERIFIED_DISPOSITION'
            rejected.append({'question_id':qid,'reason':'UNVERIFIED_DISPOSITION'})
    return {'records': records, 'rejected': rejected, 'source': 'BOT',
        'summary': {'questions': len(records), 'mock_runs': sum(a['mode'] == 'mock' for aa in attempts.values() for a in aa),
                    'discarded_questions':sum(r['disposition']=='DISCARDED' for r in records.values()),
                    'unresolved_native_runs': unresolved, 'real_generation_requests': native_count, 'offline_evaluation_eligible': 0}}


def workspace(root, source, *, benchmark_loader):
    """Keep legacy reader membership and shape intact; resolve source once."""
    if source == 'BOT':
        return discover(root)
    if source == 'BENCHMARK':
        return benchmark_loader(root)
    raise ValueError('UNKNOWN_QUESTION_SOURCE')
