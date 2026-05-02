import os
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
os.environ.setdefault("CREWAI_STORAGE_DIR", str(PROJECT_ROOT / ".crewai_storage"))
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

import streamlit as st
import pandas as pd

from agents.crew_setup import DebugCrew
from inference.detector import HDFSAnomalyDetector, MODEL_OPTIONS
from inference.event_mapper import EventMapper
from inference.hdfs_data import TEMPLATES_PATH, get_hdfs_sample
from inference.incident_store import (
    build_incident_report,
    load_incident_history,
    save_incident_history,
)
from llm.llm_explainer import OllamaLLM
from streamlit_app.auth_view import render_auth_screen
from streamlit_app.styles import APP_CSS
from streamlit_app.utils import (
    clear_app_cache,
    compress_event_runs,
    event_manual_rows,
    event_positions,
    ollama_model_available,
    parse_event_ids,
    parse_uploaded_events,
    pdf_bytes_from_text,
    probability_value,
    rule_based_explanation,
    sample_from_events,
    timeline_rows,
)


MODEL_LABELS = {name: config["label"] for name, config in MODEL_OPTIONS.items()}


def render_dashboard_summary():
    history = load_incident_history(limit=200, user=st.session_state["user"])
    st.markdown('<div class="section-title">Operations Snapshot</div>', unsafe_allow_html=True)
    if history.empty:
        st.info("No incident history yet. Run a detection to populate your dashboard.")
        return

    anomaly_count = int((history["Prediction"] == "Anomaly").sum())
    normal_count = int((history["Prediction"] == "Normal").sum())
    high_count = int((history["Severity"] == "HIGH").sum())
    top_trigger = history["Trigger Event"].mode().iloc[0] if not history["Trigger Event"].empty else "N/A"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Analyses", len(history))
    col2.metric("Anomalies", anomaly_count)
    col3.metric("Normal", normal_count)
    col4.metric("High severity", high_count, f"Top trigger {top_trigger}")

    chart_left, chart_mid, chart_right = st.columns([1, 1, 1.2])
    with chart_left:
        st.caption("Prediction mix")
        st.bar_chart(history["Prediction"].value_counts())
    with chart_mid:
        st.caption("Severity mix")
        st.bar_chart(history["Severity"].value_counts())
    with chart_right:
        st.caption("Most frequent trigger events")
        st.bar_chart(history["Trigger Event"].value_counts().head(8))


def render_incident_history(container):
    history = load_incident_history(user=st.session_state["user"])
    with container:
        if not history.empty:
            with st.expander(
                f"Your Incident History ({len(history)} latest records)",
                expanded=False,
            ):
                st.dataframe(
                    history.drop(columns=["User"], errors="ignore"),
                    use_container_width=True,
                    hide_index=True,
                )


st.set_page_config(
    page_title="AI Incident Intelligence",
    page_icon="AI",
    layout="wide",
)

st.markdown(APP_CSS, unsafe_allow_html=True)

if "user" not in st.session_state:
    render_auth_screen()
    st.stop()

