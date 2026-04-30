from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"
USERS_PATH = ARTIFACTS_ROOT / "users.json"
HISTORY_PATH = ARTIFACTS_ROOT / "incident_history.csv"

