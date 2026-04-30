from datetime import datetime

import pandas as pd

from inference.detector import HDFSAnomalyDetector
from inference.event_mapper import EventMapper
from inference.hdfs_data import TEMPLATES_PATH, get_hdfs_sample
from inference.incident_store import build_incident_report, save_incident_history
from server.presentation import compress_event_runs, parse_event_ids, serializable_rows, timeline_rows


def build_sample(payload):
    source = payload.get("source", "Dataset sample")
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
    return source, sample_pool, sample_index, sample


def analyze_events(payload, user):
    model_name = payload.get("modelName", "random_forest")
    source, sample_pool, sample_index, sample = build_sample(payload)
    events = sample["events"]
    if not events:
        raise ValueError("Provide at least one event ID before analysis.")

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

    return {
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

