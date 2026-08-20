import os

from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    # threaded=True per §5.2 -- required so background ingestion (Phase 3)
    # doesn't block chat requests from other users while a PDF is processing.
    app.run(host="0.0.0.0", port=5000, debug=app.config.get("DEBUG", False), threaded=True)
