"""Minimal Flask application for quick Cloud Run startup."""

import logging
import os
import sys

from flask import Flask, jsonify


def create_app() -> Flask:
    """Create minimal Flask application."""
    app = Flask(__name__)

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    @app.route("/health")
    def health():
        """Health check endpoint."""
        return jsonify(
            {"status": "healthy", "service": "Squeeze Bot", "version": "1.0.0"}
        )

    @app.route("/")
    def index():
        """Root endpoint."""
        return jsonify(
            {"service": "Squeeze Hunter Bot", "status": "running", "mode": "minimal"}
        )

    @app.route("/api/signals")
    def get_signals():
        """Minimal signals endpoint."""
        return jsonify(
            {
                "status": "success",
                "message": "Minimal mode - full services loading...",
                "scan_summary": {"total": 0},
            }
        )

    logger.info("Minimal Flask app initialized")
    return app


if __name__ == "__main__":
    try:
        print("Starting Squeeze Bot (Minimal Mode)...")
        app = create_app()
        port = int(os.getenv("PORT", 8080))
        app.run(host="0.0.0.0", port=port, debug=False)
    except Exception as e:
        print(f"Failed to start: {str(e)}")
        sys.exit(1)
