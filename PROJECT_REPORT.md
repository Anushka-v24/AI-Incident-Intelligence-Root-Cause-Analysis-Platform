# AI Incident Intelligence and Root Cause Analysis Platform

## Preliminary Pages

### Cover Page

**Project Title:** AI Incident Intelligence and Root Cause Analysis Platform  
**Submitted in partial fulfilment of the requirements for:** Minor Project / Academic Project  
**Submitted by:** `[Student Name / Roll Number]`  
**Department:** `[Department Name]`  
**Institution:** `[Institution Name]`  
**Academic Year:** `2025-2026`  
**Supervisor:** `[Supervisor Name]`

> Note: Replace bracketed fields with the standardized institutional format before printing.

### Certificate

This is to certify that the project report titled **"AI Incident Intelligence and Root Cause Analysis Platform"** submitted by `[Student Name]`, Roll No. `[Roll Number]`, is a record of original work carried out under my supervision and guidance. The work is submitted in partial fulfilment of the academic requirements of `[Programme / Department]`.

**Supervisor Signature:** ____________________  
**Name:** `[Supervisor Name]`  
**Date:** ____________________

**HOD / Associate HOD Signature:** ____________________  
**Name:** `[HOD / Associate HOD Name]`  
**Date:** ____________________

### Declaration of Originality by the Student

I, `[Student Name]`, declare that this project report titled **"AI Incident Intelligence and Root Cause Analysis Platform"** is my original work. The work has not been submitted elsewhere for any degree, diploma, or certification. All external datasets, research papers, software libraries, and documentation used in the project have been properly acknowledged.

**Student Signature:** ____________________  
**Date:** ____________________

### Acknowledgement

I express my sincere gratitude to my project supervisor, `[Supervisor Name]`, for continuous guidance, technical support, and valuable feedback throughout the project. I also thank the Head of Department, faculty members, classmates, and the institution for providing the necessary academic environment and resources. I acknowledge the open-source communities and researchers whose datasets, tools, and studies supported the development of this project.

### Abstract

Distributed systems such as Hadoop Distributed File System generate large volumes of logs during normal operation. These logs contain valuable evidence for detecting failures, but manual inspection is time-consuming and difficult because log sequences can be long, repetitive, and highly technical. This project proposes an AI Incident Intelligence and Root Cause Analysis Platform that detects anomalous HDFS event sequences, identifies likely contributing events, and generates a developer-facing explanation for debugging.

The methodology uses preprocessed HDFS block-level event traces and event-template mappings. Count-based event features are used for supervised machine-learning models, including RandomForest, LightGBM, XGBoost, and compatible sequence-model artifacts. The platform also includes event sequence visualization, severity scoring, sample comparison, incident history, and report generation. A local Ollama-based language model produces a live Developer Debug Brief; when the model is unavailable, a deterministic rule-based explanation is used.

The implemented system achieved strong RandomForest baseline performance, with reported accuracy of 0.997 and ROC-AUC of 0.9615 on the configured holdout evaluation. The interface supports dataset samples, manual event entry, and uploaded log evidence. It presents anomaly declaration, block details, generated explanation, graphs, and evidence tables in an operator-friendly workflow.

The societal relevance of the project lies in reducing debugging time, improving reliability of digital infrastructure, and helping developers interpret operational logs responsibly. The system is designed as decision support and includes ethical caution that remediation must be verified before changing live systems.

### Table of Contents

1. Introduction  
2. Literature Survey / Critical Review  
3. System Design and Methodology  
4. Implementation and Testing  
5. Results and Discussion  
6. Conclusion and Future Scope  
7. References  
8. Appendices  
9. Annexure

### List of Figures

**Figure 1.1:** Project Gantt chart / timeline  
**Figure 3.1:** Proposed system block diagram  
**Figure 3.2:** Detection and explanation workflow  
**Figure 4.1:** Flask/React dashboard screenshot  
**Figure 4.2:** Streamlit dashboard screenshot  
**Figure 5.1:** Incident severity timeline  
**Figure 5.2:** Event sequence graph

