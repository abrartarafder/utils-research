"""Utility Lens — a Canadian electricity utilities research workspace."""

import html
import os
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv

from research import ResearchSettings, export_pdf, friendly_error, run_research

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
st.set_page_config(page_title="Utility Lens · Canadian Utilities Research", page_icon="✳", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(f"<style>{(ROOT / 'assets/style.css').read_text()}</style>", unsafe_allow_html=True)


def markup(content: str):
    st.markdown(content, unsafe_allow_html=True)


def initialize():
    defaults = {"messages": [], "composer": "", "pending_prompt": None,
                "failed_prompt": None, "failure": None, "api_key_input": "",
                "model": os.getenv("OPENAI_MODEL", "gpt-4o"), "depth": "Quick brief",
                "web_search": True, "calculator": True}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def new_research():
    st.session_state.update(messages=[], composer="", pending_prompt=None,
                            failure=None, failed_prompt=None)


def set_example(question: str):
    st.session_state.composer = question


def queue_question(question: str):
    st.session_state.pending_prompt = question


def activity_label(event: dict) -> str:
    data = event["output"]
    if event["status"] == "error":
        return data.get("error", "Tool could not finish.")
    if event["tool"] == "search_tool":
        return f"Searched: {data.get('query', '')} · {len(data.get('results', []))} sources found"
    return f"Calculated: {data.get('expression', '')} = {data.get('result', '')}"


def show_activity(events: list[dict]):
    for event in events:
        st.markdown(f"{'✓' if event['status'] == 'complete' else '⚠'} {activity_label(event)}")


def source_cards(sources: list[dict]):
    if not sources:
        st.caption("No web sources were cited in this answer.")
        return
    columns = st.columns(2, gap="small")
    for index, source in enumerate(sources):
        with columns[index % 2]:
            url = source["url"]
            title = html.escape(" ".join(source.get("title", url).split()))
            domain = html.escape(urlparse(url).hostname or url)
            preview = " ".join(source.get("snippet", "").split())
            snippet = html.escape(preview[:180].rstrip() + ("…" if len(preview) > 180 else ""))
            # HTML avoids Markdown splitting a card when source text contains blank lines.
            st.html(f'<a class="source-card" href="{html.escape(url, quote=True)}" target="_blank" '
                    f'rel="noopener noreferrer"><span class="source-domain">{domain} <span>↗</span></span>'
                    f'<strong>{title}</strong><span class="source-snippet">{snippet}</span></a>')


def show_assistant(message: dict, index: int, is_latest: bool):
    payload = message["payload"]
    result = payload.get("result", {})
    with st.chat_message("assistant", avatar="✳"):
        markup('<div class="answer-label">UTILITY LENS UTILITIES RESEARCH BRIEF</div>')
        st.markdown(f"### {result.get('topic', 'Research brief')}")
        st.markdown(message["content"])
        findings = result.get("key_findings", [])
        if findings:
            with st.container(border=True):
                markup('<div class="eyebrow">KEY TAKEAWAYS</div>')
                for finding in findings:
                    st.markdown(f"- {finding}")
        tabs = st.tabs([f"Sources · {len(payload.get('source_details', []))}", "Research activity"])
        with tabs[0]:
            source_cards(payload.get("source_details", []))
        with tabs[1]:
            show_activity(payload.get("activity", []))
            st.caption(f"Completed in {payload.get('elapsed', 0):.1f}s")
        st.caption("Search previews may be incomplete. Open the sources to check the evidence.")
        if is_latest:
            questions = result.get("follow_up_questions", [])
            if questions:
                markup('<div class="eyebrow followup-label">KEEP EXPLORING</div>')
                for number, question in enumerate(questions[:3]):
                    st.button(question, key=f"followup_{index}_{number}",
                              on_click=queue_question, args=(question,), use_container_width=True)


def show_landing():
    markup('''<section class="welcome">
        <div class="welcome-kicker"><span class="tiny-star">✳</span> CANADIAN ELECTRICITY UTILITIES</div>
        <h1>Utilities research.<br><span>A Canadian perspective.</span></h1>
        <p>Explore Hydro One and Canada's electricity sector.<br>
        Understand grid investment, reliability, and regulation with linked sources.</p>
    </section>''')
    with st.container(border=True, key="question_box"):
        st.text_area("What would you like to research about Canadian utilities?", key="composer", height=115,
                     placeholder="Ask about Hydro One, grid reliability, or electricity regulation…",
                     label_visibility="collapsed", max_chars=6000)
        controls, action = st.columns([3, 1.35], vertical_alignment="center")
        with controls:
            st.segmented_control("Research depth", ["Quick brief", "Deep research"],
                                 key="depth", label_visibility="collapsed")
        with action:
            if st.button("Begin research  →", type="primary", use_container_width=True,
                         disabled=not st.session_state.composer.strip()):
                st.session_state.pending_prompt = st.session_state.composer
    markup('<div class="composer-hint">Public sources. Canadian context. A quick brief or a deeper dive.</div>')
    markup('<div class="eyebrow inspiration-label">NEED A STARTING POINT?</div>')
    examples = [
        ("↗", "Hydro One", "Explore grid investment",
         "Research Hydro One's latest publicly reported transmission and distribution investment priorities in Ontario. "
         "Explain timelines, reported costs, and intended reliability benefits using public utility reports and regulatory "
         "filings. State the reporting period and distinguish proposed plans from approved investments."),
        ("◎", "Reliability", "Compare utility reliability",
         "Compare Hydro One's distribution reliability with another Canadian electricity utility using the latest comparable "
         "published SAIDI and SAIFI data. Define the metrics, align reporting years and major-event exclusions, and explain "
         "any limits on the comparison. Identify missing data rather than estimating it."),
        ("≋", "Regulation", "Understand Ontario's grid",
         "Explain the distinct roles of Hydro One, the Ontario Energy Board (OEB), and the Independent Electricity System "
         "Operator (IESO) in Ontario's electricity sector. Use official sources and distinguish transmission, distribution, "
         "regulation, and system operation."),
    ]
    for column, (icon, category, title, question) in zip(st.columns(3, gap="medium"), examples):
        with column:
            with st.container(border=True):
                markup(f'<div class="example-icon">{icon}</div><div class="example-category">{category}</div>')
                st.button(f"{title}  ↗", key=f"example_{category}", use_container_width=True,
                          on_click=set_example, args=(question,))
    markup('''<div class="workflow-strip">
        <div><span>01</span><strong>Choose a utility topic</strong><small>Grid investment, reliability, or regulation</small></div>
        <div><span>02</span><strong>Explore public sources</strong><small>Utility reports and sector publications</small></div>
        <div><span>03</span><strong>Understand the findings</strong><small>Canadian context and linked evidence</small></div>
    </div>''')


initialize()
messages = st.session_state.messages

with st.sidebar:
    markup('<div class="brand"><span class="brand-symbol">✳</span> utility lens<span class="brand-dot">.</span></div>'
           '<div class="brand-caption">Canadian electricity utilities research</div>')
    st.button("＋  New research", key="new_research", type="primary", use_container_width=True, on_click=new_research)
    st.divider()
    markup('<div class="eyebrow recent-label">THIS CONVERSATION</div>')
    if messages:
        st.caption(f"{len(messages) // 2} questions explored")
    else:
        markup('<div class="empty-history">A fresh brief.<br>Start with a utility or a grid question.</div>')
    st.caption("Ask follow-ups to keep exploring the same topic.")
    with st.expander("Settings", icon=":material/tune:"):
        st.text_input("OpenAI API key", type="password", key="api_key_input",
                      placeholder="Use your key from .env, or enter one", help="Kept only in this browser session; never saved with conversations.")
        st.text_input("Model", key="model")
        st.toggle("Web search", key="web_search")
        st.toggle("Calculator", key="calculator")
        st.caption("Memory lasts for this browser session. Refreshing the page or starting new research clears it.")
    markup('<div class="sidebar-note"><span>✳</span><strong>Follow the grid.</strong>'
           '<p>From public utility reports<br>to a clearer understanding.</p></div>')
    st.caption("UTILITY LENS / CANADIAN UTILITIES RESEARCH")

api_key = st.session_state.api_key_input.strip() or os.getenv("OPENAI_API_KEY", "")
top_left, top_right = st.columns([3, 2], vertical_alignment="center")
with top_left:
    markup('<div class="workspace-title">Workspace <span>/</span> <strong>Canadian utilities</strong></div>')
with top_right:
    markup('<div class="workspace-status"><span class="status-dot"></span>'
           f'{"Ready to explore" if api_key else "Add an API key in Settings"}</div>')
st.divider()

if not api_key:
    st.info("Add your OpenAI API key in Settings to start research. You can explore the workspace first.")
if not messages:
    show_landing()
else:
    heading, download = st.columns([3, 1], vertical_alignment="center")
    with heading:
        markup('<div class="eyebrow">THE EXPLORATION CONTINUES</div>')
        st.markdown("## Your utilities research")
    with download:
        title = messages[0]["content"][:80]
        st.download_button("Download PDF", export_pdf(messages, title),
                           file_name="utility-lens-research.pdf", mime="application/pdf", use_container_width=True)
    for index, message in enumerate(messages):
        if message["role"] == "user":
            with st.chat_message("user", avatar=":material/person:"):
                st.markdown(message["content"])
        else:
            show_assistant(message, index, is_latest=index == len(messages) - 1)
    st.segmented_control("Research depth", ["Quick brief", "Deep research"], key="depth")
    prompt = st.chat_input("Ask a follow-up. Utility Lens remembers the conversation.", max_chars=6000)
    if prompt:
        st.session_state.pending_prompt = prompt

if st.session_state.failure:
    st.error(st.session_state.failure)
    if st.button("Retry research", key="retry"):
        st.session_state.pending_prompt = st.session_state.failed_prompt

question = st.session_state.pending_prompt
if question:
    st.session_state.pending_prompt = None
    settings = ResearchSettings(model=st.session_state.model,
                                depth=st.session_state.depth or "Quick brief",
                                web_search=st.session_state.web_search,
                                calculator=st.session_state.calculator)
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(question)
    with st.status("Exploring your question…", expanded=True) as status:
        try:
            run = run_research(question, messages, settings, api_key,
                               on_activity=lambda event: show_activity([event]))
            messages.extend([
                {"role": "user", "content": question},
                {"role": "assistant", "content": run["result"]["summary"], "payload": run},
            ])
            st.session_state.failure = None
            st.session_state.failed_prompt = None
            status.update(label="Research complete", state="complete", expanded=False)
        except Exception as exc:
            st.session_state.failure = friendly_error(exc)
            st.session_state.failed_prompt = question
            status.update(label="Research needs another try", state="error", expanded=False)
    st.rerun()
