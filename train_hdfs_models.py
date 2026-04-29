from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from inference.hdfs_data import load_occurrence_matrix


ARTIFACT_DIR = Path("artifacts")
RF_PATH = ARTIFACT_DIR / "hdfs_random_forest.joblib"


def train_random_forest():
    print("Training RandomForest on HDFS event-count features...")
    _, x, y, event_cols = load_occurrence_matrix()
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )

    pipeline = Pipeline(
        steps=[
            ("variance", VarianceThreshold(threshold=0.01)),
            ("log", FunctionTransformer(np.log1p, validate=False)),
            ("scaler", StandardScaler()),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=200,
                    n_jobs=-1,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    pipeline.fit(x_train, y_train)
    y_pred = pipeline.predict(x_test)
    y_prob = pipeline.predict_proba(x_test)[:, 1]

    print("RandomForest report:")
    print(classification_report(y_test, y_pred, target_names=["Normal", "Anomaly"]))
    print(f"RandomForest ROC-AUC: {roc_auc_score(y_test, y_prob):.4f}")

    ARTIFACT_DIR.mkdir(exist_ok=True)
    joblib.dump({"pipeline": pipeline, "event_cols": event_cols}, RF_PATH)
    print(f"Saved {RF_PATH}")


def main():
    train_random_forest()
    print(
        "\nTransformer note: PyTorch/TensorFlow currently segfault in this Python 3.13 "
        "environment. Train/export the Transformer from a stable Python 3.10/3.11 "
        "environment, then we can plug its artifact into inference."
    )


if __name__ == "__main__":
    main()
