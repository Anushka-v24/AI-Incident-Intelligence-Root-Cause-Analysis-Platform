from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from inference.hdfs_data import load_event_traces
from inference.detector import HIGH_RISK_EVENT_HINTS


ARTIFACT_DIR = Path("artifacts")
TRANSFORMER_PATH = ARTIFACT_DIR / "hdfs_transformer.joblib"


def sequence_to_text(events):
    return " ".join(events)


def train_transformer_artifact(sample_size=60000):
    df = load_event_traces()
    if sample_size and len(df) > sample_size:
        df = df.sample(sample_size, random_state=42)

    x = df["Events"].apply(sequence_to_text)
    y = df["BinaryLabel"]
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )

    pipeline = Pipeline(
        steps=[
            (
                "events",
                TfidfVectorizer(
                    token_pattern=r"E\d+",
                    lowercase=False,
                    ngram_range=(1, 4),
                    min_df=2,
                    max_features=5000,
                ),
            ),
            (
                "model",
                LogisticRegression(
                    max_iter=1000,
                    n_jobs=1,
                    random_state=42,
                ),
            ),
        ]
    )
    pipeline.fit(x_train, y_train)
    y_pred = pipeline.predict(x_test)
    y_prob = pipeline.predict_proba(x_test)[:, 1]

    print("Transformer-compatible sequence artifact report:")
    print(classification_report(y_test, y_pred, target_names=["Normal", "Anomaly"]))
    print(f"ROC-AUC: {roc_auc_score(y_test, y_prob):.4f}")

    ARTIFACT_DIR.mkdir(exist_ok=True)
    joblib.dump(
        {
            "sequence_pipeline": pipeline,
            "model_type": "Transformer-compatible sequence classifier",
            "high_risk_events": sorted(HIGH_RISK_EVENT_HINTS),
            "high_risk_floor": 0.85,
            "description": (
                "Uses event-token sequence n-grams for safe Streamlit inference when "
                "PyTorch Transformer import is unavailable in this Python environment."
            ),
        },
        TRANSFORMER_PATH,
    )
    print(f"Saved {TRANSFORMER_PATH}")


if __name__ == "__main__":
    train_transformer_artifact()
