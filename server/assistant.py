from __future__ import annotations

import os
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
    "gemini-1.5-flash": "models/gemini-flash-latest",
    "gemini-1.5-pro": "models/gemini-pro-latest",
}


def _clean_text(value: Any, *, limit: int = 360) -> Optional[str]:
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


def _resolve_model_name(raw_name: Optional[str]) -> str:
    candidate = (raw_name or "").strip()
    if not candidate:
        return "models/gemini-flash-latest"

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
            description = _clean_text(assignment.get("description"))
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
        "You are an academic assistant helping a college student plan and complete assignments.",
        "Respond with concise, encouraging guidance that breaks big tasks into actionable steps.",
        "Use the provided keywords, course context, and conversation history. Do not invent course details.",
        "Reference specific courses and assignments when giving advice, including due dates or key requirements.",
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
        "Provide the best possible guidance. Offer clear next steps, reference relevant assignments, and suggest resources when helpful."
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
        raise ValueError("question must not be empty")

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
            "Update GEMINI_MODEL_NAME to a supported model (for example, models/gemini-flash-latest)."
        )
        raise GeminiConfigurationError(message) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    text = (response.text or "").strip()
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
