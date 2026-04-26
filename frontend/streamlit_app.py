from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from app.core.config import get_settings

import os
from tempfile import NamedTemporaryFile

import streamlit.components.v1 as components
import pandas as pd
import streamlit as st
import logging

from app.services.api_client import BackendApiClient
from app.services.document_parser import DocumentParser

from app.core.logging import configure_logging

configure_logging()

logger = logging.getLogger(__name__)
logger.info("Streamlit UI initialized")


st.set_page_config(
    page_title="Talent Scouting Agent",
    layout="wide",
)

settings = get_settings()
api_client = BackendApiClient(settings.backend_api_url)
document_parser = DocumentParser()

if "shortlist_result" not in st.session_state:
    st.session_state["shortlist_result"] = None

st.title("Talent Scouting & Engagement Agent")
st.caption("Recruiter decision-support workflow for explainable candidate shortlisting")

with st.sidebar:
    st.subheader("System")
    st.write("Backend: FastAPI")
    st.write("Frontend: Streamlit")
    st.write("Storage: SQLite")
    st.write(f"Dataset path: `{os.getenv('RESUME_DATA_PATH', settings.resume_data_path)}`")
    st.write("Retrieval: Azure AI Search")
    st.write("LLM: Gemini")
    try:
        dataset = api_client.dataset_summary()
        health = api_client.healthcheck()
        search_index = api_client.search_index_status()
    except Exception:
        dataset = None
        health = None
        search_index = None
    st.write(f"API URL: `{settings.backend_api_url}`")
    st.write(f"API Health: `{health['status'] if health else 'unreachable'}`")
    if dataset:
        st.subheader("Dataset")
        st.write(f"Candidates: `{dataset['total_candidates']}`")
        st.write("Top skills:")
        st.write(", ".join(dataset["top_skills"][:8]))
    if search_index:
        st.subheader("Search Index")
        st.write(f"Backend: `{search_index['backend']}`")
        st.write(f"Configured: `{search_index['configured']}`")
        st.write(f"Ready: `{search_index['ready']}`")
        st.write(f"Documents: `{search_index['document_count']}`")
        st.caption(search_index["message"])
        if st.button("Sync Search Index", use_container_width=True):
            with st.spinner("Building embeddings and syncing search index..."):
                try:
                    sync = api_client.sync_search_index()
                    st.success(sync["status"]["message"])
                except Exception as exc:
                    logger.exception("Search index sync failed")
                    st.error(f"Search index sync failed: {exc}")

input_mode = st.segmented_control(
    "Input Mode",
    options=["Paste JD", "Upload JD File"],
    default="Paste JD",
)

jd_text = ""
uploaded_file = None
if input_mode == "Paste JD":
    jd_text = st.text_area(
        "Job Description",
        height=280,
        placeholder="Paste the job description here...",
    )
else:
    uploaded_file = st.file_uploader(
        "Upload JD",
        type=["txt", "md", "pdf"],
        accept_multiple_files=False,
    )

run = st.button("Generate Shortlist", type="primary", use_container_width=True)

if run:
    with st.spinner("Generating shortlist and evaluating candidates..."):
        try:
            if input_mode == "Paste JD":
                if not jd_text.strip():
                    st.error("Add a job description first.")
                    st.stop()
                jd_payload = jd_text
            else:
                if uploaded_file is None:
                    st.error("Upload a JD file first.")
                    st.stop()

                suffix = os.path.splitext(uploaded_file.name)[1]

                with NamedTemporaryFile(delete=False, suffix=suffix) as temp:
                    temp.write(uploaded_file.getbuffer())
                    temp_path = temp.name

                jd_payload = document_parser.parse(temp_path)

            result = api_client.create_shortlist(jd_payload)

            st.session_state["shortlist_result"] = result

        except Exception as exc:
            logger.exception("Shortlist generation failed")

            error_message = str(exc)

            if "429" in error_message or "Too Many Requests" in error_message:
                st.warning(
                    "AI evaluation service is temporarily busy. Please retry in a few seconds."
                )
            elif "502" in error_message:
                st.warning(
                    "Candidate evaluation service is temporarily unavailable. Please retry shortly."
                )
            else:
                st.error("Something went wrong while generating the shortlist.")

