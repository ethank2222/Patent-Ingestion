from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, send_from_directory

from .config import Config
from .extensions import cors, db
from .routes.admin import admin_bp
from .routes.health import health_bp
from .routes.patents import patents_bp
from .routes.summaries import summaries_bp
from .services.ingestion_service import IngestionService


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="")
    settings = Config.load()
    app.settings = settings

    app.config["SECRET_KEY"] = settings.secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(patents_bp, url_prefix="/api")
    app.register_blueprint(summaries_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api")

    @app.get("/")
    def serve_root():
        index_file = Path(app.static_folder or "").joinpath("index.html")
        if index_file.exists():
            return app.send_static_file("index.html")
        return {"message": "API is running. Frontend assets are not built yet."}, 200

    @app.get("/<path:path>")
    def serve_spa(path: str):
        if path == "api" or path.startswith("api/"):
            abort(404)
        static_path = Path(app.static_folder or "").joinpath(path)
        if static_path.exists():
            return send_from_directory(app.static_folder, path)
        index_file = Path(app.static_folder or "").joinpath("index.html")
        if index_file.exists():
            return app.send_static_file("index.html")
        abort(404)

    @app.cli.command("init-db")
    def init_db_command() -> None:
        with app.app_context():
            db.create_all()
            print("Database initialized.")

    @app.cli.command("ingest-recent")
    def ingest_recent_command() -> None:
        with app.app_context():
            service = IngestionService(settings)
            result = service.ingest_recent()
            print(result)

    with app.app_context():
        # Lightweight safeguard for first boot in greenfield environments.
        db.create_all()

    return app
