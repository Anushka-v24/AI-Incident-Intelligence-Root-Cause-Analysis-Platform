import hashlib
import json
import secrets
from datetime import datetime

from server.config import USERS_PATH


def load_users():
    if not USERS_PATH.exists():
        return {}
    try:
        return json.loads(USERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_users(users):
    USERS_PATH.parent.mkdir(exist_ok=True)
    USERS_PATH.write_text(json.dumps(users, indent=2), encoding="utf-8")


def password_hash(password, salt):
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def create_user(username, password):
    username = username.strip().lower()
    if not username:
        return False, "Enter a username.", None
    if len(password) < 6:
        return False, "Use at least 6 characters for the password.", None

    users = load_users()
    if username in users:
        return False, "That username already exists.", None

    salt = secrets.token_hex(16)
    users[username] = {
        "salt": salt,
        "password_hash": password_hash(password, salt),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_users(users)
    return True, "", username


def verify_user(username, password):
    username = username.strip().lower()
    user = load_users().get(username)
    if not user:
        return False
    return secrets.compare_digest(user["password_hash"], password_hash(password, user["salt"]))


def require_user(payload):
    username = str(payload.get("user", "")).strip().lower()
    if not username or username not in load_users():
        return None
    return username