### List of Tables

**Table 2.1:** Summary of existing literature  
**Table 3.1:** Tool and technique selection  
**Table 4.1:** Test cases  
**Table 5.1:** Dataset summary  
**Table 5.2:** RandomForest performance metrics  
**Table 5.3:** Model comparison

### List of Abbreviations

| Abbreviation | Full Form |
|---|---|
| AI | Artificial Intelligence |
| API | Application Programming Interface |
| BERT | Bidirectional Encoder Representations from Transformers |
| CSV | Comma-Separated Values |
| EDA | Exploratory Data Analysis |
| HDFS | Hadoop Distributed File System |
| HOD | Head of Department |
| LGBM | Light Gradient Boosting Machine |
| LLM | Large Language Model |
| LSTM | Long Short-Term Memory |
| ML | Machine Learning |
| RCA | Root Cause Analysis |
| ROC-AUC | Receiver Operating Characteristic - Area Under Curve |
| UI | User Interface |
| XGBoost | Extreme Gradient Boosting |

---

# Chapter 1: Introduction

## 1.1 Background

Distributed systems are widely used for storage, computation, cloud platforms, and large-scale data processing. Hadoop Distributed File System is one such system that records operational events through logs. These logs help developers and operators understand block creation, deletion, replication, verification, and failure behaviour.

However, raw logs are difficult to interpret. They are repetitive, large, and often require expert knowledge. In real operational environments, delayed detection of abnormal patterns can increase downtime and reduce system reliability. Automated log anomaly detection helps convert logs into structured evidence and supports faster incident response.

This project builds a practical platform that combines HDFS event mapping, machine-learning anomaly detection, severity analysis, visual dashboards, and local LLM-based explanation.

## 1.2 Problem Statement

The problem addressed by this project is:

> To design and implement an AI-based platform that detects anomalous HDFS log event sequences, identifies likely trigger events, explains the cause in developer-friendly language, and presents evidence through a usable dashboard.

The platform must support:

- Dataset-based and manual event analysis.
- Model-based anomaly prediction.
- Evidence tables, graphs, and severity timeline.
- Local generative explanation through Ollama.
- Report generation and user-specific history.

## 1.3 Social and Environmental Relevance

Reliable digital infrastructure supports banking, education, healthcare, governance, cloud services, and business operations. Faster anomaly detection can reduce downtime and help teams prevent cascading failures. The project promotes responsible AI by presenting model output as decision support rather than automatic proof.

Environmental relevance is indirect but meaningful. Efficient debugging can reduce repeated computation, unnecessary server restarts, and prolonged system failures. Local inference with Ollama also reduces dependency on remote API calls, although local compute usage must still be managed responsibly.

## 1.4 Gantt Chart / Timeline

**Figure 1.1: Project Gantt Chart / Timeline**

| Phase | Activities | Duration |
|---|---|---|
| Phase 1 | Problem identification and literature review | Week 1-2 |
| Phase 2 | Dataset study and preprocessing | Week 3-4 |
| Phase 3 | Model training and artifact creation | Week 5-6 |
| Phase 4 | Streamlit dashboard implementation | Week 7 |
| Phase 5 | Flask/React dashboard implementation | Week 8-9 |
| Phase 6 | Ollama/CrewAI explanation integration | Week 10 |
| Phase 7 | Testing, UI refinement, report writing | Week 11-12 |

## 1.5 Scope

The project scope includes:

- HDFS v1 dataset-based anomaly detection.
- Event-template mapping from preprocessed HDFS logs.
- Multiple ML model choices with safe fallback.
- Local web dashboard and Streamlit dashboard.
- Developer-facing explanation and report generation.
- Academic demonstration of AI-assisted incident intelligence.

The project does not include production-grade deployment, enterprise identity management, real-time cluster integration, or autonomous remediation.

---

