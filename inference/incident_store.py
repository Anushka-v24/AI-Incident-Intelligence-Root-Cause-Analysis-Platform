import csv
from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
HISTORY_PATH = ARTIFACT_DIR / "incident_history.csv"

HISTORY_COLUMNS = [
    "User",
    "Time",
    "Block ID",
    "Sample Pool",
    "Sample Index",
    "Ground Truth",
    "Prediction",
    "Probability",
    "Severity",
    "Risk Score",
    "Trigger Event",
    "Model",
]


def load_incident_history(limit=25, user=None):
    if not HISTORY_PATH.exists():
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    history = pd.read_csv(HISTORY_PATH)
    for column in HISTORY_COLUMNS:
        if column not in history.columns:
            history[column] = ""
    history = history[HISTORY_COLUMNS]
    if user:
        history = history[history["User"].fillna("") == user]
    return history.tail(limit).iloc[::-1].reset_index(drop=True)


def save_incident_history(row):
    ARTIFACT_DIR.mkdir(exist_ok=True)
    exists = HISTORY_PATH.exists()
    if exists:
        history = pd.read_csv(HISTORY_PATH)
        if list(history.columns) != HISTORY_COLUMNS:
            for column in HISTORY_COLUMNS:
                if column not in history.columns:
                    history[column] = ""
            history = history[HISTORY_COLUMNS]
            history.to_csv(HISTORY_PATH, index=False)

    with HISTORY_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=HISTORY_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow({column: row.get(column, "") for column in HISTORY_COLUMNS})


def build_incident_report(
    sample,
    sample_pool,
    sample_index,
    prediction,
    severity,
    trigger,
    trigger_positions,
    contributors,
    mapped_events,
    llm_result,
):
    lines = [
        "AI Incident Intelligence Report",
        "=" * 31,
        f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Block ID: {sample['block_id']}",
        f"Sample Pool: {sample_pool}",
        f"Sample Index: {sample_index}",
        f"Dataset Ground Truth: {sample['label']}",
        "",
        "Model Result",
        "-" * 12,
        f"Prediction: {prediction['label']}",
        f"Anomaly Probability: {prediction['anomaly_probability']:.2%}",
        f"Severity: {severity['level']}",
        f"Risk Score: {severity['risk_score']}/100",
        "",
        "Likely Trigger",
        "-" * 14,
        f"Event ID: {trigger['event_id']}",
        f"Reason: {trigger['reason']}",
        f"Template: {trigger['template']}",
        f"Count: {trigger['count']}",
        f"Positions: {trigger_positions}",
        f"Contribution Score: {trigger['contribution_score']:.4f}",
        "",
        "Top Contributing Events",
        "-" * 23,
    ]

    for row in contributors.to_dict("records"):
        lines.append(
            f"{row['Event ID']} | count={row['Count']} | "
            f"contribution={row['Contribution Score']:.4f} | {row['Template']}"
        )

    lines.extend(["", "Mapped Event Templates", "-" * 22])
    lines.extend(mapped_events)

    lines.extend(["", "LLM Root-Cause and Fix Report", "-" * 29, str(llm_result)])
    return "\n".join(lines)