st.markdown(
    """
    <div class="hero-strip">
        <div class="eyebrow">Professional Error Detection Console</div>
        <h1>AI Incident Intelligence</h1>
        <p>Run trained anomaly detectors against HDFS event streams, inspect root-cause signals,
        compare model behavior, and preserve investigation history per operator.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

mapper = EventMapper(str(TEMPLATES_PATH))

with st.sidebar:
    st.markdown("### Account")
    st.write(f"Signed in as `{st.session_state['user']}`")
    account_col, cache_col = st.columns(2)
    with account_col:
        if st.button("Logout", use_container_width=True):
            st.session_state.pop("user", None)
            st.rerun()
    with cache_col:
        if st.button("Clear cache", use_container_width=True):
            clear_app_cache()
            st.success("Cache cleared.")
    st.divider()

page = st.radio(
    "Page",
    ["Detection Dashboard", "Event Mapping Manual"],
    horizontal=True,
    label_visibility="collapsed",
)

if page == "Event Mapping Manual":
    st.subheader("Event Mapping Manual")
    st.caption("Use this reference when entering manual event IDs or reading uploaded log sequences.")
    st.dataframe(event_manual_rows(mapper), use_container_width=True, hide_index=True)
    st.stop()

render_dashboard_summary()

with st.sidebar:
    st.header("Input Source")
    input_source = st.radio("Analyze", ["Dataset sample", "Manual events", "Upload file"])
    with st.form("analysis_form"):
        sample_pool = "Mixed"
        sample_index = 0
        manual_text = ""
        uploaded_file = None

        if input_source == "Dataset sample":
            sample_pool = st.selectbox("Sample pool", ["Mixed", "Anomaly", "Normal"])
            sample_index = st.number_input("Sample index", min_value=0, value=0, step=1)
        elif input_source == "Manual events":
            manual_text = st.text_input(
                "Event IDs",
                value="E5, E22, E11, E9, E3, E20",
                help="Use commas or spaces between event IDs, then press Enter or click Run Detection.",
            )
        else:
            uploaded_file = st.file_uploader("Upload CSV or log file", type=["csv", "log", "txt"])

        selected_model_label = st.selectbox(
            "Detector",
            list(MODEL_LABELS.values()),
            help="Models without exported artifacts use the trained RandomForest fallback.",
        )
        model_name = next(name for name, label in MODEL_LABELS.items() if label == selected_model_label)
        st.markdown("<div style='height: 14px'></div>", unsafe_allow_html=True)
        run_detection = st.form_submit_button(
            "Run Detection and Explain",
            type="primary",
            use_container_width=True,
        )

if input_source == "Manual events":
    events = parse_event_ids(manual_text)
    sample = sample_from_events(events, "Manual events", block_id="manual_sequence")
elif input_source == "Upload file":
    events, upload_mode, upload_error = parse_uploaded_events(uploaded_file)
    block_id = Path(uploaded_file.name).stem if uploaded_file else "uploaded_sequence"
    sample = sample_from_events(events, f"Upload file ({upload_mode})", block_id=block_id)
else:
    upload_error = ""
    sample = get_hdfs_sample(sample_pool, int(sample_index))

events = sample["events"]
compressed_events = compress_event_runs(events, mapper)

if not events:
    st.warning("No events found for the selected input source.")
if input_source == "Upload file" and upload_error:
    st.error(upload_error)

left, right = st.columns([1, 1])
with left:
    st.subheader("HDFS Input")
    st.write(f"Source: `{input_source}`")
    if input_source == "Dataset sample":
        st.write(f"Selected pool: `{sample_pool}`")
        st.write(f"Selected index: `{int(sample_index)}`")
    st.write(f"Block ID: `{sample['block_id']}`")
    st.write(f"Dataset label: `{sample['label']}`")
    st.write(f"Sequence length: `{len(events)}`")
with right:
    st.subheader("Event Sequence")
    st.caption("Compressed consecutive repeats so long runs like E3 do not hide later events.")
    st.dataframe(compressed_events, use_container_width=True, hide_index=True)
    st.caption("Preview: first 20 and last 20 raw events.")
    preview = events[:20]
    if len(events) > 40:
        preview = events[:20] + ["..."] + events[-20:]
    st.code(", ".join(preview))

history_container = st.empty()
render_incident_history(history_container)

if run_detection and not events:
    if input_source == "Upload file" and upload_error:
        st.warning(upload_error)
    else:
        st.warning("Enter or upload at least one event ID before running detection.")

if run_detection and events:
    try:
        detector = HDFSAnomalyDetector(model_name=model_name)
        prediction = detector.predict(events)
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    mapped_event_rows = mapper.summarize_events(events)
    comparison = detector.compare_models(events)
    metrics = detector.metrics_table()
    contributors = detector.top_contributing_events(events, mapper=mapper)
    trigger = detector.likely_trigger(events, mapper=mapper)
    severity = detector.severity(prediction["anomaly_probability"], trigger=trigger)
    trigger_positions = event_positions(events, trigger["event_id"])
    mapped_events = [
        f"{row['Event ID']} repeated {row['Count']} time(s): {row['Template']}"
        for row in mapped_event_rows
    ]
    save_incident_history(
        {
            "User": st.session_state["user"],
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Block ID": sample["block_id"],
            "Sample Pool": sample_pool if input_source == "Dataset sample" else input_source,
            "Sample Index": int(sample_index) if input_source == "Dataset sample" else "",
            "Ground Truth": sample["label"],
            "Prediction": prediction["label"],
            "Probability": f"{prediction['anomaly_probability']:.2%}",
            "Severity": severity["level"],
            "Risk Score": severity["risk_score"],
            "Trigger Event": trigger["event_id"],
            "Model": model_name,
        }
    )
    render_incident_history(history_container)

    st.subheader("Model Detection")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Prediction", prediction["label"])
    col2.metric("Anomaly probability", f"{prediction['anomaly_probability']:.2%}")
    col3.metric("Ground truth", sample["label"])
    col4.metric("Severity", severity["level"], f"Risk {severity['risk_score']}/100")
    if prediction.get("fallback_reason"):
        st.info(prediction["fallback_reason"])

    if prediction["is_anomaly"]:
        st.error(
            f"Likely anomaly trigger: {trigger['event_id']} - {trigger['reason']} "
            f"(count: {trigger['count']}, contribution: {trigger['contribution_score']:.4f}, "
            f"positions: {trigger_positions[:12]}{' ...' if len(trigger_positions) > 12 else ''})"
        )
        st.code(trigger["template"])
    else:
        st.success("No high-risk anomaly trigger was found for this selected sample.")

    overview_tab, timeline_tab, compare_tab, metrics_tab, events_tab, llm_tab, report_tab = st.tabs(
        [
            "Overview",
            "Timeline",
            "Model Comparison",
            "Model Metrics",
            "Contributing Events",
            "Developer Debug Brief",
            "Report",
        ]
    )

    with overview_tab:
        st.subheader("Mapped Event Templates")
        overview_left, overview_right = st.columns([1.1, 0.9])
        with overview_left:
            st.dataframe(mapped_event_rows, use_container_width=True, hide_index=True)
        with overview_right:
            st.caption("Event frequency in selected sequence")
            event_counts = pd.DataFrame(mapped_event_rows)
            if not event_counts.empty:
                st.bar_chart(event_counts.set_index("Event ID")["Count"])

    with timeline_tab:
        st.subheader("Incident Timeline")
        timeline = timeline_rows(events, trigger["event_id"])
        timeline_left, timeline_right = st.columns([1.15, 0.85])
        with timeline_left:
            st.dataframe(timeline, use_container_width=True, hide_index=True)
        with timeline_right:
            st.caption("Timeline role distribution")
            st.bar_chart(timeline["Role"].value_counts())
        st.caption("Trigger and known high-risk events are marked so the sequence can be scanned quickly.")

    with compare_tab:
        st.subheader("Model Comparison")
        compare_left, compare_right = st.columns([1.2, 0.8])
        with compare_left:
            st.dataframe(comparison, use_container_width=True, hide_index=True)
        with compare_right:
            st.caption("Anomaly probability by detector")
            comparison_chart = comparison.copy()
            comparison_chart["Probability"] = comparison_chart["Anomaly Probability"].apply(probability_value)
            st.bar_chart(comparison_chart.set_index("Model")["Probability"])

    with metrics_tab:
        st.subheader("RandomForest Holdout Metrics")
        st.caption("Scores were produced when training on HDFS event-count features with an 80/20 stratified split.")
        metrics_left, metrics_right = st.columns([1.05, 0.95])
        with metrics_left:
            st.dataframe(metrics, use_container_width=True, hide_index=True)
        with metrics_right:
            st.caption("Metric scores")
            st.bar_chart(metrics.set_index("Metric")["Score"])

    with events_tab:
        st.subheader("Likely Anomaly Trigger")
        st.write(f"Event ID: `{trigger['event_id']}`")
        st.write(f"Trigger severity: `{trigger['severity']}`")
        st.write(f"Reason: {trigger['reason']}")
        st.write(f"Count in selected sequence: `{trigger['count']}`")
        st.write(f"Positions in full sequence: `{trigger_positions}`")
        st.write(f"Contribution score: `{trigger['contribution_score']:.4f}`")
        st.code(trigger["template"])

        st.subheader("Top Contributing Events")
        st.caption("Contribution score = event count in this sample x RandomForest feature importance.")
        contributors_left, contributors_right = st.columns([1.2, 0.8])
        with contributors_left:
            st.dataframe(
                contributors,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Model Importance": st.column_config.NumberColumn(format="%.4f"),
                    "Contribution Score": st.column_config.NumberColumn(format="%.4f"),
                },
            )
        with contributors_right:
            if not contributors.empty:
                st.caption("Top contribution scores")
                st.bar_chart(contributors.set_index("Event ID")["Contribution Score"])

    with llm_tab:
        st.subheader("Developer Debug Brief")
        result = "Developer debug brief was not generated."
        top_event_lines = [
            f"{row['Event ID']} contribution {row['Contribution Score']:.4f}: {row['Template']}"
            for row in contributors.to_dict("records")
        ]
        context = [
            f"Model prediction: {prediction['label']}",
            f"Anomaly probability: {prediction['anomaly_probability']:.2%}",
            f"Severity: {severity['level']} ({severity['risk_score']}/100)",
            f"Likely anomaly trigger: {trigger['event_id']} - {trigger['reason']}",
            f"Trigger template: {trigger['template']}",
            f"Dataset ground truth: {sample['label']}",
            f"Block ID: {sample['block_id']}",
            "Top contributing HDFS events:",
            *top_event_lines,
            "Mapped HDFS events:",
            *mapped_events,
        ]

        if not ollama_model_available("llama3"):
            result = rule_based_explanation(prediction, severity, trigger, contributors)
            st.markdown(result)
            st.info("Local Ollama llama3 is not available, so the app used the built-in explanation.")
        else:
            with st.spinner("CrewAI agents are analyzing the detected HDFS pattern..."):
                try:
                    llm = OllamaLLM(model="llama3")
                    crew = DebugCrew(llm=llm)
                    result = crew.run(context)
                    st.markdown(str(result))
                except Exception:
                    result = rule_based_explanation(prediction, severity, trigger, contributors)
                    st.markdown(result)
                    st.info("LLM explanation failed, so the app used the built-in explanation.")

    report_text = build_incident_report(
        sample=sample,
        sample_pool=sample_pool if input_source == "Dataset sample" else input_source,
        sample_index=int(sample_index) if input_source == "Dataset sample" else "",
        prediction=prediction,
        severity=severity,
        trigger=trigger,
        trigger_positions=trigger_positions,
        contributors=contributors,
        mapped_events=mapped_events,
        llm_result=result,
    )

    with report_tab:
        st.subheader("Incident Report")
        st.download_button(
            "Download TXT Report",
            data=report_text,
            file_name=f"incident_report_{sample['block_id']}.txt",
            mime="text/plain",
        )
        st.download_button(
            "Download PDF Report",
            data=pdf_bytes_from_text("AI Incident Intelligence Report", report_text),
            file_name=f"incident_report_{sample['block_id']}.pdf",
            mime="application/pdf",
        )
        st.text_area("Report Preview", report_text, height=500)