# Chapter 2: Literature Survey / Critical Review

## 2.1 Overview of Existing Work / Literature Review

Early work by Xu et al. demonstrated that console logs can be mined to detect large-scale system problems. This established the HDFS dataset as a common benchmark for log anomaly detection. Later systems such as Drain focused on structured log parsing, while DeepLog introduced deep sequence modelling using LSTM networks.

Recent work has explored transformer and BERT-based approaches. LogBERT uses self-supervised BERT-style learning for log anomaly detection, while LAnoBERT proposes a parser-free BERT masked language model approach. These studies show that both traditional ML and modern deep learning can be useful, but practical deployment still requires interpretability, usability, and integration with operator workflows.

This project uses that research direction but focuses on a deployable student project platform: model prediction, event mapping, visualization, explanation, and report generation in one interface.

## 2.2 Summary Table

**Table 2.1: Summary of Existing Literature**

| Work | Method | Dataset / Domain | Strength | Limitation |
|---|---|---|---|---|
| Xu et al. | Log mining and feature extraction | HDFS logs | Established HDFS benchmark | Older dataset and feature engineering heavy |
| Drain | Online log parsing | Multiple logs | Efficient structured parsing | Parser quality affects downstream detection |
| DeepLog | LSTM sequence modelling | System logs | Captures sequence patterns | Requires careful training and tuning |
| LogBERT | BERT-based self-supervised model | HDFS, BGL, Thunderbird | Learns contextual log patterns | Higher computational cost |
| LAnoBERT | Parser-free BERT masked LM | System logs | Reduces dependency on parsers | More complex to deploy locally |
| Proposed system | ML + dashboard + LLM explanation | HDFS v1 | Practical, explainable workflow | Limited to available local data and artifacts |

## 2.3 Research Gaps / Limitations of Existing Methods

Identified gaps include:

- Many models focus on prediction accuracy but not operator usability.
- Deep learning methods can be difficult to explain.
- Manual mapping from event ID to operational meaning is often missing.
- Research prototypes may not include report generation or user history.
- Production use requires ethical caution, validation, and auditability.

The proposed system addresses these gaps by combining detection, mapping, graphing, explanation, and report generation.

---

# Chapter 3: System Design and Methodology

## 3.1 Proposed Methodology

The proposed methodology contains six main stages:

1. Load HDFS block-level event traces.
2. Convert event sequences into model features.
3. Run anomaly detector and estimate anomaly probability.
4. Identify likely trigger events through model contribution and high-risk event hints.
5. Generate visual evidence, severity timeline, and event graph.
6. Produce a Developer Debug Brief through Ollama or fallback explanation.

**Figure 3.1: Proposed System Block Diagram**

```text
HDFS Logs / Event IDs
        |
        v
Preprocessed Event Traces + Templates
        |
        v
Feature Extraction / Sequence Encoding
        |
        v
ML Detector Layer
        |
        +--> Prediction + Probability + Severity
        +--> Trigger Event + Contributors
        |
        v
Dashboard Evidence Layer
        |
        +--> Graphs and Tables
        +--> Incident History
        +--> Report Export
        |
        v
Ollama / Rule-Based Explanation
        |
        v
Developer Debug Brief
```

**Figure 3.2: Detection and Explanation Workflow**

```text
Input Source Selection
  -> Dataset Sample / Manual Events / Uploaded Log
  -> Event Parsing
  -> Model Selection
  -> Run Detection
  -> Save History
  -> Display Anomaly Declaration
  -> Display Block Details
  -> Generate Debug Brief
  -> Display Graphs
  -> Display Tables and Report
```

## 3.2 Tool and Technique Selection

**Table 3.1: Tool and Technique Selection**

