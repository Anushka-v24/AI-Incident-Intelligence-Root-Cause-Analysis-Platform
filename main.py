# main.py

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
os.environ.setdefault("CREWAI_STORAGE_DIR", str(PROJECT_ROOT / ".crewai_storage"))
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

from inference.event_mapper import EventMapper
from llm.llm_explainer import OllamaLLM
from agents.crew_setup import DebugCrew

# =========================
# 1. INPUT (Simulated events from model)
# =========================
# Later this will come from Transformer automatically
events = ["E12", "E4"]

# =========================
# 2. EVENT MAPPING
# =========================
mapper = EventMapper("dataset/HDFS_v1/preprocessed/HDFS.log_templates.csv")

mapped_events = mapper.map_events(events)

print("\n🔍 Mapped Events:")
for e in mapped_events:
    print("-", e)

# =========================
# 3. INITIALIZE LLM (OLLAMA)
# =========================
llm = OllamaLLM(model="llama3")

# =========================
# 4. RUN CREWAI SYSTEM
# =========================
crew = DebugCrew(llm=llm)

result = crew.run(mapped_events)

# =========================
# 5. FINAL OUTPUT
# =========================
print("\n🚨 FINAL AI DEBUGGER OUTPUT:\n")
print(result)
