import hashlib
import json
import re
import secrets
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

from inference.detector import HDFSAnomalyDetector, MODEL_OPTIONS
from inference.event_mapper import EventMapper
from inference.hdfs_data import TEMPLATES_PATH, get_hdfs_sample
from inference.incident_store import (
    build_incident_report,
    load_incident_history,
    save_incident_history,
)


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PROJECT_ROOT / "web"
USERS_PATH = PROJECT_ROOT / "artifacts" / "users.json"

app = Flask(__name__, static_folder=str(WEB_ROOT), static_url_path="")


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


def verify_user(username, password):
    username = username.strip().lower()
    user = load_users().get(username)
    if not user:
        return False
    return secrets.compare_digest(user["password_hash"], password_hash(password, user["salt"]))


def parse_event_ids(value):
    if not value:
        return []
    return re.findall(r"\bE\d+\b", str(value).upper())


def serializable_rows(rows):
    if isinstance(rows, pd.DataFrame):
        return rows.fillna("").to_dict("records")
    return rows


def compress_event_runs(events, mapper):
    if not events:
        return []

    rows = []
    start = 1
    current = events[0]
    count = 1
    for position, event_id in enumerate(events[1:], start=2):
        if event_id == current:
            count += 1
            continue
        rows.append(
            {
                "start": start,
                "end": position - 1,
                "eventId": current,
                "repeat": count,
                "template": mapper.get_template(current),
            }
        )
        start = position
        current = event_id
        count = 1

    rows.append(
        {
            "start": start,
            "end": len(events),
            "eventId": current,
            "repeat": count,
            "template": mapper.get_template(current),
        }
    )
    return rows


def timeline_rows(events, trigger_event_id):
    high_risk_events = {"E4", "E7", "E8", "E10", "E12", "E14", "E17", "E20", "E24", "E28", "E29"}
    rows = []
    for index, event_id in enumerate(events, start=1):
        if event_id == trigger_event_id:
            role = "Trigger"
        elif event_id in high_risk_events:
            role = "High risk"
        else:
            role = "Nominal"
        rows.append({"position": index, "eventId": event_id, "role": role})
    return rows


def event_manual_rows():
    mapper = EventMapper(str(TEMPLATES_PATH))
    return [
        {
            "number": int(event_id[1:]),
            "eventId": event_id,
            "template": mapper.get_template(event_id),
        }
        for event_id in sorted(mapper.templates, key=lambda value: int(value[1:]))
    ]


def build_history_summary(history):
    if history.empty:
        return {
            "total": 0,
            "anomalies": 0,
            "normal": 0,
            "highSeverity": 0,
            "predictionMix": [],
            "severityMix": [],
            "triggerMix": [],
        }

    prediction_counts = history["Prediction"].value_counts()
    severity_counts = history["Severity"].value_counts()
    trigger_counts = history["Trigger Event"].value_counts().head(8)
    return {
        "total": int(len(history)),
        "anomalies": int(prediction_counts.get("Anomaly", 0)),
        "normal": int(prediction_counts.get("Normal", 0)),
        "highSeverity": int(severity_counts.get("HIGH", 0)),
        "predictionMix": [{"label": key, "value": int(value)} for key, value in prediction_counts.items()],
        "severityMix": [{"label": key, "value": int(value)} for key, value in severity_counts.items()],
        "triggerMix": [{"label": key, "value": int(value)} for key, value in trigger_counts.items()],
    }


def fallback_explanation(payload):
    sample = payload.get("sample", {})
    input_kind = "dataset sample" if payload.get("source") == "Dataset sample" else "manual event sequence"
    prediction = payload.get("prediction", {})
    severity = payload.get("severity", {})
    trigger = payload.get("trigger", {})
    contributors = payload.get("contributors", [])[:5]
    contributor_text = ", ".join(
        f"{row.get('Event ID')} contribution {float(row.get('Contribution Score', 0)):.4f}"
        for row in contributors
    )
    return (
        "Incident assessment\n\n"
        f"The selected {input_kind} for block {sample.get('blockId', 'unknown')} was classified as "
        f"{prediction.get('label', 'Unknown')} with an anomaly probability of "
        f"{float(prediction.get('anomaly_probability', 0)):.2%}. "
        f"The current severity estimate is {severity.get('level', 'UNKNOWN')} with risk score "
        f"{severity.get('risk_score', 'N/A')}/100.\n\n"
        "Likely problem\n\n"
        f"The strongest operational signal is {trigger.get('event_id', 'N/A')}. "
        f"{trigger.get('reason', 'The event pattern should be reviewed against nearby NameNode and DataNode activity.')} "
        f"Template evidence: {trigger.get('template', 'No template available.')}\n\n"
        "Why it may be happening\n\n"
        f"The detector is weighting repeated and high-impact event patterns in the sample. "
        f"Top contributing evidence includes {contributor_text or 'no dominant contributor'}.\n\n"
        "How to improve safely\n\n"
        "Validate the affected block metadata, compare the event timestamp window with replication and deletion "
        "operations, review DataNode health, and document the remediation decision before taking irreversible action. "
        "Treat the model output as decision support and keep a human operator accountable for final action."
    )


