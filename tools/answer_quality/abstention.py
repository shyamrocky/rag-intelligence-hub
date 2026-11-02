"""Application-owned abstention structure/display; never a semantic assessor.

Nonempty text can still be vague, false or unsupported. No string heuristic,
provider call, approval, source authorization or response mutation occurs here.
"""

VERSION = 'abstention-explanation-check-1.0'
LABEL = 'Unable to answer from available evidence'


def check_explanation(response):
    applicable = isinstance(response, dict) and response.get('status') == 'ABSTAINED'
    result = {'schema': VERSION, 'applicable': applicable,
              'structural_status': 'NOT_APPLICABLE', 'semantic_status': 'NOT_ASSESSED',
              'diagnoses': [], 'meaningfulness_verified': False,
              'factual_support_verified': False, 'citation_integrity_verified': False}
    if not applicable:
        return result
    values = response.get('missing_information')
    valid = (type(values) is list and bool(values)
             and all(type(v) is str and bool(v.strip()) for v in values))
    result.update(structural_status='PASS' if valid else 'FAIL',
                  semantic_status='REVIEW_REQUIRED',
                  diagnoses=[] if valid else ['ABSTENTION_EXPLANATION_MISSING_OR_INVALID'])
    return result


def render_response(st, response):
    """Presentation of model output only; old sealed responses remain unchanged."""
    if response.get('status') == 'ABSTAINED' and response.get('answer') == '':
        st.subheader(LABEL)
        st.caption('Model status: ABSTAINED · Explanation is model-reported; '
                   'grounding and adequacy require independent review.')
        if check_explanation(response)['structural_status'] == 'PASS':
            for reason in response['missing_information']:
                st.markdown(reason, unsafe_allow_html=False)
        else:
            st.warning('ABSTENTION_EXPLANATION_MISSING_OR_INVALID — no usable explanation '
                       'was supplied. This is distinct from citation integrity.')
    else:
        st.markdown(response.get('answer', ''), unsafe_allow_html=False)
