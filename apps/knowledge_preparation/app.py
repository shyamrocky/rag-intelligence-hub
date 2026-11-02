"""RAG Bot foundation and isolated knowledge workspace (localhost:8516)."""

import streamlit as st

SECTIONS = {
    "Sources": (":material/description:", "Inspect source identities, permissions and publications."),
    "Parsing & Evidence": (":material/account_tree:", "Follow parsed structure, normalized sections and evidence units."),
    "Chunks & Lineage": (":material/schema:", "Explore retrieval chunks and their authoritative parent relationships."),
    "Embeddings & Indexes": (":material/database:", "Inspect embedding and index publications and their source bindings."),
    "Validation & Publications": (":material/verified:", "Review integrity findings and versioned publication history."),
}

STYLE = """
<style>
:root {
    --knowledge-font:-apple-system,BlinkMacSystemFont,"SF Pro Text",
        "Helvetica Neue","Segoe UI",sans-serif;
}
[data-testid="stAppViewContainer"] {
    background:#fff;color:#1d1d1f;
    font-family:var(--knowledge-font);
    -webkit-font-smoothing:antialiased;
}
[data-testid="stMarkdownContainer"], [data-testid="stMetric"],
[data-testid="stSidebarNav"],
[data-testid="stAppViewContainer"] :is(h1,h2,h3,h4,p,label,input,button),
[data-testid="stMetricValue"] > div {
    font-family:var(--knowledge-font)!important;
    font-optical-sizing:auto;
}
[data-testid="stAppViewContainer"] p {letter-spacing:-.012em;}
[data-testid="stSidebarNav"] a p {font-weight:450;letter-spacing:-.015em;}
[data-testid="stSidebar"] {background:#f3f5f8;border-right:1px solid #e3e7ee;}
.block-container {max-width:1380px;padding:3.5rem 3.5rem 2rem;}
h1 {font-size:clamp(2.2rem,3.5vw,3.5rem)!important;letter-spacing:-.045em;
    line-height:1.08!important;font-weight:650!important;color:#1d1d1f;}
h2,h3 {letter-spacing:-.025em;font-weight:600!important;color:#1d1d1f;}
h3 {font-size:1.3rem!important;}
[data-testid="stCaptionContainer"] {color:#62626a;line-height:1.55;}
[data-testid="stMetricValue"] {font-size:2.6rem;font-weight:500;letter-spacing:-.04em;}
[data-testid="stMetricLabel"] {color:#515158;font-size:.9rem;}
.st-key-kp-chunk-metrics [data-testid="stMetric"] {
    background:#fff;border-radius:14px;padding:1.1rem;text-align:center;
}
.st-key-kp-chunk-metrics [data-testid="stMetricLabel"] {
    display:flex;justify-content:center;text-align:center;width:100%;
}
.st-key-kp-chunk-metrics [data-testid="stMetricLabel"] p {text-align:center;}
.st-key-kp-chunk-metrics [data-testid="stMetricValue"] {text-align:center;}
.st-key-kp-embedding-metrics [data-testid="stMetric"] {
    background:#fff;border-radius:14px;padding:1.1rem;text-align:center;
}
.st-key-kp-embedding-metrics [data-testid="stMetricLabel"] {
    display:flex;justify-content:center;text-align:center;width:100%;
}
.st-key-kp-embedding-metrics [data-testid="stMetricLabel"] p {text-align:center;}
.st-key-kp-embedding-metrics [data-testid="stMetricValue"] {text-align:center;}
hr {border-color:#e8e8ed;}
.st-key-preparation-metrics [data-testid="stVerticalBlockBorderWrapper"] {
    background:#f5f5f7;border-color:transparent!important;border-radius:16px;
}
.st-key-preparation-metrics [data-testid="stColumn"]:nth-child(1)
    [data-testid="stVerticalBlockBorderWrapper"] {background:#edf3fa;}
.st-key-preparation-metrics [data-testid="stColumn"]:nth-child(2)
    [data-testid="stVerticalBlockBorderWrapper"] {background:#edf5f1;}
.st-key-preparation-metrics [data-testid="stColumn"]:nth-child(3)
    [data-testid="stVerticalBlockBorderWrapper"] {background:#f2eff8;}
.st-key-preparation-metrics [data-testid="stColumn"]:nth-child(4)
    [data-testid="stVerticalBlockBorderWrapper"] {background:#f8f3eb;}
.st-key-preparation-pipeline {background:#f3f6f9;border-radius:16px;}
.st-key-preparation-pipeline [data-testid="stCaptionContainer"] {font-size:.85rem;}
.stApp:has(.st-key-kp-overview),
[data-testid="stAppViewContainer"]:has(.st-key-kp-overview) {background:#f5f5f7;}
.st-key-kp-overview h2,.st-key-kp-overview h3 {font-weight:650!important;}
.st-key-kp-overview .st-key-preparation-pipeline,
.st-key-kp-overview .st-key-kp-source-scope,
.st-key-kp-overview .st-key-kp-source-breakdown,
.st-key-kp-overview .st-key-kp-source-inventory {
    background:#fff;border:1px solid #e8e8ed;border-radius:16px;padding:1.5rem;
}
.st-key-kp-overview .st-key-preparation-metrics [class*="st-key-kp-metric-"] {
    background:#fff;border:1px solid #e8e8ed;border-radius:14px;padding:1.2rem;
    min-height:11rem;
}
.st-key-preparation-metrics [data-testid="stColumn"] > div {height:100%;}
.st-key-kp-overview .st-key-preparation-pipeline a {color:#244a68;}
.st-key-kp-overview .st-key-preparation-pipeline a p {
    white-space:normal!important;overflow:visible!important;text-overflow:clip!important;
}
/* Compact overview only; keep native navigation and detail-page layouts intact. */
.st-key-kp-overview {gap:.75rem;}
.st-key-kp-overview h1 {padding-bottom:.35rem;}
.st-key-kp-overview :is(h2,h3) {padding-top:0;padding-bottom:.25rem;}
.st-key-kp-overview :is(.st-key-preparation-pipeline,.st-key-kp-source-scope,
    .st-key-kp-source-breakdown,.st-key-kp-source-inventory) {
    padding:1rem 1.2rem;gap:.5rem;
}
.st-key-kp-overview hr {margin:.65rem 0;}
/* Keep toolbar clearance; tighten the breadcrumb-to-title transition on all pages. */
[data-testid="stAppViewContainer"]
    .block-container > [data-testid="stVerticalBlock"] {gap:.5rem;}
[data-testid="stAppViewContainer"] h1 {
    padding-top:0;margin-top:0;padding-bottom:.35rem;
}
.st-key-kp-breadcrumb {margin-bottom:0;padding-bottom:0;}
:is(.st-key-kp-sources-page,.st-key-kp-parse-page,.st-key-kp-evidence-flow) {gap:.65rem;}
:is(.st-key-kp-sources-page,.st-key-kp-parse-page,.st-key-kp-evidence-flow) h1 {padding-bottom:.35rem;}
:is(.st-key-kp-sources-page,.st-key-kp-parse-page,.st-key-kp-evidence-flow) :is(h2,h3) {padding-top:0;padding-bottom:.25rem;}
:is(.st-key-kp-sources-page,.st-key-kp-parse-page,.st-key-kp-evidence-flow) [data-testid="stVerticalBlock"] {gap:.5rem;}
:is(.st-key-kp-sources-page,.st-key-kp-parse-page,.st-key-kp-evidence-flow) [data-testid="stLinkButton"] {margin-top:.35rem;}
:is(.st-key-kp-sources-page,.st-key-kp-parse-page,.st-key-kp-evidence-flow) [data-testid="stDataFrame"] {margin-top:.35rem;}
.st-key-kp-pipeline-stages [data-testid="stColumn"] {
    padding:0 .65rem;
}
.st-key-kp-pipeline-stages [data-testid="stColumn"] + [data-testid="stColumn"] {
    border-left:1px solid #e8e8ed;
}
.st-key-kp-pipeline-stages [class*="st-key-kp-stage-"] {gap:.45rem;}
.st-key-kp-pipeline-stages [class*="st-key-kp-stage-"] > :first-child {
    text-align:center;
}
.st-key-kp-pipeline-stages [data-testid="stPageLink"] a {
    justify-content:center;text-align:center;min-height:3rem;
}
.st-key-preview-notice p {font-size:.85rem;color:#62626a;}
[data-testid="stSidebarNav"] a {border-radius:9px;padding-top:.65rem;padding-bottom:.65rem;}
[data-testid="stSidebarNav"] a p {
    font-size:1.08rem!important;line-height:1.5;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {background:#e4edf6;color:#244a68;}
.st-key-kp-sidebar-navigation [data-testid="stPageLink"] p {
    font-size:1.08rem!important;line-height:1.5;white-space:normal;
}
.st-key-kp-sidebar-stages {padding-left:.5rem;}

button:focus-visible,a:focus-visible,input:focus-visible {
    outline:2px solid #0066cc!important;outline-offset:3px;
}
@media(max-width:800px) {.block-container {padding:3.5rem 1rem 1.5rem;}}
@media(max-width:640px) {
    .st-key-kp-pipeline-stages [data-testid="stColumn"] + [data-testid="stColumn"] {
        border-left:0;border-top:1px solid #e8e8ed;padding-top:.65rem;
    }
}
</style>
"""