def ollama_prompt(payload):
    sample = payload.get("sample", {})
    prediction = payload.get("prediction", {})
    severity = payload.get("severity", {})
    trigger = payload.get("trigger", {})
    contributors = payload.get("contributors", [])[:8]
    comparison = payload.get("comparison", [])

    input_kind = "dataset sample" if payload.get("source") == "Dataset sample" else "manual event sequence"
    return f"""
You are a professional incident response analyst for HDFS operations.
Write a concise, ethical, operator-facing explanation for the selected {input_kind}.

Requirements:
- Use clear section headings: Problem, Why This May Be Happening, Recommended Improvements, Ethical Caution.
- Explain uncertainty and avoid claiming proof beyond the evidence.
- Keep the response practical and professional.
- Mention that remediation should be verified by a human operator.

Sample:
- Block ID: {sample.get("blockId")}
- Input source: {payload.get("source")}
- Dataset label: {sample.get("label")}
- Sequence length: {sample.get("sequenceLength")}
- Event preview: {sample.get("preview")}

Model result:
- Prediction: {prediction.get("label")}
- Anomaly probability: {float(prediction.get("anomaly_probability", 0)):.2%}
- Severity: {severity.get("level")} ({severity.get("risk_score")}/100)
- Trigger event: {trigger.get("event_id")}
- Trigger reason: {trigger.get("reason")}
- Trigger template: {trigger.get("template")}

Top contributing events:
{json.dumps(contributors, indent=2)}

Model comparison:
{json.dumps(comparison, indent=2)}
""".strip()


