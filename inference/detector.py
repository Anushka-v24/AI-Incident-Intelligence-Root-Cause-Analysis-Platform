from pathlib import Path

import joblib
import pandas as pd

from inference.hdfs_data import sequence_to_counts


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
RF_PATH = ARTIFACT_DIR / "hdfs_random_forest.joblib"
TRANSFORMER_PATH = ARTIFACT_DIR / "hdfs_transformer.joblib"

MODEL_OPTIONS = {
    "random_forest": {"label": "RandomForest", "path": RF_PATH, "fallback": False},
    "ensemble": {"label": "Ensemble", "path": None, "fallback": False},
    "transformer": {"label": "Transformer", "path": TRANSFORMER_PATH, "fallback": True},
    "lstm": {"label": "LSTM", "path": ARTIFACT_DIR / "hdfs_lstm.joblib", "fallback": True},
    "lightgbm": {"label": "LightGBM", "path": ARTIFACT_DIR / "hdfs_lightgbm.joblib", "fallback": True},
    "xgboost": {"label": "XGBoost", "path": ARTIFACT_DIR / "hdfs_xgboost.joblib", "fallback": True},
}

RF_METRICS = {
    "Accuracy": 0.997,
    "Normal Precision": 1.00,
    "Normal Recall": 1.00,
    "Normal F1": 1.00,
    "Anomaly Precision": 0.99,
    "Anomaly Recall": 0.91,
    "Anomaly F1": 0.95,
    "ROC-AUC": 0.9615,
}

HIGH_RISK_EVENT_HINTS = {
    "E4": "Exception while serving a block",
    "E7": "writeBlock received an exception",
    "E8": "PacketResponder was interrupted",
    "E10": "PacketResponder exception",
    "E12": "Exception while writing block to mirror",
    "E14": "Exception in receiveBlock",
    "E17": "Block transfer failed",
    "E20": "Unexpected delete error: block metadata missing from volumeMap",
    "E24": "Block removed from needed replication unexpectedly",
    "E28": "Stored block does not belong to any file",
    "E29": "Pending replication timed out",
}