| Tool / Technique | Purpose | Reason for Selection |
|---|---|---|
| Python | Core implementation | Strong ML and data ecosystem |
| Pandas / NumPy | Data handling | Efficient CSV and matrix processing |
| Scikit-learn | ML model training | Reliable baseline algorithms and pipelines |
| RandomForest | Primary detector | Robust for tabular event-count features |
| LightGBM / XGBoost | Optional boosted detectors | Strong supervised classification baselines |
| Streamlit | Rapid dashboard | Simple academic prototype interface |
| Flask | API server | Lightweight backend for browser UI |
| React + Tailwind | Web UI | Responsive and interactive frontend |
| Ollama | Local LLM inference | Privacy-friendly local explanation generation |
| CrewAI | Agent workflow | Structured LLM reasoning flow |
| HDFS v1 dataset | Evaluation data | Standard log anomaly detection benchmark |

---

# Chapter 4: Implementation and Testing

## 4.1 Experimental Setup

The project was implemented in Python with local model artifacts stored in the `artifacts/` directory. The dashboard can run in two modes:

- Streamlit mode using `streamlit run app.py`.
- Flask/React mode using `python3 api_server.py`.

Dataset files are stored under `dataset/HDFS_v1/preprocessed/`. The main dataset file `Event_traces.csv` contains `575,061` block sequences, including `558,223` success sequences and `16,838` failure sequences. Event-template mapping uses `HDFS.log_templates.csv` with `29` event templates.

## 4.2 Test Cases / Case Study / Code / Flow Chart / Screenshots / Output

**Table 4.1: Test Cases**

| Test Case ID | Input | Expected Output | Status |
|---|---|---|---|
| TC-01 | Valid login credentials | Dashboard opens | Passed |
| TC-02 | Dataset sample with RandomForest | Prediction, severity, and block details displayed | Passed |
| TC-03 | Manual events such as `E5, E22, E11, E9, E3, E20` | Events parsed and analysed | Passed |
| TC-04 | Uploaded `.txt` or `.log` file | Event IDs extracted from file | Passed |
| TC-05 | Missing Ollama model | Rule-based explanation displayed | Passed |
| TC-06 | Comparison page samples | Left and right sample results displayed | Passed |
| TC-07 | Report export | TXT/PDF report generated | Passed |

**Figure 4.1: Flask/React Dashboard Screenshot**

Insert screenshot of the dark web console showing anomaly declaration, block details, Developer Debug Brief, graph, and evidence tables.

**Figure 4.2: Streamlit Dashboard Screenshot**

Insert screenshot of Streamlit dashboard showing model detection, tabs, and report export.

Important implementation files:

- `web/index.html`: React/Tailwind UI.
- `api_server.py`: Flask app entry point.
- `server/routes.py`: API routes.
- `server/analysis.py`: analysis workflow.
- `inference/detector.py`: model prediction and evidence logic.
- `inference/event_mapper.py`: event ID to template mapping.
- `inference/incident_store.py`: history and report generation.
- `streamlit_app/utils.py`: Streamlit utility functions.

---

# Chapter 5: Results and Discussion

## 5.1 Result Analysis

The platform successfully presents the result in the following order:

1. Anomaly declaration.
2. Block details and trigger evidence.
3. Developer Debug Brief.
4. Incident graph.
5. Evidence tables and report tools.

This order makes the result easier to understand because users first see the decision, then the supporting block details, then the explanation, and finally deeper evidence.

**Table 5.1: Dataset Summary**

| Item | Value |
|---|---:|
| Block sequences | 575,061 |
| Success sequences | 558,223 |
| Failure sequences | 16,838 |
| Event templates | 29 |

**Table 5.2: RandomForest Performance Metrics**

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

## 5.2 Performance Evaluation / Comparison with Existing Methods

**Table 5.3: Model Comparison**

| Model | Role in Project | Expected Strength |
|---|---|---|
| RandomForest | Primary baseline | High accuracy on count features |
| Transformer-compatible artifact | Sequence-style option | Captures ordered event patterns through n-grams |
| LSTM-compatible artifact | Sequence-style option | Represents sequential event context |
| LightGBM | Optional boosted model | Fast tree-based classification |
| XGBoost | Optional boosted model | Strong gradient boosting performance |
| Ensemble | Combines available artifacts | Reduces dependency on one model |

