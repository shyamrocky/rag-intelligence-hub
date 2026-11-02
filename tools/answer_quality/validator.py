"""Post-generation-validation-2.0; independent dimensions and conservative acceptance.

Fixtures can call evaluate_dimensions but cannot establish live source authority.
Production/native integration uses PostGenerationValidator and existing public M8.
No gold labels, lexical semantics, new models, provider calls or answer repair.
"""
import copy
import hashlib
import re

from tools.pre_generation_gate.response_v2 import validate_response_shape
from tools.quality_dashboard.artifacts import ArtifactError, digest

from .fidelity import match_quote, safe_quote_record, source_fields
from .review import HumanReview, bound_assessment

VERSION = 'post-generation-validation-2.0'


def evaluate_dimensions(response, package, *, question, request_sha256,
                        qualification, assessment=None, layout_reviews=(), human_review_qualified=False,
                        fidelity_matcher=match_quote, version=VERSION):
    """Pure evaluation; caller must first validate source/request bindings live."""
    parents = {}
    for p in package['parents']:
        uid = p['evidence']['unit_id']
        if uid in parents:
            raise ArtifactError('DUPLICATE_SUPPLIED_PARENT')
        parents[uid] = p['evidence']['verified_parent']
    citation_refs = []
    try:
        for claim in response['claims']:
            citation_refs.extend(claim['evidence_unit_ids'])
            citation_refs.extend(q['evidence_unit_id'] for q in claim['supporting_quotes'])
        for item in response['requirement_coverage'] + response['conflicts_detected']:
            citation_refs.extend(item['evidence_unit_ids'])
        citation_valid = all(isinstance(u, str) and u in parents and not u.startswith('EXAMPLE-')
                             and parents[u].get('citation_locators') for u in citation_refs)
    except (KeyError, TypeError):
        citation_valid = False
    try:
        checked = validate_response_shape(response, authorized_unit_ids=set(parents)).model_dump()
        structure = 'PASS'
    except (ValueError, TypeError):
        checked, structure = None, 'FAIL'
    result = {'schema': version, 'response_sha256': digest(response),
        'M8_package_sha256': digest(package), 'request_sha256': request_sha256,
        'question_sha256': hashlib.sha256(question.encode()).hexdigest(),
        'structural_validation': structure, 'citation_validity': 'PASS' if citation_valid else 'FAIL',
        'qualification_status': qualification['status'], 'qualification_assessment': qualification,
        'semantic_status': 'PENDING_REVIEW', 'claim_grounding': [],
        'completeness': {'outcome': 'INDETERMINATE', 'requirements': []},
        'material_qualifications': 'INDETERMINATE', 'conflicts': 'INDETERMINATE',
        'quotation_fidelity': [], 'fully_validated': False, 'answer_rewritten': False,
        'model_calls': 0, 'diagnoses': [], 'review_reasons': []}
    if not checked or not citation_valid:
        result['overall_status'] = 'VALIDATION_FAILED'
        result['diagnoses'] = ['INVALID_CITATION'] if not citation_valid else ['INVALID_RESPONSE_SCHEMA']
        return result
    fields = {(uid, pointer): text for uid, parent in parents.items() for pointer, text in source_fields(parent)}
    for i, claim in enumerate(checked['claims']):
        for j, quote in enumerate(claim['supporting_quotes']):
            match = fidelity_matcher(quote['quote'], quote['evidence_unit_id'], parents.get(quote['evidence_unit_id']),
                                layout_reviews=layout_reviews)
            result['quotation_fidelity'].append(safe_quote_record(match) | {'claim_index': i, 'quote_index': j})
    failures = []
    fidelity = result['quotation_fidelity']
    if any(q['outcome'] in {'SUBSTANTIVE_MISMATCH', 'SOURCE_NOT_FOUND'} for q in fidelity):
        failures.append('SUBSTANTIVE_MISQUOTATION')
    if any(q['outcome'] == 'INDETERMINATE' for q in fidelity):
        result['review_reasons'].append('QUOTATION_PRESENTATION_REVIEW_REQUIRED')
    result['raw_exact_matches'] = {'numerator': sum(q['raw_exact_match'] for q in fidelity),
                                   'denominator': len(fidelity)}
    if qualification['status'] == 'QUALIFICATIONS_MISSING':
        failures.append('MISSING_QUALIFICATION')
    if assessment is not None:
        reviewed = bound_assessment(assessment, question=question, response=response, package=package,
                                    request_sha256=request_sha256, fields=fields)
        result['assessment'] = reviewed.model_dump()
        result['claim_grounding'] = [c.model_dump() for c in reviewed.claims]
        outcomes = {r.outcome for r in reviewed.requirements}
        complete = ('INDETERMINATE' if 'INDETERMINATE' in outcomes else
                    'INCOMPLETE' if 'INCOMPLETE' in outcomes else 'PARTIAL' if 'PARTIAL' in outcomes else 'COMPLETE')
        result['completeness'] = {'outcome': complete, 'requirements': [r.model_dump() for r in reviewed.requirements]}
        result['material_qualifications'] = reviewed.qualifications.outcome
        result['conflicts'] = reviewed.conflicts.outcome
        qualified = (human_review_qualified and reviewed.method == 'HUMAN_REVIEW' and reviewed.independent_of_generator
                     and reviewed.answer_claim_inventory_complete and reviewed.question_requirements_reviewed
                     and not reviewed.uncertainty)
        result['semantic_status'] = 'HUMAN_REVIEWED' if qualified else 'PROVISIONAL_NOT_ACCEPTED'
        result['independent_human_acceptance'] = qualified
        if qualified:
            if any(c.outcome in {'UNSUPPORTED', 'CONTRADICTED'} for c in reviewed.claims):
                failures.append('ESTABLISHED_UNSUPPORTED_OR_CONTRADICTED_CLAIM')
            if reviewed.response_status_appropriate is False or (complete != 'COMPLETE' and checked['status'] == 'ANSWERED'):
                failures.append('INCOMPLETE_OR_INAPPROPRIATE_ANSWER_STATUS')
            if reviewed.qualifications.outcome == 'MISSING' or reviewed.conflicts.outcome == 'MISSING':
                failures.append('MATERIAL_DISCLOSURE_OR_CONFLICT_MISSING')
        else:
            result['review_reasons'].append('INDEPENDENT_QUALIFIED_HUMAN_ASSESSMENT_REQUIRED')
        if any(c.outcome not in {'SUPPORTED'} for c in reviewed.claims):
            result['review_reasons'].append('UNRESOLVED_CLAIM_SUPPORT')
        if (reviewed.qualifications.outcome != 'SATISFIED' or reviewed.conflicts.outcome != 'SATISFIED'
                or reviewed.response_status_appropriate is not True or complete == 'INDETERMINATE'):
            result['review_reasons'].append('UNRESOLVED_COMPLETENESS_OR_DISCLOSURES')
    else:
        result['independent_human_acceptance'] = False
        result['review_reasons'].append('NO_INDEPENDENT_SEMANTIC_OR_COMPLETENESS_ASSESSMENT')
    if ('UNDETERMINED' in qualification['status'] and result['material_qualifications'] != 'SATISFIED'):
        result['review_reasons'].append('QUALIFICATION_APPLICABILITY_UNDETERMINED')
    result['diagnoses'] = failures
    result['overall_status'] = ('VALIDATION_FAILED' if failures else 'REVIEW_REQUIRED'
                                if result['review_reasons'] else 'VALIDATED')
    result['fully_validated'] = result['overall_status'] == 'VALIDATED'
    return result


