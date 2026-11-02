"""Specific response rejection codes without Pydantic input values or source text."""
import re


class ResponseValidationError(ValueError):
    def __init__(self, code, *, path=(), issues=None):
        super().__init__(code)
        self.diagnostics = issues or [{'code': code, 'path': list(path)}]


RULES = {'claim_quote_reference_shape_inconsistent', 'blank_response_metadata',
         'abstention_requires_empty_answer_claims_and_missing_reason', 'answer_requires_text_and_claims',
         'partial_requires_missing_information', 'complete_status_conflicts_with_missing_information',
         'blank_or_duplicate_reference', 'blank_requirement', 'asserted_support_requires_references',
         'unsupported_requirement_cannot_assert_support', 'blank_conflict',
         'complete_answer_conflicts_with_coverage_declarations',
         'complete_answer_with_unresolved_reported_conflicts', 'abstention_conflicts_with_asserted_usable_support'}


def shape_error(error, value=None, allowed_ids=()):
    issues = []
    if hasattr(error, 'errors'):
        for item in error.errors(include_input=False, include_context=False, include_url=False):
            path = [p if type(p) is int or (type(p) is str and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', p))
                    else '<field>' for p in item['loc']]
            rule = item.get('msg', '').removeprefix('Value error, ')
            # These are owned validator rule names, never model/provider messages.
            if rule not in RULES:
                rule = 'schema_constraint_violation'
            issues.append({'code': 'SCHEMA_OR_RELATIONSHIP_INVALID', 'path': path, 'rule': rule})
    else:
        known = {'unauthorized_evidence_reference': 'UNAUTHORIZED_EVIDENCE_REFERENCE',
                 'example_reference_forbidden_in_live_response': 'EXAMPLE_REFERENCE_FORBIDDEN',
                 'explicit_authorized_unit_ids_required': 'AUTHORIZED_ID_SCOPE_REQUIRED'}
        issues.append({'code': known.get(str(error), 'RESPONSE_CONTRACT_INVALID'), 'path': []})
        if str(error) == 'unauthorized_evidence_reference' and isinstance(value, dict):
            issues = []
            for group in ['claims', 'requirement_coverage', 'conflicts_detected']:
                for i, item in enumerate(value.get(group, [])):
                    for j, unit in enumerate(item.get('evidence_unit_ids', [])):
                        if unit not in allowed_ids:
                            issues.append({'code': 'UNAUTHORIZED_EVIDENCE_REFERENCE',
                                           'path': [group, i, 'evidence_unit_ids', j]})
                    if group == 'claims':
                        for j, quote in enumerate(item.get('supporting_quotes', [])):
                            if quote['evidence_unit_id'] not in allowed_ids:
                                issues.append({'code': 'UNAUTHORIZED_EVIDENCE_REFERENCE',
                                               'path': [group, i, 'supporting_quotes', j, 'evidence_unit_id']})
    return ResponseValidationError('RESPONSE_CONTRACT_INVALID', issues=issues)