WORKSPACE_SECTIONS = {
    "Offline Retrieval Evaluation": (":material/analytics:", "offline-retrieval-evaluation",
        "Measure evidence discovery and delivery against human-approved benchmarks."),
    "Pre-Generation": (":material/checklist:", "pre-generation",
        "Prepare grounded prompts and verify model, context and cost readiness."),
    "Generation": (":material/chat_bubble_outline:", "generation",
        "Inspect model responses, token usage, cost and execution performance."),
    "Post-Generation Evaluation": (":material/fact_check:", "post-generation-evaluation-human-review",
        "Inspect evidence delivery, technical findings and review readiness."),
    "Human Review": (":material/rate_review:", "human-review",
        "Assess answer quality and record explicit owner decisions."),
}


def workspace_placeholder(title):
    if title == "Human Review":
        from apps.knowledge_preparation.human_review import render
        render()
        return
    if title == "Post-Generation Evaluation":
        from apps.knowledge_preparation.post_generation import render
        render()
        return
    if title == "Generation":
        from apps.knowledge_preparation.generation import render
        render()
        return
    if title == "Pre-Generation":
        from apps.knowledge_preparation.pre_generation import render
        render()
        return
    if title == "Offline Retrieval Evaluation":
        from apps.knowledge_preparation.offline_evaluation import render
        render()
        return
    st.title(title)
    st.write(WORKSPACE_SECTIONS[title][2])
    with st.container(border=True):
        st.subheader("Workspace preview")
        st.caption("Design placeholder · No data connected yet.")
        st.write("Existing capabilities will be connected separately. No execution controls are enabled.")