Compared with literature, the project prioritizes integration and usability over proposing a new algorithm. Its contribution is a working platform that connects ML detection with explanation and evidence presentation.

---

# Chapter 6: Conclusion and Future Scope

## 6.1 Summary of Work and Achievements

The project implemented a complete AI-assisted incident intelligence platform for HDFS logs. Major achievements include:

- HDFS event anomaly detection using trained model artifacts.
- Event mapping manual for developer interpretation.
- Flask/React web UI with responsive dashboard.
- Streamlit dashboard.
- Local Ollama-based Developer Debug Brief.
- Sample comparison page.
- Incident history and report export.
- Visual graphs for severity and event sequence analysis.

No award, publication, accepted abstract, conference paper, journal paper, or patent has been claimed at this stage. These may be added later if achieved.

## 6.2 Impact on Society, Environmental Sustainability, Ethical Issues and Compliance

The system can support faster diagnosis of failures in distributed infrastructure. Faster debugging can reduce service downtime and improve dependability for users. The project is ethically designed as decision support: it does not automatically delete data, restart services, or modify live systems. Human validation is required before remediation.

Sustainability considerations include:

- Local inference can reduce external API dependency.
- Faster incident resolution can reduce repeated computation and unnecessary resource usage.
- The system should still be used responsibly because ML training and LLM inference consume compute resources.

## 6.3 Limitations of the Work

Limitations include:

- Evaluation is based mainly on the HDFS v1 dataset.
- Production deployment security is not fully implemented.
- Local authentication is suitable only for academic demonstration.
- LLM explanations may be incomplete or uncertain.
- Real-time streaming from live HDFS clusters is not implemented.
- Transformer/LSTM artifacts are compatible substitutes rather than full production deep-learning deployments.

## 6.4 Future Scope

Future improvements include:

- Real-time ingestion from live log streams.
- Production authentication and role-based access.
- Better transformer models trained in a stable deep-learning environment.
- Integration with alerting systems such as Slack, email, or incident management tools.
- More explainability methods such as SHAP for model contribution.
- Deployment packaging with Docker.
- Export of this report as a formatted Word/PDF file.

---

# References

[1] W. Xu, L. Huang, A. Fox, D. Patterson, and M. I. Jordan, "Detecting large-scale system problems by mining console logs," in *Proc. ACM SIGOPS 22nd Symposium on Operating Systems Principles*, 2009, pp. 117-132, doi: 10.1145/1629575.1629587.

[2] P. He, J. Zhu, Z. Zheng, and M. R. Lyu, "Drain: An online log parsing approach with fixed depth tree," in *Proc. IEEE International Conference on Web Services*, 2017, doi: 10.1109/ICWS.2017.13.

[3] M. Du, F. Li, G. Zheng, and V. Srikumar, "DeepLog: Anomaly detection and diagnosis from system logs through deep learning," in *Proc. ACM CCS*, 2017, doi: 10.1145/3133956.3134015.

[4] H. Guo, S. Yuan, and X. Wu, "LogBERT: Log anomaly detection via BERT," in *Proc. International Joint Conference on Neural Networks*, 2021, doi: 10.1109/IJCNN52387.2021.9534113.

[5] Y. Lee, J. Kim, and P. Kang, "LAnoBERT: System log anomaly detection based on BERT masked language model," *Applied Soft Computing*, vol. 146, Art. no. 110689, 2023, doi: 10.1016/j.asoc.2023.110689.

[6] A. H. Shah, D. Pasha, E. H. Zadeh, and S. Konur, "Automated log analysis and anomaly detection using machine learning," *Fuzzy Systems and Data Mining VIII*, 2022, doi: 10.3233/FAIA220378.

[7] J. Zhu, S. He, P. He, J. Liu, and M. R. Lyu, "Loghub: A large collection of system log datasets for AI-driven log analytics," in *Proc. ISSRE*, 2023.

