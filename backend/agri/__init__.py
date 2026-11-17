"""AgriExpert API: one Flask app for the whole farming assistant."""
from __future__ import annotations

import secrets
import threading
import time

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from .config import APP_DATA_DIR, Config


def _secret() -> str:
    """Use JWT_SECRET from .env; otherwise make one once and keep it in app_data/."""
    if Config.JWT_SECRET and len(Config.JWT_SECRET) >= 32:
        return Config.JWT_SECRET
    path = APP_DATA_DIR / "jwt_secret.txt"
    if path.exists():
        return path.read_text().strip()
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(48)
    path.write_text(value)
    print("[config] JWT_SECRET not set: generated one in app_data/jwt_secret.txt")
    return value


def create_app(testing: bool = False) -> Flask:
    from .core import ApiError
    from .db import get_db, save_local
    from .routes import api

    if not testing:
        Config.JWT_SECRET = _secret()
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_MB * 1024 * 1024
    app.config["TESTING"] = testing
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.register_blueprint(api)

    @app.errorhandler(ApiError)
    def api_error(err):
        return jsonify({"error": err.message}), err.status

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_):
        return jsonify({"error": f"File is too large (limit {Config.MAX_UPLOAD_MB} MB)"}), 413

    @app.errorhandler(HTTPException)
    def http_error(err):
        return jsonify({"error": err.description or err.name}), err.code

    @app.errorhandler(Exception)
    def unexpected(err):
        app.logger.exception(err)
        return jsonify({"error": "Something went wrong on the server. Please try again."}), 500

    # Serve the built React app (frontend/dist) so the whole product runs as one process.
    dist = Config.FRONTEND_DIST

    @app.get("/")
    @app.get("/<path:path>")
    def spa(path=""):
        if path.startswith("api/"):
            return jsonify({"error": "Not found"}), 404
        if not dist.exists():
            return ("Frontend not built yet. Run `npm run build` in frontend/, or use `npm run dev` "
                    "and open http://localhost:5173."), 200
        target = dist / path
        if path and target.is_file():
            return send_from_directory(dist, path)
        return send_from_directory(dist, "index.html")

    get_db()  # connect at start-up so a bad MONGO_URI fails loudly
    if Config.DB_MODE == "local" and not testing:
        def saver():
            while True:
                time.sleep(3)
                try:
                    save_local()
                except Exception as exc:  # keep the app running; report the problem
                    print(f"[db] could not save: {exc}")
        threading.Thread(target=saver, daemon=True).start()
    return app
