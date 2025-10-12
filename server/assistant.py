from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Sequence

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


def _clean_keyword(keyword: str) -> str:
    cleaned = keyword.strip()
    return cleaned


def _build_prompt(keywords: Sequence[str], question: str, history: Sequence[Dict[str, str]]) -> str:
    sections: List[str] = [
        "You are an academic assistant helping a college student plan and complete assignments.",
        "Respond with concise, encouraging guidance that breaks big tasks into actionable steps.",
        "Only reference details from the provided conversation history or keywords.",
    ]

    unique_keywords = [_clean_keyword(keyword) for keyword in keywords if keyword]
    if unique_keywords:
        bullet_keywords = "\n".join(f"- {keyword}" for keyword in unique_keywords[:25])
        sections.append("Keywords describing current assignments, concepts, or tools:")
        sections.append(bullet_keywords)
    else:
        sections.append("No keywords were provided for this question.")

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
        "Provide the best possible guidance. Offer clear next steps, useful resources, and tips."
    )

    return "\n\n".join(sections)


_LEGACY_MODEL_ALIASES = {
    "gemini-1.5-flash": "models/gemini-flash-latest",
    "gemini-1.5-pro": "models/gemini-pro-latest",
}


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
        "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0.4")),
        "top_p": float(os.getenv("GEMINI_TOP_P", "0.9")),
        "top_k": int(os.getenv("GEMINI_TOP_K", "40")),
        "max_output_tokens": int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "512")),
    }

    return genai.GenerativeModel(model_name, generation_config=generation_config)


def get_assignment_help(
    keywords: Iterable[str],
    question: str,
    *,
    history: Optional[Sequence[Dict[str, str]]] = None,
) -> AssistantResult:
    question = (question or "").strip()
    if not question:
        raise ValueError("question must not be empty")

    model = _get_model()

    prompt = _build_prompt(list(keywords or []), question, list(history or []))

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