if st.session_state["shortlist_result"]:

    result = st.session_state["shortlist_result"]
    candidates = result.get("candidates", [])
                    
    top = candidates[0] if candidates else None
    summary_cols = st.columns(5)
    summary_cols[0].metric("Candidates Scanned", result["total_candidates_scanned"])
    summary_cols[1].metric("Retrieved", result["retrieval_candidates_considered"])
    summary_cols[2].metric("Final Shortlist", len(candidates))
    summary_cols[3].metric("Top Match", top["match_score"] if top else 0)
    summary_cols[4].metric("Top Interest", top["interest_score"] if top else 0)

    left, right = st.columns([1, 2])
    with left:
        st.subheader("Parsed JD")
        st.json(result["jd"])
        st.subheader("Pipeline")
        st.write(f"Retrieval backend: `{result['retrieval_backend']}`")
        st.write(f"Evaluation backend: `{result['llm_backend']}`")

    with right:
        st.subheader("Ranked Shortlist")
        frame = pd.DataFrame(
            [
                {
                    "Candidate": item["candidate_id"],
                    "Category": item["candidate_category"],
                    "Match Score": item["match_score"],
                    "Interest Score": item["interest_score"],
                    "Recommendation": item["recommendation"],
                }
                for item in candidates
            ]
        )
        st.dataframe(frame, use_container_width=True, hide_index=True)
        st.download_button(
            "Download Shortlist CSV",
            data=frame.to_csv(index=False).encode("utf-8"),
            file_name=f"shortlist_{result['request_id']}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.subheader("Candidate Detail")
    for item in candidates:
        with st.expander(f"{item['candidate_id']} | {item['recommendation']}", expanded=False):
            metric_cols = st.columns(3)
            metric_cols[0].metric("Match", item["match_score"])
            metric_cols[1].metric("Interest", item["interest_score"])
            metric_cols[2].metric("Retrieval", item["retrieval_score"])
            st.write("**Persona**")
            st.text_area(
                "Persona",
                value=item["persona_summary"],
                height=120,
                disabled=True,
                key=f"persona_{item['candidate_id']}",
            )

            st.write("**Simulated Conversation**")

            chat_html = f"""
            <div style="display:flex; flex-direction:column; gap:14px; padding-top:10px;">

                <div style="
                    background-color:#1e3a5f;
                    padding:14px;
                    border-radius:14px;
                    width:85%;
                    color:white;
                    box-shadow:0 2px 6px rgba(0,0,0,0.2);
                ">
                    <div style="font-size:12px; opacity:0.8; margin-bottom:6px;">
                        Recruiter
                    </div>
                    <div>
                        {item["simulated_outreach_message"]}
                    </div>
                </div>

                <div style="
                    background-color:#2b2b2b;
                    padding:14px;
                    border-radius:14px;
                    width:85%;
                    margin-left:auto;
                    color:white;
                    box-shadow:0 2px 6px rgba(0,0,0,0.2);
                ">
                    <div style="font-size:12px; opacity:0.8; margin-bottom:6px;">
                        Candidate
                    </div>
                    <div>
                        {item["simulated_candidate_response"]}
                    </div>
                </div>

            </div>
            """

            components.html(chat_html, height=320, scrolling=False)

            st.write("**Interest Reasoning**")
            if item["interest_reasoning"]:
                for reason in item["interest_reasoning"]:
                    st.write(f"- {reason}")
            else:
                st.write("No additional interest reasoning available.")

            st.write("**Why matched**")
            for reason in item["reasoning"]:
                st.write(f"- {reason}")
            st.write("**Risk flags**")
            if item["risk_flags"]:
                for flag in item["risk_flags"]:
                    st.write(f"- {flag}")
            else:
                st.write("No major risk flags detected.")
            st.write("**Score breakdown**")
            st.json(item["score_breakdown"])

st.divider()
st.subheader("Recent Results")
try:
    results = api_client.list_results()["items"]
except Exception:
    results = []

if results:
    recent = pd.DataFrame(results)
    st.dataframe(recent, use_container_width=True, hide_index=True)
else:
    st.info("No stored shortlist runs yet.")
