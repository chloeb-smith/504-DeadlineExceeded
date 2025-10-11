import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from canvas import canvas_get
from store import add_item, list_items

load_dotenv()

DEV_UID = os.getenv("DEV_UID", "dev-user-1")


def _get_canvas_config():
    """Return Canvas API base URL and token from environment, if available."""
    base = (os.getenv("CANVAS_BASE_URL") or "").rstrip("/")
    token = os.getenv("CANVAS_TOKEN")
    return base, token


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-me")

    CORS(
        app,
        resources={r"/api/*": {"origins": os.getenv("CORS_ORIGIN", "http://localhost:5173")}},
        supports_credentials=True,
    )

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/hello")
    def hello():
        return jsonify({"message": "Hello from Flask API"})

    @app.post("/api/items")
    def create_item():
        title = (request.get_json() or {}).get("title", "Untitled")
        add_item(DEV_UID, title)
        return {"ok": True}

    @app.get("/api/items")
    def items():
        return jsonify(list_items(DEV_UID))

    @app.get("/api/canvas/me/upcoming")
    def canvas_upcoming():
        base, token = _get_canvas_config()
        if not (base and token):
            return {"error": "Canvas not configured"}, 500
        data = canvas_get(base, token, "/api/v1/users/self/upcoming_events")
        return jsonify(data)

    @app.get("/api/canvas/courses")
    def canvas_courses():
        base, token = _get_canvas_config()
        if not (base and token):
            return {"error": "Canvas not configured"}, 500
        data = canvas_get(base, token, "/api/v1/courses", {"per_page": 50})
        return jsonify(data)

    @app.get("/api/canvas/courses/<int:course_id>/assignments")
    def canvas_assignments(course_id: int):
        base, token = _get_canvas_config()
        if not (base and token):
            return {"error": "Canvas not configured"}, 500
        data = canvas_get(
            base,
            token,
            f"/api/v1/courses/{course_id}/assignments",
            {"per_page": 100, "include[]": ["submission"]},
        )
        return jsonify(data)

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