[8] LogPAI, "Loghub: A large collection of system log datasets for AI-driven log analytics," GitHub repository. [Online]. Available: https://github.com/logpai/loghub

[9] Streamlit, "Streamlit documentation." [Online]. Available: https://docs.streamlit.io/

[10] Flask, "Flask documentation." [Online]. Available: https://flask.palletsprojects.com/

[11] Ollama, "Ollama documentation." [Online]. Available: https://ollama.com/

[12] Scikit-learn Developers, "Scikit-learn documentation." [Online]. Available: https://scikit-learn.org/

> Recent-reference note: References [4], [5], [6], and [7] are from 2021-2023. Add more 2024-2026 journal papers before final binding if your department strictly requires at least 50% recent journal-only references.

---

# Appendices

## Appendix A: Important Commands

Run Streamlit dashboard:

```bash
streamlit run app.py
```

Run Flask/React dashboard:

```bash
python3 api_server.py
```

Train RandomForest artifact:

```bash
python3 train_hdfs_models.py
```

Train optional artifacts:

```bash
python3 train_transformer_artifact.py
python3 train_lstm_xgboost_artifacts.py
```

## Appendix B: Important File Paths

| File | Purpose |
|---|---|
| `app.py` | Streamlit dashboard |
| `web/index.html` | React/Tailwind UI |
| `api_server.py` | Flask app entry point |
| `server/analysis.py` | Analysis workflow |
| `server/llm.py` | Ollama prompt and streaming |
| `inference/detector.py` | Model inference |
| `inference/hdfs_data.py` | Dataset loading |
| `inference/event_mapper.py` | Event-template mapping |
| `artifacts/` | Model artifacts and local state |

## Appendix C: Formatting Specifications

| Feature | Requirement |
|---|---|
| Paper Size | A4, White |
| Font Style | Times New Roman |
| Font Size | 12 pt body, 14 pt sub-headings, 16 pt chapter titles |
| Line Spacing | 1.5 |
| Margins | 2 cm on all sides |
| Page Numbering | Bottom-centre; Roman for prelims, Arabic for chapters |
| Binding | Spiral |

---

# Annexure

## Outcome of the Report

The project outcome is a working software application/product prototype:

- Streamlit dashboard.
- Flask/React dashboard.
- HDFS anomaly detection pipeline.
- Local explanation and report generation.

Proof to attach:

- Screenshots of dashboard.
- Screenshots of generated report.
- Git repository snapshot.
- Model artifact list.
- Demonstration video or deployment link, if available.

## Sustainability Statement

The project supports sustainable digital operations by reducing the time needed to diagnose system failures. Early identification of anomalous log patterns can reduce repeated debugging cycles, unnecessary compute use, and prolonged service disruption. The system uses local inference where possible, limiting external data transfer. However, model training and LLM inference consume computational resources, so the platform should be used responsibly and optimized before large-scale deployment.

## Team Roles

| Team Member | Role | Contribution |
|---|---|---|
| Student A | Data and preprocessing | Dataset study, event trace preparation, EDA |
| Student B | Model development | Training RandomForest, LightGBM, XGBoost, sequence artifacts |
| Student C | Application and UI | Streamlit/Flask dashboard, LLM integration, report generation |

> Replace Student A/B/C with actual names and precise contributions.

## Final Review Checklist

- [ ] No spelling or grammatical errors.
- [ ] Consistent formatting throughout the document.
- [ ] All figures are numbered, captioned, and referred to in text.
- [ ] Figure captions are placed below figures.
- [ ] All tables are numbered, titled, and referred to in text.
- [ ] Table titles are placed above tables.
- [ ] All equations, if added, are numbered and referred to.
- [ ] No section is empty or incomplete.
- [ ] References follow IEEE format.
- [ ] At least 50% of references are recent, as required by the department.
- [ ] Certificate and declaration are signed before submission.
