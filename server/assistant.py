from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence

import google.generativeai as genai
from google.api_core.exceptions import NotFound


class GeminiConfigurationError(RuntimeError):
    """Raised when Gemini is misconfigured or unavailable."""


@dataclass
class AssistantResult:
    """Container for a Gemini response."""

    text: str
    model: str
    usage: Dict[str, int]


_LEGACY_MODEL_ALIASES = {
    "gemini-2.0-flash": "models/gemini-2.0-flash",
    "gemini-2.0-flash-exp": "models/gemini-2.0-flash-exp",
    "gemini-flash": "models/gemini-2.0-flash",
    "gemini-flash-latest": "models/gemini-2.0-flash",
    "gemini-2.5-pro": "models/gemini-2.5-pro",
    "gemini-pro": "models/gemini-2.5-pro",
    "gemini-pro-latest": "models/gemini-2.5-pro",
}


def _clean_text(value: Any, *, limit: int = 900) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    collapsed = " ".join(value.split())
    if not collapsed:
        return None
    if len(collapsed) > limit:
        return collapsed[: limit - 1].rstrip() + "…"
    return collapsed


def _clean_keyword(keyword: str) -> str:
    return keyword.strip()


_SENSITIVE_PATTERNS = [
    ("weapon", "[redacted]"),
    ("suicide", "[redacted]"),
    ("self-harm", "[redacted]"),
    ("terror", "[redacted]"),
    ("bomb", "[redacted]"),
    ("explosive", "[redacted]"),
    ("drugs", "[redacted]"),
    ("harass", "[redacted]"),
]


def _sanitize_description(text: Optional[str]) -> Optional[str]:
    if not isinstance(text, str):
        return None
    sanitized = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        sanitized = (
            sanitized.replace(pattern, replacement)
            .replace(pattern.title(), replacement)
            .replace(pattern.upper(), replacement)
        )
    return sanitized


