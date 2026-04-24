from flask import Flask, jsonify, request
from extensions import db, cors
from config import Config
import logging
import sys

from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt

from models.token_blocklist import TokenBlocklist

# IMPORT ALL MODELS
from models.user import User
from models.conversation import Conversation
from models.message import Message
from models.summary import Summary
from models.entity import Entity
from models.kg_triple import KGTriple

# Routes import
from routes.conversations import conversations_bp
from routes.messages import messages_bp
from routes.personas import personas_bp
from routes.memory import memory_bp
from routes.export import export_bp
from routes.health import health_bp
from routes.auth import auth_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ---------------- INIT EXTENSIONS ----------------
    db.init_app(app)

    # FIXED CORS CONFIG (IMPORTANT)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": "http://localhost:5173"}},
        supports_credentials=True,
    )

    # AUTH EXTENSIONS INIT
    bcrypt = Bcrypt(app)
    jwt = JWTManager(app)

    # HANDLE PREFLIGHT (OPTIONS) REQUESTS GLOBALLY
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            return jsonify({"ok": True}), 200

    # JWT BLOCKLIST CHECK (LOGOUT SUPPORT)
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        token = TokenBlocklist.query.filter_by(jti=jti).first()
        return token is not None

    # JWT ERROR HANDLERS (NO REDIRECT ISSUE)
    @jwt.unauthorized_loader
    def unauthorized_callback(err):
        return jsonify({"error": "Missing or invalid token"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(err):
        return jsonify({"error": "Invalid token"}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token expired"}), 401

    # ---------------- LOGGING SETUP ----------------
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # ---------------- REGISTER BLUEPRINTS ----------------
    app.register_blueprint(conversations_bp, url_prefix="/api/conversations")
    app.register_blueprint(messages_bp, url_prefix="/api/messages")
    app.register_blueprint(personas_bp, url_prefix="/api/personas")
    app.register_blueprint(memory_bp, url_prefix="/api/memory")
    app.register_blueprint(export_bp, url_prefix="/api/export")
    app.register_blueprint(health_bp, url_prefix="/api/health")

    # Auth Routes
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    # ---------------- GLOBAL ERROR HANDLER ----------------
    @app.errorhandler(Exception)
    def handle_exception(e):
        logging.error(f"[GLOBAL ERROR] {str(e)}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

    # ---------------- DATABASE INIT ----------------
    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()

    # ENV BASED RUN (IMPORTANT)
    debug_mode = app.config.get("DEBUG", False)

    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
