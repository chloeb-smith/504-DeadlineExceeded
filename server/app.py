import calendar
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


def _get_term_grace_period_days() -> int:
    raw = os.getenv("CANVAS_TERM_GRACE_DAYS")
    if not raw:
        return 14
    try:
        value = int(raw)
        return value if value >= 0 else 14
    except ValueError:
        return 14


def _get_max_course_age_days() -> int:
    raw = os.getenv("CANVAS_MAX_COURSE_AGE_DAYS")
    if not raw:
        return 150
    try:
        value = int(raw)
        return value if value > 0 else 150
    except ValueError:
        return 150


def _shift_months(dt: datetime, months: int) -> datetime:
    """Return dt shifted by a number of calendar months, clamping the day."""
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _assignment_window(now: datetime) -> Tuple[datetime, datetime, int, int]:
    raw_lookahead_days = os.getenv("CANVAS_ASSIGNMENT_LOOKAHEAD_DAYS")
    raw_lookback_days = os.getenv("CANVAS_ASSIGNMENT_LOOKBACK_DAYS")

    if raw_lookahead_days or raw_lookback_days:
        # Allow overriding with explicit day counts.
        try:
            lookahead_days = int(raw_lookahead_days) if raw_lookahead_days else 90
        except ValueError:
            lookahead_days = 90
        try:
            lookback_days = int(raw_lookback_days) if raw_lookback_days else 30
        except ValueError:
            lookback_days = 30
        lookahead_days = max(1, lookahead_days)
        lookback_days = max(0, lookback_days)
        window_start = now - timedelta(days=lookback_days)
        window_end = now + timedelta(days=lookahead_days)
        return window_start, window_end, lookback_days, lookahead_days

    raw_lookahead_months = os.getenv("CANVAS_ASSIGNMENT_LOOKAHEAD_MONTHS")
    raw_lookback_months = os.getenv("CANVAS_ASSIGNMENT_LOOKBACK_MONTHS")
    try:
        lookahead_months = int(raw_lookahead_months) if raw_lookahead_months else 3
    except ValueError:
        lookahead_months = 3
    try:
        lookback_months = int(raw_lookback_months) if raw_lookback_months else 1
    except ValueError:
        lookback_months = 1
    lookahead_months = max(1, lookahead_months)
    lookback_months = max(0, lookback_months)

    window_start = _shift_months(now, -lookback_months)
    window_end = _shift_months(now, lookahead_months)

    lookback_days = max(0, int((now - window_start).total_seconds() // 86400))
    lookahead_days = max(1, int((window_end - now).total_seconds() // 86400))
    return window_start, window_end, lookback_days, lookahead_days


def _course_term_dates(course: Dict[str, Any]) -> Tuple[Optional[datetime], Optional[datetime]]:
    term = course.get("term") or {}
    start = (
        _parse_canvas_datetime(term.get("start_at"))
        or _parse_canvas_datetime(course.get("start_at"))
        or _parse_canvas_datetime(course.get("created_at"))
    )
    end = (
        _parse_canvas_datetime(term.get("end_at"))
        or _parse_canvas_datetime(course.get("end_at"))
        or _parse_canvas_datetime(course.get("conclude_at"))
    )
    return start, end


def _parse_first_datetime(values: Iterable[Optional[str]]) -> Optional[datetime]:
    for value in values:
        parsed = _parse_canvas_datetime(value)
        if parsed:
            return parsed
    return None


def _course_recent_activity(course: Dict[str, Any]) -> Optional[datetime]:
    enrollments = course.get("enrollments") or []
    enrollment_activity = _parse_first_datetime(
        enrollment.get("last_activity_at") for enrollment in enrollments
    )
    if enrollment_activity:
        return enrollment_activity

    return _parse_first_datetime(
        [
            course.get("last_activity_at"),
            course.get("updated_at"),
            course.get("created_at"),
        ]
    )


def _is_current_course(course: Dict[str, Any], now: datetime) -> bool:
    # Allow a configurable grace window so recently-ended courses stay visible briefly.
    grace_days = _get_term_grace_period_days()
    grace = timedelta(days=grace_days)
    age_limit = timedelta(days=_get_max_course_age_days())
    start, end = _course_term_dates(course)

    if end and now > end + grace:
        return False
    if start and now < start - grace:
        return False

    if not end:
        recent_activity = _course_recent_activity(course)
        if recent_activity and now - recent_activity > grace + age_limit:
            return False
        if not recent_activity and start and now - start > grace + age_limit:
            return False

    return True


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
        params = {
            "per_page": 100,
            "enrollment_state[]": ["active", "invited_or_pending"],
            "include[]": ["favorites", "term", "enrollments"],
            "state[]": ["available", "completed"],
        }
        courses = canvas_get(base, token, "/api/v1/courses", params, paginate=True)
        now_utc = datetime.now(timezone.utc)
        return jsonify(courses)

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
        window_start, window_end, lookback_days, lookahead_days = _assignment_window(now_utc)

        try:
            courses = canvas_get(
                base,
                token,
                "/api/v1/courses",
                {
                    "per_page": 100,
                    "enrollment_state[]": ["active", "invited_or_pending"],
                    "include[]": ["favorites", "term", "enrollments"],
                    "state[]": ["available", "completed"],
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
            if course.get("workflow_state") == "deleted":
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
                if due_at < window_start or due_at > window_end:
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
            earliest_due_at = normalized[0]["due_at"] if normalized else None
            response_courses.append(
                {
                    "id": course_id,
                    "name": course.get("name"),
                    "course_code": course.get("course_code"),
                    "assignments": normalized,
                    "assignments_in_window": len(normalized),
                    "earliest_due_at": earliest_due_at,
                }
            )

        payload: Dict[str, Any] = {
            "fetched_at": now_utc.isoformat(),
            "window": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
                "lookback_days": lookback_days,
                "lookahead_days": lookahead_days,
            },
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