def _coerce_float(value: Any) -> Optional[float]:
    """Attempt to coerce a value into a float."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _safe_parse_datetime(value: Any) -> Optional[datetime]:
    """Parse common ISO-8601 timestamps into timezone-aware datetimes."""
    if not value or not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_json_text(raw: Optional[str]) -> str:
    if not raw:
        return ""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3]
    return cleaned.strip()


def _extract_candidate_text(response: Any) -> str:
    parts: List[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            text = getattr(part, "text", None)
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _extract_safety_reasons(response: Any) -> List[str]:
    reasons: List[str] = []

    prompt_feedback = getattr(response, "prompt_feedback", None)
    if prompt_feedback is not None:
        blocked_reason = getattr(prompt_feedback, "block_reason", None)
        if blocked_reason:
            reasons.append(str(blocked_reason))

    for candidate in getattr(response, "candidates", []) or []:
        safety_ratings = getattr(candidate, "safety_ratings", []) or []
        for rating in safety_ratings:
            blocked = getattr(rating, "blocked", None)
            if blocked is None:
                blocked = getattr(rating, "probability", "") == "HIGH_AND_LIKELY"
            if blocked:
                category = getattr(rating, "category", None)
                reasons.append(str(category or "unspecified"))
    # Remove duplicates while preserving order
    seen: set[str] = set()
    deduped: List[str] = []
    for reason in reasons:
        key = reason.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(reason)
    return deduped


def _resolve_model_name(raw_name: Optional[str]) -> str:
    candidate = (raw_name or "").strip()
    if not candidate:
        return "models/gemini-2.0-flash"

    lookup_key = candidate.lower()
    if lookup_key.startswith("models/"):
        lookup_key = lookup_key[len("models/") :]
    resolved = _LEGACY_MODEL_ALIASES.get(lookup_key)
    if resolved:
        return resolved
    return candidate


def _normalize_context(context: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not context or not isinstance(context, dict):
        return None

    courses = context.get("courses")
    if not isinstance(courses, list):
        return None

    normalized: List[Dict[str, Any]] = []
    for course in courses[:5]:
        if not isinstance(course, dict):
            continue
        course_id = course.get("id")
        course_name = (course.get("name") or "").strip()
        course_code = (course.get("course_code") or "").strip() or None

        assignments = course.get("assignments")
        if not isinstance(assignments, list):
            assignments = []

        clean_assignments: List[Dict[str, Any]] = []
        for assignment in assignments[:6]:
            if not isinstance(assignment, dict):
                continue
            name = (assignment.get("name") or "").strip()
            if not name:
                continue
            description = _clean_text(_sanitize_description(assignment.get("description")))
            clean_assignments.append(
                {
                    "id": assignment.get("id"),
                    "name": name,
                    "due": (assignment.get("due_at_display") or assignment.get("due_at") or "").strip()
                    or None,
                    "course_name": (assignment.get("course_name") or course_name).strip() or None,
                    "course_code": (assignment.get("course_code") or course_code or "").strip() or None,
                    "points_possible": assignment.get("points_possible"),
                    "description": description,
                }
            )

        if not clean_assignments:
            continue

        normalized.append(
            {
                "id": course_id,
                "name": course_name or "Untitled course",
                "course_code": course_code,
                "assignments": clean_assignments,
            }
        )

    return normalized or None


def _format_context_lines(courses: Sequence[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for course in courses:
        header_bits = [course.get("name") or "Course"]
        if course.get("course_code"):
            header_bits.append(f"({course['course_code']})")
        lines.append("- " + " ".join(header_bits).strip())

        for assignment in course.get("assignments", []):
            detail_bits = [assignment.get("name", "Assignment")]
            if assignment.get("due"):
                detail_bits.append(f"due {assignment['due']}")
            if assignment.get("points_possible") not in (None, ""):
                detail_bits.append(f"({assignment['points_possible']} pts)")
            lines.append("  - " + " ".join(detail_bits))
            if assignment.get("description"):
                lines.append("      Summary: " + assignment["description"])
    return lines


def _build_prompt(
    keywords: Sequence[str],
    question: str,
    history: Sequence[Dict[str, str]],
    context: Optional[List[Dict[str, Any]]] = None,
) -> str:
    sections: List[str] = [
        "You are an experienced academic success coach helping a college student plan and complete assignments.",
        "Deliver thorough, encouraging guidance. Break large goals into sequenced action steps with estimated effort or durations when possible.",
        "Tie every recommendation back to the student's actual courses, assignments, or deadlines. If the information is missing, state the assumption clearly.",
        "Offer complementary study strategies, resource suggestions, and risk alerts (e.g., overlapping due dates, missing prerequisites).",
        "Close with a concise recap of the immediate next actions so the student can start right away.",
    ]

    unique_keywords = [_clean_keyword(keyword) for keyword in keywords if keyword]
    if unique_keywords:
        bullet_keywords = "\n".join(f"- {keyword}" for keyword in unique_keywords[:25])
        sections.append("Keywords describing current assignments, concepts, or tools:")
        sections.append(bullet_keywords)
    else:
        sections.append("No keywords were provided for this question.")

    if context:
        context_lines = _format_context_lines(context)
        if context_lines:
            sections.append("Courses and assignments currently in focus:")
            sections.append("\n".join(context_lines[:64]))
            sections.append(
                "Use these assignment summaries to tailor your plan. Highlight prerequisites or deliverables from the descriptions when relevant."
            )

    if history:
        formatted_history = []
        for message in history[-10:]:
            role = (message.get("role") or "user").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = (message.get("content") or "").strip()
            if not content:
                continue
            pretty_role = "Student" if role == "user" else "Tutor"
            formatted_history.append(f"{pretty_role}: {content}")
        if formatted_history:
            sections.append("Conversation so far:")
            sections.append("\n".join(formatted_history))

    sections.append("Student question or message:")
    sections.append(question.strip())
    sections.append(
        "Structure your response with short headings or bullet points when helpful. Include: (1) immediate priorities, (2) detailed work plan with time estimates, (3) study or support resources, and (4) final quick recap."
    )

    return "\n\n".join(sections)


@lru_cache(maxsize=1)
def _get_model() -> genai.GenerativeModel:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiConfigurationError(
            "Gemini API key not configured. Set GEMINI_API_KEY in the environment."
        )

    model_name = _resolve_model_name(os.getenv("GEMINI_MODEL_NAME"))
    genai.configure(api_key=api_key)

    generation_config = {
        "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0.35")),
        "top_p": float(os.getenv("GEMINI_TOP_P", "0.85")),
        "top_k": int(os.getenv("GEMINI_TOP_K", "40")),
        "max_output_tokens": int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "512")),
    }

    return genai.GenerativeModel(model_name, generation_config=generation_config)


def get_assignment_help(
    keywords: Iterable[str],
    question: str,
    *,
    history: Optional[Sequence[Dict[str, str]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> AssistantResult:
    question = (question or "").strip()
    if not question:
        logging.getLogger(__name__).warning(
            "get_assignment_help received empty question. Supplying fallback prompt. keywords=%s context_keys=%s",
            list(keywords or []),
            list((context or {}).keys()) if isinstance(context, dict) else None,
        )
        question = (
            "Provide a thorough, actionable study and execution plan based on the supplied keywords "
            "and assignment context. Include priorities, milestones, resources, risks, and next actions."
        )

    model = _get_model()

    resolved_context = _normalize_context(context)
    prompt = _build_prompt(list(keywords or []), question, list(history or []), resolved_context)

    try:
        response = model.generate_content(
            prompt,
            request_options={"timeout": float(os.getenv("GEMINI_TIMEOUT_SECONDS", "15"))},
        )
    except NotFound as exc:
        resolved_name = _resolve_model_name(os.getenv("GEMINI_MODEL_NAME"))
        message = (
            f"Gemini model '{resolved_name}' is unavailable. "
            "Update GEMINI_MODEL_NAME to a supported model (for example, models/gemini-2.0-flash)."
        )
        raise GeminiConfigurationError(message) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    try:
        text_value = response.text
    except ValueError:
        safety_reasons = _extract_safety_reasons(response)
        if safety_reasons:
            text_value = (
                "I couldn't generate a plan because the safety filters flagged this request for "
                f"{', '.join(safety_reasons)}. Try rephrasing or removing any sensitive details."
            )
        else:
            text_value = ""

    text = (text_value or "").strip()
    if not text:
        text = "I'm sorry, I couldn't generate guidance right now. Please try asking again."

    usage_meta = getattr(response, "usage_metadata", None)
    usage = {
        "prompt_tokens": getattr(usage_meta, "prompt_token_count", 0),
        "candidates_tokens": getattr(usage_meta, "candidates_token_count", 0),
        "total_tokens": getattr(usage_meta, "total_token_count", 0),
    }

    model_name = getattr(
        model,
        "model_name",
        _resolve_model_name(os.getenv("GEMINI_MODEL_NAME")),
    )

    return AssistantResult(
        text=text,
        model=model_name,
        usage=usage,
    )


def _build_fallback_priority_output(
    cleaned_items: Sequence[Dict[str, Any]],
    generated_at: str,
) -> Dict[str, Any]:
    """Provide deterministic priority scores when the model returns no content."""
    now = datetime.now(timezone.utc)
    point_values = [
        value
        for value in (_coerce_float(item.get('points_possible')) for item in cleaned_items)
        if value is not None
    ]
    max_points = max(point_values) if point_values else 0.0

    assignments_output: List[Dict[str, Any]] = []
    for item in cleaned_items:
        due_at = _safe_parse_datetime(item.get('due_at'))
        if due_at is None:
            due_score = 55.0
        else:
            delta_hours = (due_at - now).total_seconds() / 3600
            if delta_hours <= 0:
                due_score = 95.0
            elif delta_hours <= 24:
                due_score = 88.0
            elif delta_hours <= 72:
                due_score = 78.0
            elif delta_hours <= 168:
                due_score = 70.0
            elif delta_hours <= 336:
                due_score = 60.0
            else:
                due_score = 50.0

        points_value = _coerce_float(item.get('points_possible')) or 0.0
        points_bonus = 0.0
        if max_points > 0:
            points_bonus = min(12.0, (points_value / max_points) * 12.0)

        description = item.get('description') or ""
        workload_bonus = 4.0 if len(description) > 280 else 0.0

        raw_score = due_score + points_bonus + workload_bonus
        priority_score = max(0, min(100, int(round(raw_score))))
        assignments_output.append(
            {
                'id': item['id'],
                'priority_score': priority_score,
            }
        )

    return {'generated_at': generated_at, 'assignments': assignments_output}


def analyze_assignments(
    assignments: Sequence[Dict[str, Any]],
    *,
    include_descriptions: bool = True,
    _attempt: int = 1,
) -> Dict[str, Any]:
    cleaned_items: List[Dict[str, Any]] = []
    for raw in assignments:
        if not isinstance(raw, dict):
            continue
        assignment_id = raw.get('id')
        if assignment_id is None:
            continue
        name = _clean_text(raw.get('name'), limit=200)
        if not name:
            continue
        description_source = _sanitize_description(raw.get('description')) if include_descriptions else None
        cleaned_items.append(
            {
                'id': assignment_id,
                'name': name,
                'course_name': _clean_text(raw.get('course_name'), limit=160),
                'course_code': _clean_text(raw.get('course_code'), limit=40),
                'due_at': raw.get('due_at'),
                'due_at_display': raw.get('due_at_display'),
                'description': _clean_text(description_source, limit=1500),
                'points_possible': raw.get('points_possible'),
            }
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    if not cleaned_items:
        return {'generated_at': generated_at, 'assignments': []}

    assignments_json = json.dumps(cleaned_items, ensure_ascii=False)
    prompt = (
        "You are an academic coach helping a college student prioritize upcoming assignments. "
        "You will receive a JSON array of assignments with id, course details, due dates, descriptions, and points. "
        "Evaluate the relative urgency and workload of each assignment, considering due date proximity, workload implied by the description, complexity, and point value. "
        "Return only a priority score between 0 and 100 (higher means more urgent/important). "
        "Respond with JSON ONLY in the following structure:\n"
        "{\n"
        '  "assignments": [\n'
        "    {\n"
        '      "id": 123,\n'
        '      "priority_score": 85\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Assignments JSON:\n{assignments_json}"
    )

    model = _get_model()
    try:
        response = model.generate_content(
            prompt,
            request_options={'timeout': float(os.getenv('GEMINI_TIMEOUT_SECONDS', '20'))},
        )
    except NotFound as exc:
        resolved_name = _resolve_model_name(os.getenv('GEMINI_MODEL_NAME'))
        message = (
            f"Gemini model '{resolved_name}' is unavailable. "
            'Update GEMINI_MODEL_NAME to a supported model (for example, models/gemini-2.0-flash).'
        )
        raise GeminiConfigurationError(message) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f'Gemini assignment analysis failed: {exc}') from exc

    try:
        text = (response.text or '').strip()
    except ValueError:
        text = _normalize_json_text(_extract_candidate_text(response))
        if not text:
            if include_descriptions and _attempt == 1:
                return analyze_assignments(assignments, include_descriptions=False, _attempt=_attempt + 1)
            return _build_fallback_priority_output(cleaned_items, generated_at)

    text = _normalize_json_text(text)

    if not text:
        if include_descriptions and _attempt == 1:
            return analyze_assignments(assignments, include_descriptions=False, _attempt=_attempt + 1)
        return _build_fallback_priority_output(cleaned_items, generated_at)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        fallback_text = _normalize_json_text(_extract_candidate_text(response))
        if fallback_text and fallback_text != text:
            try:
                parsed = json.loads(fallback_text)
            except json.JSONDecodeError as fallback_exc:
                if include_descriptions and _attempt == 1:
                    return analyze_assignments(assignments, include_descriptions=False, _attempt=_attempt + 1)
                return _build_fallback_priority_output(cleaned_items, generated_at)
        else:
            if include_descriptions and _attempt == 1:
                return analyze_assignments(assignments, include_descriptions=False, _attempt=_attempt + 1)
            return _build_fallback_priority_output(cleaned_items, generated_at)

    assignments_output: List[Dict[str, Any]] = []
    insight_lookup = {item['id']: item for item in cleaned_items}

    for entry in parsed.get('assignments', []) or []:
        if not isinstance(entry, dict):
            continue
        assignment_id = entry.get('id')
        if assignment_id not in insight_lookup:
            continue

        priority_score = entry.get('priority_score')
        try:
            if priority_score is not None:
                priority_score = max(0, min(100, int(priority_score)))
        except (TypeError, ValueError):
            priority_score = None

        if priority_score is None:
            fallback_priority = _build_fallback_priority_output(
                [insight_lookup[assignment_id]],
                generated_at,
            )['assignments'][0]['priority_score']
            priority_score = fallback_priority

        assignments_output.append(
            {
                'id': assignment_id,
                'priority_score': priority_score,
            }
        )

    if not assignments_output:
        return _build_fallback_priority_output(cleaned_items, generated_at)

    return {
        'generated_at': generated_at,
        'assignments': assignments_output,
    }
