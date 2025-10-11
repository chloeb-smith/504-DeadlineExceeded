import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()


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

    @app.get("/api/assignments")
    def assignments():
        canvas_base = os.getenv("CANVAS_API_BASE", "").rstrip("/")
        canvas_token = os.getenv("CANVAS_API_TOKEN", "")

        if not canvas_base or not canvas_token:
            return jsonify(_mock_assignments_payload()), 200

        try:
            data = _fetch_canvas_assignments(canvas_base, canvas_token)
            return jsonify(data), 200
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response else 502
            return (
                jsonify(
                    {
                        "error": "Failed to fetch assignments from Canvas.",
                        "details": str(exc),
                        "status": status_code,
                    }
                ),
                status_code,
            )
        except Exception as exc:  # pylint: disable=broad-except
            return (
                jsonify(
                    {
                        "error": "Unexpected error while pulling assignments.",
                        "details": str(exc),
                    }
                ),
                500,
            )

    return app


def _fetch_canvas_assignments(canvas_base: str, canvas_token: str) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {canvas_token}",
        "Accept": "application/json",
    }

    courses_url = f"{canvas_base}/api/v1/courses"
    courses_response = requests.get(
        courses_url,
        headers=headers,
        params={
            "enrollment_state": "active",
            "include[]": ["term"],
            "per_page": 100,
        },
        timeout=20,
    )
    courses_response.raise_for_status()
    courses = courses_response.json()

    result_courses: List[Dict[str, Any]] = []
    for course in courses:
        course_id = course.get("id")
        if not course_id:
            continue
        course_name = course.get("name") or course.get("course_code") or f"Course {course_id}"

        assignments_url = f"{canvas_base}/api/v1/courses/{course_id}/assignments"
        assignments_response = requests.get(
            assignments_url,
            headers=headers,
            params={
                "bucket": "upcoming",
                "include[]": ["submission"],
                "order_by": "due_at",
                "per_page": 50,
            },
            timeout=20,
        )
        assignments_response.raise_for_status()
        raw_assignments = assignments_response.json()

        normalized_assignments = [
            _normalize_assignment(assignment, course_id, course_name)
            for assignment in raw_assignments
            if assignment.get("due_at")
        ]

        if normalized_assignments:
            result_courses.append(
                {
                    "id": course_id,
                    "name": course_name,
                    "course_code": course.get("course_code"),
                    "assignments": normalized_assignments,
                }
            )

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "courses": result_courses,
    }


def _normalize_assignment(
    assignment: Dict[str, Any], course_id: int, course_name: str
) -> Dict[str, Any]:
    due_at = assignment.get("due_at")
    return {
        "id": assignment.get("id"),
        "name": assignment.get("name"),
        "description": assignment.get("description"),
        "due_at": due_at,
        "due_at_display": _format_datetime(due_at),
        "html_url": assignment.get("html_url"),
        "points_possible": assignment.get("points_possible"),
        "course_id": course_id,
        "course_name": course_name,
    }


def _format_datetime(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%b %d, %Y - %I:%M %p")
    except ValueError:
        return value


def _mock_assignments_payload() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)

    def build_due(offset_days: int, hour: int, minute: int) -> Dict[str, str]:
        due_time = (
            now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=offset_days)
        )
        return {
            "iso": due_time.isoformat(),
            "display": due_time.astimezone().strftime("%b %d, %Y - %I:%M %p"),
        }

    due_primary = build_due(2, 17, 0)
    due_quiz = build_due(4, 23, 59)
    due_lit = build_due(6, 9, 30)

    sample_courses = [
        {
            "id": 101,
            "name": "Environmental Science 201",
            "course_code": "ENV-201",
            "assignments": [
                {
                    "id": 1001,
                    "name": "Climate Change Case Study",
                    "description": "Analyze recent data trends and submit a three-page report.",
                    "due_at": due_primary["iso"],
                    "due_at_display": due_primary["display"],
                    "html_url": "https://canvas.example.com/courses/101/assignments/1001",
                    "points_possible": 50,
                    "course_id": 101,
                    "course_name": "Environmental Science 201",
                },
                {
                    "id": 1002,
                    "name": "Weekly Quiz 5",
                    "description": "Covers chapters 9 and 10.",
                    "due_at": due_quiz["iso"],
                    "due_at_display": due_quiz["display"],
                    "html_url": "https://canvas.example.com/courses/101/assignments/1002",
                    "points_possible": 20,
                    "course_id": 101,
                    "course_name": "Environmental Science 201",
                },
            ],
        },
        {
            "id": 202,
            "name": "Modern Literature 150",
            "course_code": "LIT-150",
            "assignments": [
                {
                    "id": 2001,
                    "name": "Poetry Analysis Draft",
                    "description": "First draft of the poetry analysis essay.",
                    "due_at": due_lit["iso"],
                    "due_at_display": due_lit["display"],
                    "html_url": "https://canvas.example.com/courses/202/assignments/2001",
                    "points_possible": 40,
                    "course_id": 202,
                    "course_name": "Modern Literature 150",
                }
            ],
        },
    ]

    return {"fetched_at": now.isoformat(), "courses": sample_courses}


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
