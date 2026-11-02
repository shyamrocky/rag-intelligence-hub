"""Local owner enablement and concise read-only chat stop messages."""
from pathlib import Path

import streamlit as st

from tools.quality_dashboard.artifacts import ArtifactError

ROOT = Path(__file__).resolve().parents[2]


def state(root=None):
    """Read-only readiness for normal Chat; never renders or issues an approval."""
    from tools.bot_runtime.trust import verify_implementation
    from tools.generation_runner.bot_chat import budget_state, send_policy
    from tools.generation_runner.trust import load_trust
    root = root or ROOT
    try:
        ref = verify_implementation(root)
        _, policy, _ = load_trust(root, ref['path'], ref['sha256'])
        settings = send_policy(policy)
        value = {'enabled': True, 'settings': settings, 'budget': None, 'blocked': False}
        try:
            value['budget'] = budget_state(root, settings)
        except (ArtifactError, OSError, ValueError, KeyError, TypeError):
            value['blocked'] = True
        return value
    except (ArtifactError, OSError, ValueError, KeyError, TypeError):
        return {'enabled': False, 'settings': None, 'budget': None, 'blocked': True}


def controls():
    """No provider action; only explicit, separately confirmed enable/disable writes."""
    from tools.bot_runtime.trust import verify_implementation
    from tools.generation_runner.bot_chat import (
        DISCLOSURE,
        SEND_AUTHORITY,
        active,
        budget_state,
        config,
        enable,
    )
    from tools.generation_runner.trust import load_trust
    try:
        ref = verify_implementation(ROOT)
        _, policy, _ = load_trust(ROOT, ref['path'], ref['sha256'])
        settings = config(policy)
        if settings.get('send_authorization') == SEND_AUTHORITY:
            st.info('Normal Chat is ready by default. Return to Chat and Send to process one question within the configured limits. The exact-request controls below are optional troubleshooting tools.')
            return True
        owner = active(ROOT, policy=policy, trust_ref=ref)
    except (ArtifactError, OSError, ValueError, KeyError, TypeError):
        st.info('Live chat is off or its configuration needs review. Local preparation and offline simulation remain available.')
        return False
    local = True
    try:
        from tools.human_review.local_poc import require_localhost
        require_localhost()
    except (ArtifactError, ValueError, TypeError):
        local = False
    if owner:
        st.success('Live chat enabled · Send prepares and generates one grounded answer.')
        st.caption(DISCLOSURE)
        try:
            state = budget_state(ROOT, settings)
            st.caption(f"Per question: \\${settings['per_question_cap_usd']} · Total Bot cap: \\${settings['total_bot_cap_usd']} · Remaining after reservations: \\${state['remaining_usd']}")
        except (ArtifactError, ValueError, KeyError, OSError):
            st.warning('New paid requests are blocked by the spending or execution-history checks. Existing records remain available.')
        if st.button('Turn off live chat', disabled=not local):
            enable(ROOT, owner_statement='Owner explicitly clicked Turn off live chat.', confirmed=True, enabled=False)
            st.rerun()
    else:
        with st.expander('Enable live chat — owner approval required'):
            st.write(f"Maximum \\${settings['per_question_cap_usd']} per question · \\${settings['total_bot_cap_usd']} total Bot cap. Existing Bot reservations count toward this cap; New chat does not reset it.")
            st.write(DISCLOSURE)
            with st.form('bot-chat-enable'):
                statement = st.text_area('Your live-chat approval statement')
                confirmed = st.checkbox('I enable live chat and authorize Send to process each submitted question within these evidence-transfer and spending limits.')
                submit = st.form_submit_button('Enable live chat', disabled=not local)
            if submit:
                try:
                    from tools.human_review.local_poc import require_localhost
                    require_localhost()
                    enable(ROOT, owner_statement=statement, confirmed=confirmed)
                    st.rerun()
                except (ArtifactError, ValueError, KeyError, OSError, TypeError):
                    st.error('Live chat was not enabled. Explicit approval and valid configuration/budget are required.')
    return bool(owner)


def show_finding(value):
    if value and value.get('finding'):
        issue = value['finding']
        st.warning(issue['message'])
        attempted = issue.get('generation_attempted')
        st.caption('Generation attempted: '+('Unknown' if attempted is None else 'Yes' if attempted else 'No')+
                   ' · Cost status: '+issue.get('cost_status', 'UNKNOWN').replace('_', ' ').title())
        with st.expander('Technical details — stop reason'):
            st.json(issue)
