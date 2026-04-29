from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HDFS_PREPROCESSED = PROJECT_ROOT / "dataset" / "HDFS_v1" / "preprocessed"
EVENT_TRACES_PATH = HDFS_PREPROCESSED / "Event_traces.csv"
OCCURRENCE_MATRIX_PATH = HDFS_PREPROCESSED / "Event_occurrence_matrix.csv"
TEMPLATES_PATH = HDFS_PREPROCESSED / "HDFS.log_templates.csv"


def parse_event_sequence(value):
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return []
    value = value.strip().strip("[]")
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def label_to_binary(label):
    return 0 if str(label).lower() in {"normal", "success", "0"} else 1


def load_event_traces():
    df = pd.read_csv(EVENT_TRACES_PATH)
    df["Events"] = df["Features"].apply(parse_event_sequence)
    df["BinaryLabel"] = df["Label"].apply(label_to_binary)
    return df


def load_occurrence_matrix():
    df = pd.read_csv(OCCURRENCE_MATRIX_PATH)
    event_cols = sorted(
        [col for col in df.columns if col.startswith("E")],
        key=lambda name: int(name[1:]),
    )
    x = df[event_cols].to_numpy(dtype=np.float32)
    y = df["Label"].apply(label_to_binary).to_numpy(dtype=np.int64)
    return df, x, y, event_cols


def get_hdfs_sample(label="Anomaly", index=0):
    df = load_event_traces()
    if str(label).lower() in {"mixed", "all", "any"}:
        subset = df.reset_index(drop=True)
    else:
        binary = label_to_binary(label)
        subset = df[df["BinaryLabel"] == binary].reset_index(drop=True)

    if subset.empty:
        raise ValueError(f"No HDFS samples found for label {label!r}")

    row = subset.iloc[index % len(subset)]
    return {
        "block_id": row["BlockId"],
        "label": row["Label"],
        "binary_label": int(row["BinaryLabel"]),
        "events": row["Events"],
        "latency": row.get("Latency"),
        "sample_count": len(subset),
    }


def sequence_to_counts(events, event_cols=None):
    if event_cols is None:
        event_cols = [f"E{i}" for i in range(1, 30)]
    counts = dict.fromkeys(event_cols, 0)
    for event_id in events:
        if event_id in counts:
            counts[event_id] += 1
    return np.array([[counts[col] for col in event_cols]], dtype=np.float32)
