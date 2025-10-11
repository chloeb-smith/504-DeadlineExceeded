import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from requests import HTTPError

from canvas import canvas_get
from store import add_item, list_items

load_dotenv()

DEV_UID = os.getenv("DEV_UID", "dev-user-1")


def _get_canvas_config():
    """Return Canvas API base URL and token from environment, if available."""
    base = (os.getenv("CANVAS_BASE_URL") or "").rstrip("/")
    token = os.getenv("CANVAS_TOKEN")
    return base, token


def _parse_canvas_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    adjusted = value
    if adjusted.endswith("Z"):
        adjusted = adjusted[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(adjusted)
    except ValueError:
        return None


def _format_due_display(due_at: datetime) -> str:
    local_dt = due_at.astimezone()
    date_str = local_dt.strftime("%b %d, %Y")
    time_str = local_dt.strftime("%I:%M %p")
    if time_str.startswith("0"):
        time_str = time_str[1:]
    tz = local_dt.tzname() or ""
    if tz:
        return f"{date_str} • {time_str} {tz}"
    return f"{date_str} • {time_str}"


def _get_upcoming_window_days() -> int:
    raw = os.getenv("CANVAS_UPCOMING_WINDOW_DAYS")
    if not raw:
        return 60
    try:
        value = int(raw)
        return value if value > 0 else 60
    except ValueError:
        return 60


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
            {"per_page": 100, "include[]": ["submission"], "order_by": "due_at"},
            paginate=True,
        )
        return jsonify(data)

    @app.get("/api/assignments")
    def canvas_assignments_summary():
        base, token = _get_canvas_config()
        if not (base and token):
            return {"error": "Canvas not configured"}, 500

        now_utc = datetime.now(timezone.utc)
        window_end = now_utc + timedelta(days=_get_upcoming_window_days())

        try:
            courses = canvas_get(
                base,
                token,
                "/api/v1/courses",
                {
                    "per_page": 100,
                    "enrollment_state": "active",
                    "include[]": ["favorites"],
                },
                paginate=True,
            )
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 502
            message = "Canvas API request failed while loading courses"
            return {"error": message, "status": status}, status

        response_courses: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        for course in courses:
            course_id = course.get("id")
            if not course_id:
                continue
            if course.get("workflow_state") in {"completed", "deleted"}:
                continue

            try:
                assignments = canvas_get(
                    base,
                    token,
                    f"/api/v1/courses/{course_id}/assignments",
                    {
                        "per_page": 100,
                        "order_by": "due_at",
                        "include[]": ["submission"],
                    },
                    paginate=True,
                )
            except HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 502
                warnings.append(
                    {
                        "course_id": course_id,
                        "status": status,
                        "message": f"Failed to load assignments for course {course_id}",
                    }
                )
                continue

            normalized: List[Dict[str, Any]] = []
            for assignment in assignments:
                due_at_str = assignment.get("due_at")
                due_at = _parse_canvas_datetime(due_at_str)
                if due_at is None:
                    continue
                if due_at < now_utc or due_at > window_end:
                    continue
                normalized.append(
                    {
                        "id": assignment.get("id"),
                        "name": assignment.get("name"),
                        "description": assignment.get("description"),
                        "due_at": due_at.isoformat(),
                        "due_at_display": _format_due_display(due_at),
                        "html_url": assignment.get("html_url"),
                        "points_possible": assignment.get("points_possible"),
                        "course_id": course_id,
                        "course_name": course.get("name"),
                    }
                )

            normalized.sort(key=lambda item: item["due_at"])
            response_courses.append(
                {
                    "id": course_id,
                    "name": course.get("name"),
                    "course_code": course.get("course_code"),
                    "assignments": normalized,
                }
            )

        response_courses.sort(key=lambda item: item.get("name") or "")

        payload: Dict[str, Any] = {
            "fetched_at": now_utc.isoformat(),
            "courses": response_courses,
        }
        if warnings:
            payload["warnings"] = warnings
        return jsonify(payload)

    return app


if __name__ == "__main__":
    app = create_app()
    # port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=5173, debug=True)
