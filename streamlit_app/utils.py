import json
import re
import textwrap
import urllib.request
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from inference.hdfs_data import parse_event_sequence


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

