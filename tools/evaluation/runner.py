"""Offline fixed M9 evaluation using unchanged M7 retrieval and live M8 assembly."""

import argparse
import json
import platform
import resource
import time
from pathlib import Path

from tools.evaluation.contract import load_configuration
from tools.evaluation.metrics import evidence, retrieval, summarize
from tools.evidence.contract import M7_SELECTOR, M7_SHA, validate_candidates
from tools.evidence.service import EvidenceService
from tools.indexing.m5_index import encoded, local, sha
from tools.retrieval.contract import fuse
from tools.retrieval.service import RetrievalService

M8 = 'config/evidence-reconstruction-m8-v1.json'
M8_SHA = 'e0ac189c8b5ffd331f28ae87f81d56c22868e12c45d7b73e6a5e7f1a65c6bef2'


def write_once(path, value):
    payload = encoded(value)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError('m9_existing_output_differs:' + path.name)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.partial')
    with temp.open('xb') as stream:
        stream.write(payload)
    temp.chmod(0o600)
    temp.rename(path)


def stable_candidates(result):
    return {k: v for k, v in result.items() if k != 'diagnostics'}


def obligations(package):
    output = []
    for item in package['parents']:
        parent = item['evidence']['verified_parent']
        context = parent['consumer']['llm_context']
        if (not parent['citation_locators'] or not context['qualification']
                or any(s.get('kind') != 'SOURCE_CONTENT' for s in context['source_content'])):
            raise ValueError('m9_native_obligations_missing')
        output.append({'unit_id': parent['unit_id'],
                       'publication_sha256': sha(encoded(parent['publication_identity'])),
                       'source_sha256': sha(encoded(context['source_content'])),
                       'context_sha256': sha(encoded(context['required_context'])),
                       'qualification_sha256': sha(encoded(context['qualification'])),
                       'QA_observations_sha256': sha(encoded(context['qa_observations'])),
                       'citations_sha256': sha(encoded(parent['citation_locators'])),
                       'memberships_sha256': sha(encoded(parent['memberships'])),
                       'native_complete_parent_validated': True,
                       'source_and_QA_fields_separate': True,
                       'token_count': item['token_count']})
    return output


def diagnostic_result(service, label):
    """All owner-known positives, not actual search. Never enters retrieval scoring."""
    ids = sorted(label['proposed_positive_chunk_ids'])
    hits = [{'chunk_id': cid, **service.inventory[cid], 'rank': i,
             'score': float(len(ids) - i)} for i, cid in enumerate(ids, 1)]
    result = {'schema': 'm7-candidates-1.0',
              'authority': 'CANDIDATES_ONLY_NOT_AUTHORIZED_EVIDENCE',
              'complete_parent_rehydration_required': True, 'retrieval_mode': 'bm25',
              'release_identity': service.m7['identity'],
              'selection': {'path': M7_SELECTOR, 'sha256': M7_SHA},
              'index_release_bindings': service.m7['spec']['selections'],
              'query_sha256': sha(('M9_REFERENCE_FIT_DIAGNOSTIC:' + label['question_id']).encode()),
              'parameters': {'top_k': max(1, len(ids)), 'candidate_depth': max(50, len(ids)),
                             'rrf_k': 60, 'filters': {}},
              'candidates': fuse({'bm25': hits}, mode='bm25', top_k=max(1, len(ids)),
                                 rrf_k=60, inventory=service.inventory, filters={}),
              'diagnostics': {'origin': 'KNOWN_POSITIVE_PARENT_FIT_CONTROL_NOT_RETRIEVAL'}}
    return result


def expected_fit(service, label, budgets):
    if not label['required_evidence_groups']:
        return {'authority': 'DIAGNOSTIC_NOT_RETRIEVAL_SCORE', 'answerable': False}
    control = diagnostic_result(service, label)
    package = service.assemble(control, token_budget=1000000)
    service.validate(package, control)
    costs = {p['evidence']['unit_id']: p['token_count'] for p in package['parents']}
    if package['diagnostics']['omitted']:
        raise ValueError('m9_expected_control_exceeds_diagnostic_limit')
    chosen = []
    for group in label['required_evidence_groups']:
        chosen.append(min((a['unit_id'] for a in group['alternatives']), key=lambda u: (costs[u], u)))
    reserved = sum(costs[u] for u in set(chosen))
    return {'authority': 'DIAGNOSTIC_NOT_RETRIEVAL_SCORE', 'answerable': True,
            'method': 'Live M8 on known-positive controls. Least costly approved alternative per group; '
                      'sum of whole-block reserves, no query competition. Wrapper uses control ranks '
                      'and known-positive contributions, so actual search costs may differ.',
            'parent_block_tokens': costs, 'selected_alternative_unit_ids': chosen,
            'reserved_tokens_for_all_groups': reserved,
            'all_groups_fit_estimate': {str(b): reserved <= b for b in budgets},
            'live_parent_reconstruction_passed': True}


