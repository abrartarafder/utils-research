"""Utility Lens — a Canadian electricity utilities research workspace."""

import base64
import html
import os
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv

from research import ResearchSettings, export_pdf, friendly_error, run_research

ROOT = Path(__file__).parent
EXAMPLE_QUESTION = "Who does what on Ontario’s electricity grid?"
TOPICS = (
    ("Grid investment", "electric_bolt",
     "Research Hydro One's latest publicly reported transmission and distribution investments in Ontario. "
     "Give timelines, costs and intended reliability benefits, and distinguish proposed from approved projects."),
    ("Grid reliability", "monitoring",
     "Compare Hydro One's distribution reliability with another Canadian electricity utility using the latest "
     "comparable SAIDI and SAIFI data. Explain the metrics, reporting periods and major-event exclusions."),
    ("Ontario’s grid", "hub", EXAMPLE_QUESTION),
    ("Regulation", "gavel",
     "Explain how the Ontario Energy Board reviews major electricity transmission projects and sets delivery "
     "rates. Use official sources and identify the steps where the public can participate."),
)
# City marker positions are percentages of the bundled Natural Earth map.
CITIES = {"Toronto": (64.0, 80.98), "Ottawa": (73.4, 69.74),
          "Sudbury": (58.9, 65.56), "Thunder Bay": (37.4, 54.9)}
ONTARIO_SOURCES = (
    ("Hydro One", "Transmission and distribution", "electric_bolt", "https://www.hydroone.com/about"),
    ("IESO", "Ontario’s electricity system operator", "hub", "https://www.ieso.ca/"),
    ("Ontario Energy Board", "Provincial energy regulator", "gavel", "https://www.oeb.ca/about-oeb/what-we-do"),
)

load_dotenv(ROOT / ".env")
st.set_page_config(page_title="Utility Lens · Ontario Electricity Research", page_icon="⚡", layout="wide")
st.html(ROOT / "assets/style.css")


def icon(name: str) -> str:
    return f'<span class="material-icon" aria-hidden="true">{name}</span>'