class PostGenerationValidator:
    """Native successor. Historical validator module and results remain unchanged."""
    version = VERSION
    evaluate = staticmethod(evaluate_dimensions)
    def __init__(self, evidence_service, *, assessor=None, layout_reviews=()):
        from tools.generation.qualifications import QualificationValidator
        self.qualifications = QualificationValidator(evidence_service)
        self.service, self.assessor, self.layout_reviews = evidence_service, assessor, layout_reviews

    def validate(self, response, package, original_m7_result, *, question, request_binding):
        before = digest(response), digest(package), digest(original_m7_result)
        try:
            # Source authority and exact request binding precede semantic review.
            if self.service.validate(package, original_m7_result) is not True:
                raise ArtifactError('M8_VALIDATION_NOT_CONFIRMED')
            from tools.retrieval.contract import parameters
            cfg = original_m7_result['parameters']
            normalized, _ = parameters(question, original_m7_result['retrieval_mode'], cfg['top_k'],
                cfg['candidate_depth'], cfg['rrf_k'], cfg['filters'], self.service.inventory)
            if (hashlib.sha256(normalized.encode()).hexdigest() != original_m7_result['query_sha256']
                    or request_binding['M7_result_sha256'] != digest(original_m7_result)
                    or request_binding['M8_package_sha256'] != digest(package)
                    or request_binding['question_sha256'] != hashlib.sha256(question.encode()).hexdigest()
                    or not isinstance(request_binding['request_sha256'], str)
                    or not re.fullmatch(r'[0-9a-f]{64}', request_binding['request_sha256'])):
                raise ArtifactError('QUESTION_SOURCE_REQUEST_BINDING_MISMATCH')
        except (ValueError, TypeError, KeyError, OSError):
            return {'schema': self.version, 'overall_status': 'VALIDATION_FAILED', 'fully_validated': False,
                'structural_validation': 'NOT_RUN', 'citation_validity': 'FAIL',
                'source_integrity': 'FAIL', 'semantic_status': 'NOT_ASSESSED',
                'diagnoses': ['SOURCE_OR_REQUEST_INTEGRITY_FAILURE'], 'model_calls': 0}
        # Evaluate schema first so invalid responses return a dimensioned failure,
        # rather than running disclosure or assessor code with malformed objects.
        try:
            validate_response_shape(response, authorized_unit_ids={p['evidence']['unit_id'] for p in package['parents']})
        except (ValueError, TypeError):
            qualification = {'status': 'NOT_ASSESSED_INVALID_RESPONSE'}
        else:
            qualification = self.qualifications.validate(response, package, original_m7_result)
        assessment = None
        if self.assessor is not None and qualification['status'] != 'NOT_ASSESSED_INVALID_RESPONSE':
            assessment = self.assessor.assess(question=question, response=copy.deepcopy(response),
                package=copy.deepcopy(package), request_sha256=request_binding['request_sha256'])
        result = self.evaluate(response, package, question=question,
            request_sha256=request_binding['request_sha256'], qualification=qualification,
            assessment=assessment, layout_reviews=self.layout_reviews,
            human_review_qualified=type(self.assessor) is HumanReview)
        if type(self.assessor) is HumanReview:
            result['review_provenance'] = self.assessor.provenance
        self.service.check()
        if before != (digest(response), digest(package), digest(original_m7_result)):
            raise ArtifactError('INPUT_MUTATION_DETECTED')
        return result | {'source_integrity': 'LIVE_M8_VALIDATED'}
