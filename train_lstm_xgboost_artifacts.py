from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier

from inference.detector import HIGH_RISK_EVENT_HINTS
from inference.hdfs_data import load_event_traces, load_occurrence_matrix


ARTIFACT_DIR = Path("artifacts")
LSTM_PATH = ARTIFACT_DIR / "hdfs_lstm.joblib"
XGBOOST_PATH = ARTIFACT_DIR / "hdfs_xgboost.joblib"
LIGHTGBM_PATH = ARTIFACT_DIR / "hdfs_lightgbm.joblib"


def sequence_to_text(events):
    return " ".join(events)


def train_lstm_artifact(sample_size=60000):
    df = load_event_traces()
    if sample_size and len(df) > sample_size:
        df = df.sample(sample_size, random_state=7)

    x = df["Events"].apply(sequence_to_text)
    y = df["BinaryLabel"]
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        stratify=y,
        random_state=7,
    )

    pipeline = Pipeline(
        steps=[
            (
                "events",
                TfidfVectorizer(
                    token_pattern=r"E\d+",
                    lowercase=False,
                    analyzer="word",
                    ngram_range=(1, 5),
                    min_df=2,
                    max_features=7000,
                ),
            ),
            (
                "model",
                SGDClassifier(
                    loss="log_loss",
                    alpha=0.0001,
                    max_iter=1000,
                    random_state=7,
                    tol=1e-3,
                ),
            ),
        ]
    )
    pipeline.fit(x_train, y_train)
    y_pred = pipeline.predict(x_test)
    y_prob = pipeline.predict_proba(x_test)[:, 1]

    print("LSTM-compatible sequence artifact report:")
    print(classification_report(y_test, y_pred, target_names=["Normal", "Anomaly"]))
    print(f"ROC-AUC: {roc_auc_score(y_test, y_prob):.4f}")

    ARTIFACT_DIR.mkdir(exist_ok=True)
    joblib.dump(
        {
            "sequence_pipeline": pipeline,
            "model_type": "LSTM-compatible sequence classifier",
            "high_risk_events": sorted(HIGH_RISK_EVENT_HINTS),
            "high_risk_floor": 0.85,
            "description": (
                "Uses ordered event n-grams for safe Streamlit inference when the "
                "notebook LSTM cannot be imported in this Python environment."
            ),
        },
        LSTM_PATH,
    )
    print(f"Saved {LSTM_PATH}")


def train_xgboost_artifact(sample_size=120000):
    _, x, y, event_cols = load_occurrence_matrix()
    if sample_size and len(y) > sample_size:
        _, x, y, _ = load_occurrence_matrix()
        import numpy as np

        rng = np.random.default_rng(42)
        normal_idx = np.where(y == 0)[0]
        anomaly_idx = np.where(y == 1)[0]
        normal_take = min(len(normal_idx), sample_size - len(anomaly_idx))
        selected = np.concatenate(
            [
                rng.choice(normal_idx, size=normal_take, replace=False),
                anomaly_idx,
            ]
        )
        rng.shuffle(selected)
        x = x[selected]
        y = y[selected]

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )
    model = XGBClassifier(
        n_estimators=220,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=1,
    )
    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)
    y_prob = model.predict_proba(x_test)[:, 1]

    print("XGBoost event-count artifact report:")
    print(classification_report(y_test, y_pred, target_names=["Normal", "Anomaly"]))
    print(f"ROC-AUC: {roc_auc_score(y_test, y_prob):.4f}")

    ARTIFACT_DIR.mkdir(exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "event_cols": event_cols,
            "model_type": "XGBoost event-count classifier",
            "decision_threshold": 0.6,
            "high_risk_events": sorted(HIGH_RISK_EVENT_HINTS),
            "high_risk_floor": 0.85,
        },
        XGBOOST_PATH,
    )
    print(f"Saved {XGBOOST_PATH}")


def train_lightgbm_artifact(sample_size=120000):
    _, x, y, event_cols = load_occurrence_matrix()
    if sample_size and len(y) > sample_size:
        import numpy as np

        rng = np.random.default_rng(43)
        normal_idx = np.where(y == 0)[0]
        anomaly_idx = np.where(y == 1)[0]
        normal_take = min(len(normal_idx), sample_size - len(anomaly_idx))
        selected = np.concatenate(
            [
                rng.choice(normal_idx, size=normal_take, replace=False),
                anomaly_idx,
            ]
        )
        rng.shuffle(selected)
        x = x[selected]
        y = y[selected]

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        stratify=y,
        random_state=43,
    )
    model = LGBMClassifier(
        n_estimators=260,
        max_depth=5,
        learning_rate=0.06,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary",
        class_weight="balanced",
        random_state=43,
        n_jobs=1,
        verbose=-1,
    )
    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)
    y_prob = model.predict_proba(x_test)[:, 1]

    print("LightGBM event-count artifact report:")
    print(classification_report(y_test, y_pred, target_names=["Normal", "Anomaly"]))
    print(f"ROC-AUC: {roc_auc_score(y_test, y_prob):.4f}")

    ARTIFACT_DIR.mkdir(exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "event_cols": event_cols,
            "model_type": "LightGBM event-count classifier",
            "decision_threshold": 0.6,
            "high_risk_events": sorted(HIGH_RISK_EVENT_HINTS),
            "high_risk_floor": 0.85,
        },
        LIGHTGBM_PATH,
    )
    print(f"Saved {LIGHTGBM_PATH}")


def main():
    train_lstm_artifact()
    train_xgboost_artifact()
    train_lightgbm_artifact()


if __name__ == "__main__":
    main()