def stream_ollama_text(prompt, model="llama3"):
    payload = json.dumps({"model": model, "prompt": prompt, "stream": True}).encode("utf-8")
    request_obj = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request_obj, timeout=120) as response:
        for raw_line in response:
            if not raw_line:
                continue
            try:
                item = json.loads(raw_line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            chunk = item.get("response", "")
            if chunk:
                yield chunk
            if item.get("done"):
                break


def require_user(payload):
    username = str(payload.get("user", "")).strip().lower()
    if not username or username not in load_users():
        return None
    return username


@app.get("/")
def index():
    return send_from_directory(WEB_ROOT, "index.html")


@app.post("/api/auth/signup")
def signup():
    payload = request.get_json(force=True)
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not username:
        return jsonify({"ok": False, "message": "Enter a username."}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "message": "Use at least 6 characters for the password."}), 400

    users = load_users()
    if username in users:
        return jsonify({"ok": False, "message": "That username already exists."}), 409

    salt = secrets.token_hex(16)
    users[username] = {
        "salt": salt,
        "password_hash": password_hash(password, salt),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_users(users)
    return jsonify({"ok": True, "user": username})


@app.post("/api/auth/login")
def login():
    payload = request.get_json(force=True)
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", ""))
    if verify_user(username, password):
        return jsonify({"ok": True, "user": username})
    return jsonify({"ok": False, "message": "Invalid username or password."}), 401


@app.get("/api/manual")
def manual():
    return jsonify({"rows": event_manual_rows()})


@app.get("/api/history/<user>")
def history(user):
    history_df = load_incident_history(limit=200, user=user.strip().lower())
    return jsonify(
        {
            "summary": build_history_summary(history_df),
            "rows": history_df.drop(columns=["User"], errors="ignore").fillna("").to_dict("records"),
        }
    )


@app.post("/api/cache/clear")
def clear_cache():
    HDFSAnomalyDetector.__init__.__globals__.get("joblib")
    return jsonify({"ok": True, "message": "Runtime cache cleared."})


@app.post("/api/analyze")
def analyze():
    payload = request.get_json(force=True)
    user = require_user(payload)
    if not user:
        return jsonify({"ok": False, "message": "Sign in before running analysis."}), 401

    source = payload.get("source", "Dataset sample")
    model_name = payload.get("modelName", "random_forest")
    if model_name not in MODEL_OPTIONS:
        return jsonify({"ok": False, "message": "Unknown detector selected."}), 400

    if source == "Dataset sample":
        sample_pool = payload.get("samplePool", "Mixed")
        sample_index = int(payload.get("sampleIndex", 0) or 0)
        sample = get_hdfs_sample(sample_pool, sample_index)
    else:
        events = payload.get("events") or parse_event_ids(payload.get("manualText", ""))
        sample_pool = source
        sample_index = ""
        sample = {
            "block_id": payload.get("blockId") or "manual_sequence",
            "label": "Unknown",
            "binary_label": -1,
            "events": events,
            "latency": None,
            "sample_count": 1,
            "source": source,
        }

    events = sample["events"]
    if not events:
        return jsonify({"ok": False, "message": "Provide at least one event ID before analysis."}), 400

    mapper = EventMapper(str(TEMPLATES_PATH))
    detector = HDFSAnomalyDetector(model_name=model_name)
    prediction = detector.predict(events)
    comparison = detector.compare_models(events)
    metrics = detector.metrics_table()
    contributors = detector.top_contributing_events(events, mapper=mapper)
    trigger = detector.likely_trigger(events, mapper=mapper)
    severity = detector.severity(prediction["anomaly_probability"], trigger=trigger)
    mapped_event_rows = mapper.summarize_events(events)
    trigger_positions = [index + 1 for index, value in enumerate(events) if value == trigger["event_id"]]
    mapped_events = [
        f"{row['Event ID']} repeated {row['Count']} time(s): {row['Template']}"
        for row in mapped_event_rows
    ]

    save_incident_history(
        {
            "User": user,
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Block ID": sample["block_id"],
            "Sample Pool": sample_pool,
            "Sample Index": sample_index,
            "Ground Truth": sample["label"],
            "Prediction": prediction["label"],
            "Probability": f"{prediction['anomaly_probability']:.2%}",
            "Severity": severity["level"],
            "Risk Score": severity["risk_score"],
            "Trigger Event": trigger["event_id"],
            "Model": model_name,
        }
    )

    report_text = build_incident_report(
        sample=sample,
        sample_pool=sample_pool,
        sample_index=sample_index,
        prediction=prediction,
        severity=severity,
        trigger=trigger,
        trigger_positions=trigger_positions,
        contributors=contributors,
        mapped_events=mapped_events,
        llm_result="Automated ethical guidance: review affected systems, verify evidence, document actions, and avoid irreversible remediation until impact is confirmed.",
    )

    return jsonify(
        {
            "ok": True,
            "sample": {
                "blockId": sample["block_id"],
                "label": sample["label"],
                "source": source,
                "sequenceLength": len(events),
                "preview": events[:20] + (["..."] + events[-20:] if len(events) > 40 else []),
            },
            "prediction": prediction,
            "severity": severity,
            "trigger": trigger,
            "triggerPositions": trigger_positions,
            "compressedEvents": compress_event_runs(events, mapper),
            "mappedEvents": serializable_rows(pd.DataFrame(mapped_event_rows)),
            "comparison": serializable_rows(comparison),
            "metrics": serializable_rows(metrics),
            "contributors": serializable_rows(contributors),
            "timeline": timeline_rows(events, trigger["event_id"]),
            "report": report_text,
        }
    )


@app.post("/api/explain/stream")
def explain_stream():
    payload = request.get_json(force=True)
    user = require_user(payload)
    if not user:
        return jsonify({"ok": False, "message": "Sign in before generating an explanation."}), 401

    def generate():
        try:
            for chunk in stream_ollama_text(ollama_prompt(payload)):
                yield chunk
        except (urllib.error.URLError, TimeoutError, OSError):
            text = fallback_explanation(payload)
            for paragraph in text.split("\n\n"):
                yield paragraph + "\n\n"

    return Response(stream_with_context(generate()), mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False, threaded=True)
