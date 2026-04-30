import urllib.error

import pandas as pd
from flask import Response, jsonify, request, send_from_directory, stream_with_context

from inference.detector import MODEL_OPTIONS
from inference.incident_store import load_incident_history
from server.analysis import analyze_events
from server.auth import create_user, require_user, verify_user
from server.config import HISTORY_PATH, WEB_ROOT
from server.llm import fallback_explanation, ollama_prompt, stream_ollama_text
from server.presentation import build_history_summary, event_manual_rows


def register_routes(app):
    @app.get("/")
    def index():
        return send_from_directory(WEB_ROOT, "index.html")

    @app.post("/api/auth/signup")
    def signup():
        payload = request.get_json(force=True)
        ok, message, username = create_user(
            str(payload.get("username", "")),
            str(payload.get("password", "")),
        )
        if ok:
            return jsonify({"ok": True, "user": username})
        status = 409 if message == "That username already exists." else 400
        return jsonify({"ok": False, "message": message}), status

    @app.post("/api/auth/login")
    def login():
        payload = request.get_json(force=True)
        username = str(payload.get("username", "")).strip().lower()
        password = str(payload.get("password", ""))
        if verify_user(username, password):
            return jsonify({"ok": True, "user": username})
        return jsonify({"ok": False, "message": "Invalid username or password."}), 401

    @app.get("/api/manual")
    def manual():
        return jsonify({"rows": event_manual_rows()})

    @app.get("/api/history/<user>")
    def history(user):
        history_df = load_incident_history(limit=200, user=user.strip().lower())
        return jsonify(
            {
                "summary": build_history_summary(history_df),
                "rows": history_df.drop(columns=["User"], errors="ignore").fillna("").to_dict("records"),
            }
        )

    @app.post("/api/history/delete")
    def delete_history():
        payload = request.get_json(force=True)
        user = require_user(payload)
        if not user:
            return jsonify({"ok": False, "message": "Sign in before deleting history."}), 401

        if not HISTORY_PATH.exists():
            return jsonify({"ok": True, "message": "No history found to delete."})

        history_df = pd.read_csv(HISTORY_PATH)
        if "User" not in history_df.columns:
            HISTORY_PATH.unlink()
            return jsonify({"ok": True, "message": "Incident history deleted."})

        remaining = history_df[history_df["User"].fillna("") != user]
        if remaining.empty:
            HISTORY_PATH.unlink()
        else:
            remaining.to_csv(HISTORY_PATH, index=False)

        return jsonify({"ok": True, "message": "Your incident history was deleted."})

    @app.post("/api/cache/clear")
    def clear_cache():
        return jsonify({"ok": True, "message": "Runtime cache cleared."})

    @app.post("/api/analyze")
    def analyze():
        payload = request.get_json(force=True)
        user = require_user(payload)
        if not user:
            return jsonify({"ok": False, "message": "Sign in before running analysis."}), 401

        model_name = payload.get("modelName", "random_forest")
        if model_name not in MODEL_OPTIONS:
            return jsonify({"ok": False, "message": "Unknown detector selected."}), 400

        try:
            return jsonify(analyze_events(payload, user))
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/explain/stream")
    def explain_stream():
        payload = request.get_json(force=True)
        user = require_user(payload)
        if not user:
            return jsonify({"ok": False, "message": "Sign in before generating an explanation."}), 401

        def generate():
            try:
                for chunk in stream_ollama_text(ollama_prompt(payload)):
                    yield chunk
            except (urllib.error.URLError, TimeoutError, OSError):
                text = fallback_explanation(payload)
                for paragraph in text.split("\n\n"):
                    yield paragraph + "\n\n"

        return Response(stream_with_context(generate()), mimetype="text/plain")