def component_costs(service, uid):
    parent = service.corpus.evidence.get_verified_unit(uid)
    service.corpus.evidence.validate(parent)
    consumer = parent['consumer']
    ctx = consumer['llm_context']
    text = '\n'.join(s.get('text') or s.get('restricted_projection', {}).get('consumable_text', '')
                     for s in ctx['source_content'])
    fields = {'native_parent': parent, 'native_consumer': consumer,
              'structured_source_content': ctx['source_content'],
              'text_bearing_source_fields_including_inseparable_warnings': text,
              'required_context': ctx['required_context'], 'qa_observations': ctx['qa_observations'],
              'qualification': ctx['qualification'], 'citation_locators': parent['citation_locators'],
              'memberships': parent['memberships'], 'publication_identity': parent['publication_identity']}
    texts = [value if isinstance(value, str) else encoded(value).decode()
             for value in fields.values()]
    counts = service._count(texts)  # Existing pinned counting contract; measurement, no inference.
    return {'unit_id': uid, 'document_id': parent['document_id'],
            'measurement': 'Independent field serializations with specials; NOT additive, '
                           'NOT a compact consumable projection or alternate authorization.',
            'fields': {key: {'tokens': count, 'characters': len(text)}
                       for key, text, count in zip(fields, texts, counts, strict=True)}}



def budget_measurement(job):
    """Independent live gateways; result joining retains fixed budget order."""
    engine, result, label, measured, budget = job
    package = engine.assemble(result, token_budget=budget)
    replay = label['question_id'] in {'M9-Q01', 'M9-Q21'}
    if replay:
        engine.validate(package, result)
    if package['verification'] != 'LIVE_NATIVE_PARENT_BINDINGS_VERIFIED':
        raise ValueError('m9_missing_live_M8_verification')
    bm = evidence(label, measured, package)
    bm['obligations'] = obligations(package)
    bm['package_sha256'] = sha(encoded(package))
    bm['live_revalidation_and_deterministic_package_replay'] = replay
    bm['live_native_parent_binding_validation'] = True
    costs = {}
    for p in [*package['parents'], *package['diagnostics']['omitted']]:
        uid = p.get('unit_id') or p['evidence']['unit_id']
        costs[uid] = p['token_count']
    return bm, costs


