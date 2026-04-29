import os
import hashlib
import json
import re
import secrets
import textwrap
import urllib.request
from datetime import datetime
from io import BytesIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
USERS_PATH = PROJECT_ROOT / "artifacts" / "users.json"
os.environ.setdefault("CREWAI_STORAGE_DIR", str(PROJECT_ROOT / ".crewai_storage"))
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

import streamlit as st
import pandas as pd

from agents.crew_setup import DebugCrew
from inference.detector import HDFSAnomalyDetector, MODEL_OPTIONS
from inference.event_mapper import EventMapper
from inference.hdfs_data import TEMPLATES_PATH, get_hdfs_sample, parse_event_sequence
from inference.incident_store import (
    build_incident_report,
    load_incident_history,
    save_incident_history,
)
from llm.llm_explainer import OllamaLLM


MODEL_LABELS = {name: config["label"] for name, config in MODEL_OPTIONS.items()}


def load_users():
    if not USERS_PATH.exists():
        return {}
    try:
        return json.loads(USERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_users(users):
    USERS_PATH.parent.mkdir(exist_ok=True)
    USERS_PATH.write_text(json.dumps(users, indent=2), encoding="utf-8")


def password_hash(password, salt):
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def create_user(username, password):
    username = username.strip().lower()
    if not username:
        return False, "Enter a username."
    if len(password) < 6:
        return False, "Use at least 6 characters for the password."

    users = load_users()
    if username in users:
        return False, "That username already exists."

    salt = secrets.token_hex(16)
    users[username] = {
        "salt": salt,
        "password_hash": password_hash(password, salt),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_users(users)
    return True, "Account created. You are signed in."


def verify_user(username, password):
    username = username.strip().lower()
    users = load_users()
    user = users.get(username)
    if not user:
        return False
    return secrets.compare_digest(
        user["password_hash"],
        password_hash(password, user["salt"]),
    )


def render_auth_screen():
    left, right = st.columns([1.05, 0.95], vertical_alignment="center")
    with left:
        st.markdown(
            """
            <div class="auth-hero">
                <div class="eyebrow">Incident Operations Console</div>
                <h1>Detect failures before they become outages.</h1>
                <p>Analyze HDFS event streams, compare trained detectors, isolate likely triggers,
                and keep each operator's investigation history separate.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="auth-panel">', unsafe_allow_html=True)
        auth_tab, signup_tab = st.tabs(["Login", "Sign up"])
        with auth_tab:
            with st.form("login_form"):
                username = st.text_input("Username", key="login_username")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
            if submitted:
                if verify_user(username, password):
                    st.session_state["user"] = username.strip().lower()
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
        with signup_tab:
            with st.form("signup_form"):
                username = st.text_input("Username", key="signup_username")
                password = st.text_input("Password", type="password", key="signup_password")
                confirm = st.text_input("Confirm password", type="password")
                submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if submitted:
                if password != confirm:
                    st.error("Passwords do not match.")
                else:
                    ok, message = create_user(username, password)
                    if ok:
                        st.session_state["user"] = username.strip().lower()
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        st.markdown("</div>", unsafe_allow_html=True)


def compress_event_runs(events, mapper):
    rows = []
    if not events:
        return rows

    start = 1
    current = events[0]
    count = 1
    for position, event_id in enumerate(events[1:], start=2):
        if event_id == current:
            count += 1
            continue

        rows.append(
            {
                "Start": start,
                "End": position - 1,
                "Event ID": current,
                "Repeat": count,
                "Template": mapper.get_template(current),
            }
        )
        start = position
        current = event_id
        count = 1

    rows.append(
        {
            "Start": start,
            "End": len(events),
            "Event ID": current,
            "Repeat": count,
            "Template": mapper.get_template(current),
        }
    )
    return rows


def event_positions(events, event_id):
    return [index + 1 for index, value in enumerate(events) if value == event_id]


def parse_event_ids(value):
    if not value:
        return []
    return re.findall(r"\bE\d+\b", value.upper())


def sample_from_events(events, source, label="Unknown", block_id="custom_sequence"):
    return {
        "block_id": block_id,
        "label": label,
        "binary_label": -1,
        "events": events,
        "latency": None,
        "sample_count": 1,
        "source": source,
    }


def parse_uploaded_events(uploaded_file):
    if uploaded_file is None:
        return [], "No file uploaded", "Upload a CSV, LOG, or TXT file before running detection."

    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in {".csv", ".log", ".txt"}:
        return [], "Unsupported file", "Unsupported file type. Please upload only .csv, .log, or .txt files."

    raw = uploaded_file.getvalue()
    text = raw.decode("utf-8", errors="ignore")
    if suffix == ".csv":
        df = pd.read_csv(BytesIO(raw))
        if "EventId" in df.columns:
            events = [str(value).strip().upper() for value in df["EventId"].dropna()]
            if events:
                return events, "EventId column", ""
        for column in ("Events", "Features"):
            if column in df.columns and not df.empty:
                events = parse_event_sequence(df.iloc[0][column])
                if events:
                    return events, column, ""
        return [], "CSV file", "No event IDs found. CSV must contain EventId, Events, or Features data."

    events = parse_event_ids(text)
    if not events:
        return [], "raw text scan", "No event IDs like E1, E2, or E20 were found in the uploaded file."
    return events, "raw text scan", ""


def rule_based_explanation(prediction, severity, trigger, contributors):
    lines = [
        f"The selected sequence is classified as {prediction['label']} with "
        f"{prediction['anomaly_probability']:.2%} anomaly probability.",
        f"Severity is {severity['level']} with risk score {severity['risk_score']}/100.",
    ]

    if trigger["event_id"] != "N/A":
        lines.append(
            f"The likely trigger is {trigger['event_id']}: {trigger['reason']} "
            f"It appears {trigger['count']} time(s)."
        )

    if not contributors.empty:
        top_rows = contributors.head(5).to_dict("records")
        summary = ", ".join(
            f"{row['Event ID']} count {row['Count']} contribution {row['Contribution Score']:.4f}"
            for row in top_rows
        )
        lines.append(f"Top model contributors: {summary}.")

    if prediction["is_anomaly"]:
        lines.append(
            "Recommended action: inspect the trigger template, verify block metadata state, "
            "check NameNode/DataNode consistency, and review replication or delete operations "
            "around the same block."
        )
    else:
        lines.append("Recommended action: continue monitoring; no high-risk trigger dominates this sample.")

    return "\n\n".join(lines)


def ollama_model_available(model_name="llama3"):
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return False
    names = {model.get("name", "").split(":")[0] for model in payload.get("models", [])}
    return model_name in names


def timeline_rows(events, trigger_event_id):
    high_risk_events = {
        "E4", "E7", "E8", "E10", "E12", "E14", "E17", "E20", "E24", "E28", "E29"
    }
    rows = []
    for index, event_id in enumerate(events, start=1):
        if event_id == trigger_event_id:
            role = "Trigger"
        elif event_id in high_risk_events:
            role = "High risk"
        else:
            role = "Normal"
        rows.append({"Position": index, "Event ID": event_id, "Role": role})
    return pd.DataFrame(rows)


def pdf_bytes_from_text(title, body):
    lines = [title, ""] + body.splitlines()
    wrapped = []
    for line in lines:
        wrapped.extend(textwrap.wrap(line, width=92) or [""])

    content = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
    for line in wrapped[:52]:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content.append(f"({escaped}) Tj")
        content.append("T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


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


def event_manual_rows(mapper):
    rows = []
    for event_id in sorted(mapper.templates, key=lambda value: int(value[1:])):
        rows.append(
            {
                "Number": int(event_id[1:]),
                "Event ID": event_id,
                "Mapped HDFS Event": mapper.get_template(event_id),
            }
        )
    return rows


def clear_app_cache():
    st.cache_data.clear()
    st.cache_resource.clear()


def probability_value(value):
    if isinstance(value, str):
        return float(value.strip().replace("%", "")) / 100
    return float(value)


st.set_page_config(
    page_title="AI Incident Intelligence",
    page_icon="AI",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --bg: #f4f7fb;
        --panel: #ffffff;
        --panel-soft: #eef3f8;
        --ink: #17212b;
        --muted: #647284;
        --line: #d8e0ea;
        --accent: #0e7c86;
        --accent-strong: #095f67;
        --danger: #b42318;
        --success: #067647;
    }

    .stApp {
        background:
            linear-gradient(180deg, rgba(14, 124, 134, 0.08), rgba(244, 247, 251, 0) 340px),
            var(--bg);
        color: var(--ink);
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    [data-testid="stHeader"] {
        background: rgba(244, 247, 251, 0.86);
        backdrop-filter: blur(10px);
    }

    [data-testid="stSidebar"] {
        background: #0f1d2b;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }

    [data-testid="stSidebar"] * {
        color: #f7fafc;
    }

    [data-testid="stSidebar"] [data-baseweb="select"] *,
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea {
        color: #17212b !important;
    }

    .block-container {
        max-width: 1280px;
        padding-top: 2.2rem;
        padding-bottom: 3rem;
    }

    h1 {
        color: #111827;
        font-weight: 800;
        letter-spacing: 0;
    }

    h2, h3 {
        color: #17212b;
        font-weight: 750;
        letter-spacing: 0;
    }

    .hero-strip {
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 22px 24px;
        background: linear-gradient(135deg, #ffffff 0%, #eef8f8 62%, #f7fafc 100%);
        box-shadow: 0 14px 36px rgba(18, 38, 63, 0.08);
        margin-bottom: 20px;
    }

    .hero-strip .eyebrow,
    .auth-hero .eyebrow {
        color: var(--accent-strong);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-weight: 800;
        margin-bottom: 8px;
    }

    .hero-strip p,
    .auth-hero p {
        color: var(--muted);
        max-width: 760px;
        margin-bottom: 0;
    }

    .section-title {
        color: #17212b;
        font-size: 1.18rem;
        font-weight: 750;
        margin: 20px 0 10px;
    }

    [data-testid="stMetric"] {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px 16px;
        box-shadow: 0 10px 28px rgba(18, 38, 63, 0.06);
    }

    div[data-testid="stTabs"] button {
        font-weight: 650;
    }

    .stDataFrame {
        border: 1px solid var(--line);
        border-radius: 8px;
        overflow: hidden;
        background: var(--panel);
    }

    .auth-hero {
        padding: 38px 8px;
    }

    .auth-hero h1 {
        font-size: clamp(2.1rem, 4vw, 4.2rem);
        line-height: 1.02;
        max-width: 760px;
        margin-bottom: 18px;
    }

    .auth-panel {
        background: rgba(255, 255, 255, 0.92);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 22px;
        box-shadow: 0 22px 60px rgba(18, 38, 63, 0.13);
    }

    .stButton > button,
    .stDownloadButton > button,
    button[kind="primary"] {
        border-radius: 8px;
        font-weight: 700;
    }

    .stButton > button[kind="primary"],
    .stDownloadButton > button[kind="primary"],
    button[kind="primary"] {
        background: var(--accent);
        border-color: var(--accent);
    }

    .stRadio [role="radiogroup"] {
        gap: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
            "LLM Explanation",
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
        st.subheader("LLM Root-Cause Explanation")
        result = "LLM explanation was not generated."
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
