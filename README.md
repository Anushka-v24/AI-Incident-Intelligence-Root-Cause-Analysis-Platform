# AI Incident Intelligence and Root Cause Analysis Platform

AI Incident Intelligence is a local HDFS log anomaly detection and root-cause assistance platform. It combines trained machine-learning detectors, event-template mapping, incident history, report generation, and an Ollama-powered developer debug brief for explaining likely failure causes.

## Project Overview

Modern distributed systems generate large volumes of logs. Manual inspection of HDFS event sequences is slow, error-prone, and difficult for operators or developers who need quick evidence during debugging. This project converts HDFS event streams into model-ready features, predicts whether a block sequence is normal or anomalous, identifies likely contributing events, and presents the result through a responsive web console.

## Key Features

- HDFS event anomaly detection using RandomForest, ensemble fallback, Transformer-compatible, LSTM-compatible, LightGBM, and XGBoost artifacts.
- Event mapping manual for interpreting event IDs such as `E20`, `E26`, and related HDFS templates.
- Dataset sample, manual event entry, and uploaded log input modes.
- Developer Debug Brief generated through local Ollama `llama3`, with rule-based fallback when Ollama is unavailable.
- Incident severity timeline, event sequence graph, contributing event tables, and report export.
- User login/signup with local salted password hashes.
- User-scoped incident history and sample comparison page.
- Streamlit dashboard and Flask/React web dashboard.

## Repository Structure

```text
Minor2/
├── app.py                         # Streamlit dashboard
├── api_server.py                  # Flask API + web app server
├── web/index.html                 # React/Tailwind browser UI
├── streamlit_app/                 # Streamlit auth, styles, utilities
├── inference/                     # Data loading, event mapping, detection, reports
├── server/                        # Flask routes, auth, analysis, LLM streaming
├── llm/                           # Ollama/CrewAI LLM wrapper and prompts
├── agents/                        # CrewAI agent workflow
├── artifacts/                     # Model artifacts, users, incident history
├── dataset/                       # HDFS datasets and preprocessed files
├── Models/                        # Training and comparison notebooks
├── Preprocessing and EDA/         # Exploratory notebooks
└── PROJECT_REPORT.md              # Academic report draft
```

## Dataset

The implementation uses the HDFS v1 preprocessed dataset under:

```text
dataset/HDFS_v1/preprocessed/
```

Important files:

- `Event_traces.csv`: block-level event sequences.
- `Event_occurrence_matrix.csv`: count-based features for model training.
- `HDFS.log_templates.csv`: event ID to event-template mapping.
- `anomaly_label.csv`: block-level ground-truth labels.

Current local dataset summary:

- Total block sequences: `575,061`
- Normal/success sequences: `558,223`
- Failure/anomaly sequences: `16,838`
- Event templates: `29`

## Models

The detector layer is implemented in `inference/detector.py`.

Supported detector options:

- `random_forest`
- `ensemble`
- `transformer`
- `lstm`
- `lightgbm`
- `xgboost`

The RandomForest model is the primary reliable baseline. Optional model artifacts fall back safely when unavailable or unsupported.

Reported RandomForest holdout metrics in the app:

| Metric | Score |
|---|---:|
| Accuracy | 0.997 |
| Normal Precision | 1.00 |
| Normal Recall | 1.00 |
| Normal F1 | 1.00 |
| Anomaly Precision | 0.99 |
| Anomaly Recall | 0.91 |
| Anomaly F1 | 0.95 |
| ROC-AUC | 0.9615 |

## Running the Streamlit App

```bash
streamlit run app.py
```

Open the local URL printed by Streamlit, usually:

```text
http://localhost:8502
```

## Running the Flask/React Web UI

```bash
python3 api_server.py
```

Open:

```text
http://127.0.0.1:5001/
```

The Flask/React UI contains the newer dark console layout, live Developer Debug Brief, animated assistant bot, comparison page, history page, and mapping manual.

## Ollama Setup

Install and run Ollama locally, then pull `llama3`:

```bash
ollama pull llama3
```

The app checks:

```text
http://localhost:11434/api/tags
```

If Ollama or `llama3` is not available, the platform still works and uses a built-in rule-based explanation.

## Training Artifacts

Train or refresh the primary RandomForest artifact:

```bash
python3 train_hdfs_models.py
```

Train optional compatible artifacts:

```bash
python3 train_transformer_artifact.py
python3 train_lstm_xgboost_artifacts.py
```

Generated model files are stored in:

```text
artifacts/
```

## Academic Report

A structured report draft matching the requested institutional format is available at:

```text
PROJECT_REPORT.md
```

It includes preliminary pages, chapter-wise content, result analysis, references in IEEE style, appendices, annexure sections, sustainability statement, and final review checklist.

## Limitations

- The platform is a decision-support tool, not an autonomous remediation system.
- Explanations are generated from model evidence and should be validated by a human operator.
- Model performance is based on available HDFS v1-style data and may require retraining before use on other systems.
- User authentication is local and suitable for academic demonstration, not production identity management.

## Future Scope

- Add deployment-grade authentication and role-based access.
- Integrate real-time log streaming.
- Improve transformer-based sequence modeling in a stable Python environment.
- Add richer explainability, alert routing, and MLOps monitoring.
- Export final academic report as `.docx` or PDF with institutional formatting.