def rag_bot():
    from apps.knowledge_preparation.rag_bot import render
    render()


def overview():
    from apps.knowledge_preparation.views import render
    render("Knowledge Preparation")


def retrieval_overview():
    from apps.knowledge_preparation.retrieval import render
    render()

def section(title):
    from apps.knowledge_preparation.views import render
    if title in {"Sources", "Parse", "Normalize", "QA & Verified Evidence", "Parsing & Evidence"}:
        key = {"Sources": "kp-sources-page", "Parse": "kp-parse-page"}.get(title, "kp-evidence-flow")
        with st.container(key=key):
            render(title)
    else:
        render(title)


def main():
    st.set_page_config(page_title="RAG Intelligence Hub",
                       page_icon=":material/layers:", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("### :material/layers: RAG Intelligence Hub")
    pages = {
        "RAG Bot": [st.Page(rag_bot, title="RAG Bot", icon=":material/chat_bubble_outline:", default=True)],
        "Workspace": [st.Page(overview, title="Knowledge Preparation", icon=":material/layers:",
                              url_path="knowledge-preparation"),
                      st.Page(retrieval_overview, title="Knowledge Retrieval", icon=":material/search:",
                              url_path="knowledge-retrieval")],
        "Knowledge": [st.Page(lambda title=title: section(title), title=title, icon=icon,
                              url_path=title.lower().replace(" & ", "-").replace(" ", "-"))
                      for title, (icon, _) in SECTIONS.items()],
    }
    pages["Workspace"].extend(
        st.Page(lambda title=title: workspace_placeholder(title), title=title, icon=icon, url_path=path)
        for title, (icon, path, _) in WORKSPACE_SECTIONS.items()
    )
    # Direct process-stage links reuse the same native readers and legacy detail routes.
    for title, path in [("Parse", "parse"), ("Normalize", "normalize"),
                        ("QA & Verified Evidence", "qa-evidence")]:
        pages["Knowledge"].append(st.Page(lambda title=title: section(title), title=title,
                                          url_path=path, visibility="hidden"))
    page = st.navigation(pages, position="hidden")
    st.session_state["kp_pages"] = {p.title: p for group in pages.values() for p in group}
    with st.sidebar, st.container(key="kp-sidebar-navigation"):
        st.caption("RAG BOT")
        st.page_link(pages["RAG Bot"][0], label="New chat", icon=":material/edit_square:")
        st.divider()
        st.caption("KNOWLEDGE WORKSPACE")
        st.page_link(pages["Workspace"][0], label="Knowledge Preparation", icon=":material/layers:")
        with st.expander("Preparation stages", expanded=page.title != "RAG Bot"), st.container(key="kp-sidebar-stages"):
            for destination in pages["Knowledge"]:
                if destination.title in SECTIONS:
                    st.page_link(destination, label=destination.title,
                                 icon=SECTIONS[destination.title][0])
        for destination in pages["Workspace"][1:]:
            icon = ":material/search:" if destination.title == "Knowledge Retrieval" else WORKSPACE_SECTIONS[destination.title][0]
            st.page_link(destination, label=destination.title, icon=icon)
    with st.sidebar:
        st.divider()
        st.link_button("Open Master Dashboard ↗", "http://127.0.0.1:8514/", width="stretch")
        st.caption("Local workspace · Port 8516")
        st.caption("Design preview · No saved chats" if page.title == "RAG Bot"
                   else "Saved artifacts. Review actions require explicit owner input."
                   if page.title == "Human Review"
                   else "Saved artifacts only. No pipeline execution controls.")
    if page.title == "RAG Bot":
        page.run()
        return
    # Leaving Bot drops display state, not execution records or duplicate claims.
    st.session_state.pop("bot-active-id", None)
    st.session_state.pop("bot-submission-id", None)
    with st.container(key="kp-breadcrumb"):
        breadcrumb, badge = st.columns([5, 1])
        if page.title == "Knowledge Retrieval" or page.title in WORKSPACE_SECTIONS:
            breadcrumb.caption(f"Workspace / {page.title}")
            badge.caption("◦ Saved findings & review" if page.title == "Human Review" else "◦ Saved measurements")
        else:
            breadcrumb.caption(f"Workspace / [Knowledge Preparation](/knowledge-preparation) / {page.title}")
            badge.caption("◦ Knowledge workspace")
    page.run()
    st.divider()
    st.caption("Saved findings · Explicit owner review only · No generation controls"
               if page.title == "Human Review"
               else "Read-only knowledge workspace · No pipeline actions available")


if __name__ == "__main__":
    main()
