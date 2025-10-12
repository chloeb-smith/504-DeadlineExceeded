import calendar
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from requests import HTTPError

from assistant import GeminiConfigurationError, analyze_assignments, get_assignment_help
from auth_service import AuthServiceError, login_user, register_user
from canvas import canvas_get
from store import add_item, list_items

load_dotenv()
_RETRY_SECS_PATTERN = re.compile(r"retry (?:in|after)\s+([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE)

DEV_UID = os.getenv("DEV_UID", "dev-user-1")
CANVAS_CACHE_SECONDS = max(0, int(os.getenv("CANVAS_CACHE_SECONDS", "120")))
CANVAS_MAX_WORKERS = max(1, int(os.getenv("CANVAS_MAX_WORKERS", "4")))
_assignments_cache: Dict[str, Dict[str, Any]] = {}
_assignments_cache_lock = Lock()


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
        return f"{date_str} - {time_str} {tz}"
    return f"{date_str} - {time_str}"



def _assignments_cache_key(token: str, window_start: datetime, window_end: datetime) -> str:
    return f"{token}:{window_start.date().isoformat()}:{window_end.date().isoformat()}"


def _get_cached_assignments(cache_key: str) -> Optional[Dict[str, Any]]:
    if CANVAS_CACHE_SECONDS <= 0:
        return None
    now_ts = time.time()
    with _assignments_cache_lock:
        entry = _assignments_cache.get(cache_key)
        if not entry:
            return None
        if now_ts - entry["timestamp"] > CANVAS_CACHE_SECONDS:
            _assignments_cache.pop(cache_key, None)
            return None
        return entry["payload"]


def _store_assignments_cache(cache_key: str, payload: Dict[str, Any]) -> None:
    if CANVAS_CACHE_SECONDS <= 0:
        return
    with _assignments_cache_lock:
        _assignments_cache[cache_key] = {"timestamp": time.time(), "payload": payload}
        if len(_assignments_cache) > 10:
            oldest_key = min(_assignments_cache, key=lambda key: _assignments_cache[key]["timestamp"])
            if oldest_key != cache_key:
                _assignments_cache.pop(oldest_key, None)


def _extract_retry_after_seconds(message: str) -> Optional[float]:
    match = _RETRY_SECS_PATTERN.search(message)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _get_past_due_grace_days() -> int:
    raw = os.getenv("CANVAS_PAST_DUE_GRACE_DAYS")
    if not raw:
        return 2
    try:
        value = int(raw)
        return value if value >= 0 else 2
    except ValueError:
        return 2

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

    @app.post("/api/auth/register")
    def auth_register():
        payload = request.get_json(silent=True) or {}
        email = (payload.get("email") or "").strip()
        password = payload.get("password") or ""
        display_name = payload.get("displayName")

        if not email or not password:
            return {"error": "invalid-argument", "message": "Email and password are required."}, 400

        try:
            profile = register_user(email=email, password=password, display_name=display_name)
            tokens = login_user(email=email, password=password)
        except AuthServiceError as exc:
            status_map = {
                "email-already-exists": 409,
                "invalid-argument": 400,
                "weak-password": 400,
                "configuration-error": 500,
                "network-error": 502,
            }
            status = status_map.get(exc.code, 400)
            return {"error": exc.code, "message": str(exc)}, status

        return jsonify({"profile": profile, "tokens": tokens}), 201

    @app.post("/api/auth/login")
    def auth_login():
        payload = request.get_json(silent=True) or {}
        email = (payload.get("email") or "").strip()
        password = payload.get("password") or ""

        if not email or not password:
            return {"error": "invalid-argument", "message": "Email and password are required."}, 400

        try:
            tokens = login_user(email=email, password=password)
        except AuthServiceError as exc:
            status_map = {
                "invalid-argument": 400,
                "invalid-credentials": 401,
                "access-denied": 403,
                "configuration-error": 500,
                "network-error": 502,
            }
            status = status_map.get(exc.code, 400)
            return {"error": exc.code, "message": str(exc)}, status

        return jsonify({"tokens": tokens}), 200

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
        past_due_grace_days = _get_past_due_grace_days()
        past_due_cutoff = now_utc - timedelta(days=past_due_grace_days)

        force_refresh = str(request.args.get("force", "")).lower() in {"1", "true", "yes", "refresh"}
        cache_key = _assignments_cache_key(token, window_start, window_end) if token else None
        if cache_key and not force_refresh:
            cached_payload = _get_cached_assignments(cache_key)
            if cached_payload is not None:
                return jsonify(cached_payload)
    
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

        raw_limit = os.getenv("CANVAS_MAX_ACTIVE_COURSES", "").strip()
        course_limit = 0
        if raw_limit:
            try:
                parsed = int(raw_limit)
                if parsed > 0:
                    course_limit = parsed
            except ValueError:
                course_limit = 0

        eligible_courses: List[Dict[str, Any]] = []
        for course in courses:
            course_id = course.get("id")
            if not course_id:
                continue
            if course.get("workflow_state") == "deleted":
                continue
            eligible_courses.append(course)
            if course_limit and len(eligible_courses) >= course_limit:
                break

        response_courses: List[Dict[str, Any]] = []
        analysis_candidates: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        def load_course(course: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
            course_id = course.get("id")
            if not course_id:
                return None, None
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
            except HTTPError as exc:  # Recovered later so other courses still load
                status = exc.response.status_code if exc.response is not None else 502
                return None, {
                    "course_id": course_id,
                    "status": status,
                    "message": f"Failed to load assignments for course {course_id}",
                }
    
            normalized: List[Dict[str, Any]] = []
            for assignment in assignments:
                due_at_str = assignment.get("due_at")
                due_at = _parse_canvas_datetime(due_at_str)
                if due_at is None:
                    continue
                if due_at < window_start or due_at > window_end:
                    continue
                if due_at < past_due_cutoff:
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
                        "course_code": course.get("course_code"),
                    }
                )
                analysis_candidates.append(
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
                        "course_code": course.get("course_code"),
                    }
                )
    
            normalized.sort(key=lambda item: item["due_at"])
            earliest_due_at = normalized[0]["due_at"] if normalized else None
            return (
                {
                    "id": course_id,
                    "name": course.get("name"),
                    "course_code": course.get("course_code"),
                    "assignments": normalized,
                    "assignments_in_window": len(normalized),
                    "earliest_due_at": earliest_due_at,
                },
                None,
            )
    
        if eligible_courses:
            max_workers = min(CANVAS_MAX_WORKERS, len(eligible_courses))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(load_course, course): course for course in eligible_courses}
                for future in as_completed(future_map):
                    try:
                        course_payload, warning = future.result()
                    except Exception as exc:  # pragma: no cover - defensive
                        course = future_map[future]
                        warnings.append(
                            {
                                "course_id": course.get("id"),
                                "status": 500,
                                "message": f"Unexpected error loading assignments for course {course.get('id')}: {exc}",
                            }
                        )
                        continue
                    if warning:
                        warnings.append(warning)
                    if course_payload:
                        response_courses.append(course_payload)
        else:
            response_courses = []
    
        response_courses.sort(key=lambda item: item.get("earliest_due_at") or "")
    
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

        if analysis_candidates:
            analysis_candidates.sort(key=lambda item: item.get("due_at") or "")
            analysis_candidates = analysis_candidates[:7]
            analysis_limit_raw = os.getenv("ASSIGNMENT_ANALYSIS_LIMIT", "").strip()
            chunk_size = 6
            if analysis_limit_raw:
                try:
                    parsed_limit = int(analysis_limit_raw)
                    if parsed_limit > 0:
                        chunk_size = parsed_limit
                    elif parsed_limit == 0:
                        chunk_size = len(analysis_candidates)
                except ValueError:
                    chunk_size = 6
            if chunk_size <= 0:
                chunk_size = len(analysis_candidates)

            aggregated: List[Dict[str, Any]] = []
            analysis_errors: List[str] = []
            generated_at: Optional[str] = None
            retry_after_seconds: Optional[float] = None

            for offset in range(0, len(analysis_candidates), chunk_size):
                chunk = analysis_candidates[offset : offset + chunk_size]
                if not chunk:
                    continue
                try:
                    chunk_result = analyze_assignments(chunk)
                except GeminiConfigurationError as exc:
                    analysis_errors.append(str(exc))
                    break
                except RuntimeError as exc:
                    error_message = str(exc)
                    analysis_errors.append(error_message)
                    if "429" in error_message:
                        retry_after = _extract_retry_after_seconds(error_message)
                        if retry_after is not None:
                            if retry_after_seconds is None:
                                retry_after_seconds = retry_after
                            else:
                                retry_after_seconds = max(retry_after_seconds, retry_after)
                        break
                    continue

                if chunk_result.get("generated_at"):
                    generated_at = chunk_result["generated_at"]
                aggregated.extend(chunk_result.get("assignments", []))

            if aggregated:
                payload["analysis"] = {
                    "generated_at": generated_at,
                    "assignments": aggregated,
                }
            if analysis_errors:
                payload["analysis_error"] = "; ".join(dict.fromkeys(analysis_errors))
            if retry_after_seconds is not None:
                payload["analysis_retry_after_seconds"] = round(retry_after_seconds, 2)

        if cache_key:
            _store_assignments_cache(cache_key, payload)

        return jsonify(payload)

    @app.post("/api/assistant/help")
    def assistant_help():
        payload = request.get_json(silent=True) or {}
        raw_keywords = payload.get("keywords") or []
        question = (payload.get("question") or "").strip()
        history = payload.get("history") or []

        if not question:
            if keywords or context_payload:
                question = "Provide detailed assignment planning guidance based on the supplied keywords and context."
                app.logger.info(
                    "assistant_help received empty question; using fallback prompt. payload=%s",
                    payload,
                )
            else:
                app.logger.warning("assistant_help rejected empty question payload: %s", payload)
                return {"error": "A question is required to generate guidance."}, 400

        if not isinstance(raw_keywords, list):
            app.logger.warning("assistant_help rejecting keywords=%s (not list)", raw_keywords)
            return {"error": "keywords must be an array of strings."}, 400
        keywords = []
        for keyword in raw_keywords[:25]:
            if isinstance(keyword, str):
                cleaned = keyword.strip()
                if cleaned:
                    keywords.append(cleaned)

        if history and not isinstance(history, list):
            app.logger.warning("assistant_help rejecting history=%s (not list)", history)
            return {"error": "history must be an array of messages."}, 400

        safe_history = []
        for message in (history or [])[-10:]:
            if not isinstance(message, dict):
                continue
            role = (message.get("role") or "").strip().lower()
            content = (message.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            safe_history.append({"role": role, "content": content})

        context_payload = payload.get("context")
        if context_payload is not None and not isinstance(context_payload, dict):
            app.logger.warning(
                "assistant_help rejecting context payload type=%s", type(context_payload).__name__
            )
            return {"error": "context must be an object."}, 400

        app.logger.debug(
            "assistant_help dispatch question='%s' keywords=%s context_courses=%s history_len=%s",
            question,
            keywords,
            len((context_payload or {}).get("courses", [])) if isinstance(context_payload, dict) else "n/a",
            len(safe_history),
        )

        try:
            result = get_assignment_help(
                keywords,
                question,
                history=safe_history,
                context=context_payload,
            )
        except GeminiConfigurationError as exc:
            return {"error": str(exc)}, 500
        except RuntimeError as exc:
            return {"error": str(exc)}, 502

        return jsonify(
            {
                "reply": result.text,
                "model": result.model,
                "keywords": keywords,
                "usage": result.usage,
                "history": safe_history,
            }
        )

    return app


if __name__ == "__main__":
    app = create_app()
    port_value = (
        os.getenv("BACKEND_PORT")
        or os.getenv("SERVER_PORT")
        or os.getenv("PORT")
        or "5050"
    )
    try:
        port = int(port_value)
    except (TypeError, ValueError):
        port = 5050
    app.run(host="0.0.0.0", port=port, debug=True)