def initialize():
    defaults = {
        "messages": [], "pending_prompt": None, "failed_prompt": None, "failure": None,
        "api_key_input": "", "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
        "depth": "Quick brief", "web_search": True, "calculator": True, "research_city": "Toronto",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def new_research():
    st.session_state.update(messages=[], research_chat="", pending_prompt=None,
                            failure=None, failed_prompt=None)


def set_example(question: str):
    st.session_state.research_chat = question


def set_city_question():
    city = st.session_state.research_city
    set_example(f"What electricity utilities serve {city}, Ontario, and what grid investments are planned nearby? "
                "Use official sources and distinguish proposed, approved, and in-service projects.")


def queue_question(question: str):
    st.session_state.update(pending_prompt=question, failure=None, failed_prompt=None)


def submit_question():
    if question := st.session_state.research_chat.strip():
        queue_question(question)


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
            st.html(f'<a class="source-card" href="{html.escape(url, quote=True)}" target="_blank" '
                    f'rel="noopener noreferrer"><span class="source-domain">{domain} <span>↗</span></span>'
                    f'<strong>{title}</strong><span class="source-snippet">{snippet}</span></a>')


def show_user(question: str, *, example: bool = False):
    label = '<span class="example-label">Example question</span>' if example else ""
    st.html(f'<div class="user-message"><div><p>{html.escape(question)}</p>{label}</div>'
            f'<span class="avatar user-avatar">{icon("person")}</span></div>')


def show_assistant(message: dict, index: int, is_latest: bool):
    payload = message["payload"]
    result = payload.get("result", {})
    with st.chat_message("assistant", avatar=":material/bolt:"):
        st.markdown(f"### {result.get('topic', 'Research brief')}")
        st.markdown(message["content"])
        if findings := result.get("key_findings"):
            with st.container(border=True):
                st.markdown("**Key takeaways**")
                for finding in findings:
                    st.markdown(f"- {finding}")
        sources, activity = st.tabs([f"Sources · {len(payload.get('source_details', []))}", "Research activity"])
        with sources:
            source_cards(payload.get("source_details", []))
        with activity:
            show_activity(payload.get("activity", []))
            st.caption(f"Completed in {payload.get('elapsed', 0):.1f}s")
        if is_latest and (questions := result.get("follow_up_questions")):
            st.markdown("**Suggested follow-ups**")
            for number, question in enumerate(questions[:3]):
                st.button(question, key=f"followup_{index}_{number}",
                          on_click=queue_question, args=(question,), width="stretch")


def show_topbar():
    with st.container(key="topbar"):
        brand, controls = st.columns([3, 2], gap="small", vertical_alignment="center")
        with brand:
            st.html(f'<div class="brand">{icon("electric_bolt")}<span>Utility Lens</span>'
                    '<span class="brand-divider"></span><span class="brand-caption">Ontario research</span></div>')
        with controls, st.popover("Settings", icon=":material/tune:"):
            st.text_input("OpenAI API key", type="password", key="api_key_input",
                          placeholder="Use .env or enter a key", help="Kept in this browser session.")
            st.text_input("Model", key="model")
            st.segmented_control("Research depth", ["Quick brief", "Deep research"], key="depth")
            st.toggle("Web search", key="web_search")
            st.toggle("Calculator", key="calculator")
            st.button("New research", icon=":material/add:", on_click=new_research, width="stretch")


def show_intro():
    st.html('''<section class="welcome">
        <h1>Hi, how can I help with your <br><span>Ontario utility research</span> today?</h1>
        <p>Explore Ontario’s electricity grid, from infrastructure and reliability to regulation.</p>
    </section>''')
    with st.container(key="topic_cards"):
        for column, (label, symbol, question) in zip(st.columns(4, gap="small"), TOPICS):
            with column:
                st.button(label, icon=f":material/{symbol}:", on_click=set_example, args=(question,), width="stretch")


def show_example():
    show_user(EXAMPLE_QUESTION, example=True)
    st.html(f'''<div class="example-answer">
        <span class="avatar assistant-avatar">{icon("electric_bolt")}</span>
        <div class="example-bubble">
            <h2>Three organizations play different roles on Ontario’s grid.</h2>
            <p><a href="{ONTARIO_SOURCES[0][3]}" target="_blank" rel="noopener noreferrer">Hydro One</a>
                transmits electricity across Ontario and distributes it to homes and businesses in its service areas.</p>
            <div class="grid-roles">
                <div>{icon("hub")}<div><a href="{ONTARIO_SOURCES[1][3]}" target="_blank" rel="noopener noreferrer">IESO</a>
                    <span>Operates the provincial grid</span></div></div>
                <div>{icon("gavel")}<div><a href="{ONTARIO_SOURCES[2][3]}" target="_blank" rel="noopener noreferrer">Ontario Energy Board</a>
                    <span>Regulates the energy sector</span></div></div>
            </div>
            <p>Ask me how these roles affect a project, a utility, or a place on the map.</p>
        </div>
    </div>''')
    with st.container(key="example_action"):
        st.button("Ask this question", icon=":material/chat_bubble_outline:",
                  on_click=set_example, args=(EXAMPLE_QUESTION,))


def show_ontario():
    with st.container(key="map_card"):
        st.html(f'<h2 class="map-heading">{icon("map")}Ontario grid map</h2>')
        with st.container(key="map_body"):
            image = base64.b64encode((ROOT / "assets/ontario-map.webp").read_bytes()).decode()
            selected = st.session_state.research_city
            markers = "".join(
                f'<span class="map-city{" selected" if city == selected else ""}" '
                f'style="left:{x}%;top:{y}%">{city}</span>'
                for city, (x, y) in CITIES.items()
            )
            st.html(f'''<figure class="ontario-map" role="img"
                aria-label="Map of Ontario showing Thunder Bay, Sudbury, Toronto and Ottawa. {selected} is selected.">
                <img src="data:image/webp;base64,{image}" alt="">
                <span class="map-province" aria-hidden="true">ONTARIO</span>
                <span class="map-water" aria-hidden="true">Hudson Bay</span>
                <div aria-hidden="true">{markers}</div>
                <figcaption>Natural Earth</figcaption>
            </figure>''')
            st.selectbox("Research near", CITIES, key="research_city")
            st.button("Use location in chat", icon=":material/location_on:", key="map_prompt",
                      on_click=set_city_question, width="stretch")

    with st.container(key="reference_card"):
        links = "".join(
            f'<a class="reference-link" href="{url}" target="_blank" rel="noopener noreferrer">'
            f'{icon(symbol)}<span><strong>{name}</strong><small>{description}</small></span>{icon("open_in_new")}</a>'
            for name, description, symbol, url in ONTARIO_SOURCES
        )
        st.html(f'<section class="references"><h2>{icon("book_2")}Research sources</h2>{links}</section>')


def show_conversation(messages: list[dict]):
    question = st.session_state.pending_prompt
    if not (messages or question or st.session_state.failure):
        show_example()

    if messages:
        with st.container(key="conversation_tools"):
            st.download_button("Download PDF", export_pdf(messages, messages[0]["content"][:80]),
                               icon=":material/download:", file_name="utility-lens-research.pdf",
                               mime="application/pdf")
        for index, message in enumerate(messages):
            if message["role"] == "user":
                show_user(message["content"])
            else:
                show_assistant(message, index, is_latest=index == len(messages) - 1 and not question)

    if st.session_state.failure:
        show_user(st.session_state.failed_prompt)
        st.error(st.session_state.failure)
        st.button("Retry research", icon=":material/refresh:", on_click=queue_question,
                  args=(st.session_state.failed_prompt,))

    if question:
        st.session_state.pending_prompt = None
        show_user(question)
        settings = ResearchSettings(model=st.session_state.model,
                                    depth=st.session_state.depth or "Quick brief",
                                    web_search=st.session_state.web_search,
                                    calculator=st.session_state.calculator)
        api_key = st.session_state.api_key_input.strip() or os.getenv("OPENAI_API_KEY", "")
        with st.status("Exploring your question…", expanded=True):
            try:
                run = run_research(question, messages, settings, api_key,
                                   on_activity=lambda event: show_activity([event]))
                messages.extend([
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": run["result"]["summary"], "payload": run},
                ])
            except Exception as exc:
                st.session_state.update(failure=friendly_error(exc), failed_prompt=question)
        st.rerun()


initialize()
show_topbar()
with st.container(key="dashboard"):
    main, right = st.columns([2.15, 1], gap="medium")
    with main, st.container(key="research_workspace"):
        show_intro()
        with st.container(key="conversation"):
            show_conversation(st.session_state.messages)
        with st.container(key="composer"):
            st.chat_input("Type a message…", key="research_chat", max_chars=6000, on_submit=submit_question)
    with right, st.container(key="ontario_panel"):
        show_ontario()