class HDFSAnomalyDetector:
    def __init__(self, model_name="random_forest"):
        if model_name not in MODEL_OPTIONS:
            raise ValueError(f"Unknown model: {model_name}")

        self.model_name = model_name
        if not RF_PATH.exists():
            raise FileNotFoundError(
                f"Missing RandomForest artifact: {RF_PATH}. Run python3 train_hdfs_models.py first."
            )
        self.rf_artifact = joblib.load(RF_PATH)
        self.model_artifacts = {}
        for name, config in MODEL_OPTIONS.items():
            path = config["path"]
            if name == "random_forest" or path is None or not path.exists():
                continue
            self.model_artifacts[name] = joblib.load(path)

    def predict(self, events):
        rf_probability = self._predict_random_forest(events)

        probabilities = {"random_forest": rf_probability}
        fallback_reason = ""
        if self.model_name == "transformer":
            anomaly_probability, fallback_reason = self._predict_optional_model(
                "transformer", events, rf_probability
            )
            probabilities["transformer"] = anomaly_probability
        elif self.model_name == "ensemble":
            active_probabilities = [rf_probability]
            for optional_model in MODEL_OPTIONS:
                if optional_model in {"random_forest", "ensemble"}:
                    continue
                if optional_model in self.model_artifacts:
                    model_probability = self._predict_artifact(optional_model, events)
                    probabilities[optional_model] = model_probability
                    active_probabilities.append(model_probability)
            if len(active_probabilities) > 1:
                anomaly_probability = sum(active_probabilities) / len(active_probabilities)
            else:
                anomaly_probability = rf_probability
                fallback_reason = "No additional model artifacts found; ensemble used RandomForest only."
        elif self.model_name != "random_forest":
            anomaly_probability, fallback_reason = self._predict_optional_model(
                self.model_name, events, rf_probability
            )
            probabilities[self.model_name] = anomaly_probability
        else:
            anomaly_probability = rf_probability

        label = "Anomaly" if anomaly_probability >= self._decision_threshold(self.model_name) else "Normal"
        return {
            "model": self.model_name,
            "label": label,
            "is_anomaly": label == "Anomaly",
            "anomaly_probability": anomaly_probability,
            "normal_probability": 1.0 - anomaly_probability,
            "model_probabilities": probabilities,
            "fallback_reason": fallback_reason,
        }

    def compare_models(self, events):
        rows = []
        for name, config in MODEL_OPTIONS.items():
            if name == "random_forest":
                probability = self._predict_random_forest(events)
                status = "Active"
            elif name == "ensemble":
                prediction = self.predict(events)
                probability = prediction["anomaly_probability"]
                status = "Active" if len(prediction["model_probabilities"]) > 1 else "RandomForest fallback"
            elif name in self.model_artifacts:
                probability = self._predict_artifact(name, events)
                status = "Active"
            else:
                probability = self._predict_random_forest(events)
                path = config["path"]
                status = f"Artifact missing, using RandomForest ({path.name})"

            rows.append(
                {
                    "Model": config["label"],
                    "Status": status,
                    "Prediction": "Anomaly" if probability >= self._decision_threshold(name) else "Normal",
                    "Anomaly Probability": f"{probability:.2%}",
                }
            )
        return pd.DataFrame(rows)

    def metrics_table(self):
        return pd.DataFrame(
            [{"Metric": metric, "Score": score} for metric, score in RF_METRICS.items()]
        )

    def top_contributing_events(self, events, mapper=None, limit=8):
        event_cols = self.rf_artifact["event_cols"]
        counts = sequence_to_counts(events, event_cols)[0]
        pipeline = self.rf_artifact["pipeline"]
        selector = pipeline.named_steps["variance"]
        model = pipeline.named_steps["model"]

        selected_cols = [
            event for event, keep in zip(event_cols, selector.get_support()) if keep
        ]
        importances = dict(zip(selected_cols, model.feature_importances_))

        rows = []
        for event_id, count in zip(event_cols, counts):
            importance = float(importances.get(event_id, 0.0))
            if count <= 0:
                continue
            template = mapper.get_template(event_id) if mapper else ""
            rows.append(
                {
                    "Event ID": event_id,
                    "Count": int(count),
                    "Model Importance": importance,
                    "Contribution Score": float(count * importance),
                    "Template": template,
                }
            )

        rows.sort(key=lambda row: row["Contribution Score"], reverse=True)
        return pd.DataFrame(rows[:limit])

    def likely_trigger(self, events, mapper=None):
        contributors = self.top_contributing_events(events, mapper=mapper, limit=12)
        if contributors.empty:
            return {
                "event_id": "N/A",
                "severity": "LOW",
                "reason": "No strong contributing event was found in this sequence.",
                "template": "",
                "count": 0,
                "contribution_score": 0.0,
            }

        records = contributors.to_dict("records")
        high_risk_records = [
            row
            for row in records
            if row["Event ID"] in HIGH_RISK_EVENT_HINTS and row["Count"] > 0
        ]
        trigger = high_risk_records[0] if high_risk_records else records[0]
        event_id = trigger["Event ID"]
        reason = HIGH_RISK_EVENT_HINTS.get(
            event_id,
            "This event has the highest RandomForest contribution for the selected sample.",
        )

        if event_id in HIGH_RISK_EVENT_HINTS and trigger["Contribution Score"] > 0:
            severity = "HIGH"
        elif trigger["Contribution Score"] >= 0.2:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return {
            "event_id": event_id,
            "severity": severity,
            "reason": reason,
            "template": trigger["Template"],
            "count": int(trigger["Count"]),
            "contribution_score": float(trigger["Contribution Score"]),
        }

    def severity(self, anomaly_probability, trigger=None):
        risk_score = round(float(anomaly_probability) * 100)
        if trigger and trigger.get("event_id") in HIGH_RISK_EVENT_HINTS and risk_score >= 50:
            risk_score = max(risk_score, 85)

        if risk_score >= 85:
            level = "HIGH"
        elif risk_score >= 50:
            level = "MEDIUM"
        else:
            level = "LOW"
        return {"level": level, "risk_score": risk_score}

    def _predict_random_forest(self, events):
        event_cols = self.rf_artifact["event_cols"]
        x = sequence_to_counts(events, event_cols)
        pipeline = self.rf_artifact["pipeline"]
        return float(pipeline.predict_proba(x)[0, 1])

    def _predict_optional_model(self, model_name, events, fallback_probability):
        if model_name not in self.model_artifacts:
            path = MODEL_OPTIONS[model_name]["path"]
            reason = (
                f"{MODEL_OPTIONS[model_name]['label']} artifact is missing at {path}; "
                "using RandomForest fallback."
            )
            return fallback_probability, reason
        return self._predict_artifact(model_name, events), ""

    def _decision_threshold(self, model_name):
        artifact = self.model_artifacts.get(model_name)
        if isinstance(artifact, dict):
            return float(artifact.get("decision_threshold", 0.5))
        return 0.5

    def _predict_artifact(self, model_name, events):
        artifact = self.model_artifacts[model_name]
        if callable(artifact):
            return float(artifact(events))

        if isinstance(artifact, dict):
            if "sequence_pipeline" in artifact:
                sequence_text = " ".join(events)
                probability = float(artifact["sequence_pipeline"].predict_proba([sequence_text])[0, 1])
                high_risk_events = set(artifact.get("high_risk_events", []))
                if high_risk_events.intersection(events):
                    probability = max(probability, float(artifact.get("high_risk_floor", 0.85)))
                return probability
            if "pipeline" in artifact and "event_cols" in artifact:
                x = sequence_to_counts(events, artifact["event_cols"])
                return float(artifact["pipeline"].predict_proba(x)[0, 1])
            if "model" in artifact and "event_cols" in artifact:
                x = sequence_to_counts(events, artifact["event_cols"])
                probability = float(artifact["model"].predict_proba(x)[0, 1])
                high_risk_events = set(artifact.get("high_risk_events", []))
                if high_risk_events.intersection(events):
                    probability = max(probability, float(artifact.get("high_risk_floor", 0.85)))
                return probability
            if "predict_proba" in artifact and callable(artifact["predict_proba"]):
                return float(artifact["predict_proba"](events))

        raise RuntimeError(
            f"Unsupported {MODEL_OPTIONS[model_name]['label']} artifact format. Expected a "
            "callable, or a dict with sequence_pipeline, pipeline/event_cols, model/event_cols, or predict_proba."
        )
