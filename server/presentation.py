import re

import pandas as pd

from inference.detector import HIGH_RISK_EVENT_HINTS
from inference.event_mapper import EventMapper
from inference.hdfs_data import TEMPLATES_PATH


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
    high_risk_events = set(HIGH_RISK_EVENT_HINTS)
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