def run(root, output, *, config_sha):
    root = Path(root).resolve(strict=True)
    output = local(root, output)
    if not output.is_relative_to(root / 'data/evals/m9/runs'):
        raise ValueError('m9_outputs_must_be_private_evaluation_data')
    config, questions, labels = load_configuration(root, expected_sha=config_sha)
    write_once(output / 'FROZEN_RUN_SPEC.json', {'configuration': config, 'configuration_sha256': config_sha})
    started = time.perf_counter()
    engine = EvidenceService(root, selector=M8, selector_sha256=M8_SHA)
    search = RetrievalService(root, selector=M7_SELECTOR, selector_sha256=M7_SHA)
    rows = engine.catalog.list_chunks(limit=1000)['items']
    parents = {r['chunk_id']: r['unit_id'] for r in rows}
    if len(parents) != 992 or set(parents) != set(search.inventory):
        raise ValueError('m9_exact_inventory_mismatch')
    settings = config['settings']
    print('M9_GATEWAY_READY: approved 29 questions / exact 992 IDs', flush=True)
    cases, diagnostics, max_cost = [], {}, {}
    try:
        for question in questions:
            qid = question['question_id']
            label = labels[qid]
            for mode in settings['modes']:
                case_path = output / 'cases' / (qid + '-' + mode + '.json')
                seal_path = case_path.with_suffix('.sha256')
                if case_path.exists():
                    if not seal_path.exists() or sha(case_path.read_bytes()) != json.loads(seal_path.read_text()):
                        raise ValueError('m9_resume_case_integrity_failed')
                    case = json.loads(case_path.read_bytes())
                    if case['configuration_sha256'] != config_sha:
                        raise ValueError('m9_resume_configuration_mismatch')
                    for bm in case['budgets'].values():
                        for p in [*bm['obligations'], *bm['omitted_parents']]:
                            max_cost[p['unit_id']] = max(max_cost.get(p['unit_id'], 0), p['token_count'])
                    cases.append(case)
                    print('RESUME_MEASUREMENT_ONLY', qid, mode, flush=True)
                    continue
                start = time.perf_counter()
                result = search.search(question['question'], mode=mode, top_k=10,
                                       candidate_depth=50, rrf_k=60, filters={})
                validate_candidates(result, engine.m7, engine.inventory)
                measured = retrieval(label, result['candidates'], parents)
                case = {'schema': 'm9-measured-case-1.0', 'authority': 'EVALUATION_NOT_EVIDENCE_AUTHORIZATION',
                        'configuration_sha256': config_sha, 'question_id': qid,
                        'category': question['category'], 'mode': mode,
                        'candidate_result': result, 'retrieval': measured, 'budgets': {}}
                for budget in settings['budgets']:
                    bm, costs = budget_measurement((engine, result, label, measured, budget))
                    case['budgets'][str(budget)] = bm
                    for uid, count in costs.items():
                        max_cost[uid] = max(max_cost.get(uid, 0), count)
                repeated = search.search(question['question'], mode=mode, top_k=10,
                                         candidate_depth=50, rrf_k=60, filters={})
                if encoded(stable_candidates(result)) != encoded(stable_candidates(repeated)):
                    raise ValueError('m9_repeated_ranking_changed')
                case['ranking_reproduction_passed'] = True
                case['elapsed_seconds_including_revalidation'] = time.perf_counter() - start
                write_once(case_path, case)
                write_once(seal_path, sha(case_path.read_bytes()))
                # Sidecars are JSON strings, parsed explicitly on resume below.
                cases.append(case)
                print('CASE_COMPLETE', qid, mode, 'first_relevant', measured['first_relevant_rank'],
                      'seconds', round(case['elapsed_seconds_including_revalidation'], 2), flush=True)
        for question in questions:
            qid = question['question_id']
            path = output / 'diagnostic' / (qid + '.json')
            seal = path.with_suffix('.sha256')
            if path.exists():
                if not seal.exists() or sha(path.read_bytes()) != json.loads(seal.read_text()):
                    raise ValueError('m9_diagnostic_resume_integrity_failed')
                diagnostics[qid] = json.loads(path.read_bytes())
            else:
                diagnostics[qid] = expected_fit(engine, labels[qid], settings['budgets'])
                write_once(path, diagnostics[qid])
                write_once(seal, sha(path.read_bytes()))
            print('EXPECTED_PARENT_FIT_DIAGNOSTIC', qid, flush=True)
        q21_uid = labels['M9-Q21']['required_evidence_groups'][0]['alternatives'][0]['unit_id']
        largest = [u for u, _ in sorted(max_cost.items(), key=lambda pair: (-pair[1], pair[0]))[:5]]
        costs = [component_costs(engine, uid) for uid in dict.fromkeys([q21_uid, *largest])]
        engine.check()
        search.check()
        load_configuration(root, expected_sha=config_sha)
        summary = summarize(cases, settings['modes'], settings['budgets'])
        result = {'schema': 'm9-measured-results-1.0', 'authority': 'INSPECTION_ONLY_NOT_EVIDENCE_AUTHORIZATION',
                  'status': 'EVALUATION_COMPLETE_PENDING_OWNER_ACCEPTANCE',
                  'configuration_sha256': config_sha, 'benchmark_sha256': config['benchmark']['sha256'],
                  'approval_sha256': config['approval']['sha256'], 'settings': settings,
                  'case_count': len(cases), 'budget_observation_count': len(cases) * 4,
                  'integrity_failures': [], 'summary': summary,
                  'cases': cases, 'expected_parent_fit_diagnostics': diagnostics,
                  'component_costs_non_additive': costs,
                  'largest_actual_parent_block_tokens': dict(sorted(max_cost.items(), key=lambda p: -p[1])[:15]),
                  'runtime': {'python': platform.python_version(), 'platform': platform.platform(),
                              'elapsed_seconds': time.perf_counter() - started,
                              'coordinator_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
                  'limitations': ['29 source-authored exposed questions; not held-out or statistically representative.',
                                 '26 answerable denominators, three unsupported controls, bounded known-positive labels.',
                                 'Unjudged candidates are not automatically irrelevant.',
                                 'BGE evidence budgets are not an M10 context-window selection.',
                                 'No answer faithfulness, generation, compact evidence or alternate chunk-size experiment.']}
        write_once(output / 'RESULTS.json', result)
        print('M9_PRIMARY_EVALUATION_COMPLETE', len(cases), 'cases', flush=True)
        return result
    finally:
            search.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', default='data/evals/m9/runs/m9-v3')
    parser.add_argument('--config-sha256', required=True)
    args = parser.parse_args()
    run(args.root, args.output, config_sha=args.config_sha256)


if __name__ == '__main__':
    main()
