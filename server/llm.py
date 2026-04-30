import json
import urllib.request


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

