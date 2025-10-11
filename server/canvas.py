from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import requests

DEFAULT_TIMEOUT = 20


def _next_link(link_header: Optional[str]) -> Optional[str]:
    if not link_header:
        return None
    parts = [part.strip() for part in link_header.split(",")]
    for part in parts:
        if 'rel="next"' in part:
            start = part.find("<")
            end = part.find(">")
            if start != -1 and end != -1 and end > start:
                return part[start + 1 : end]
    return None


def canvas_get(
    base_url: str,
    token: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    paginate: bool = False,
) -> Any:
    url = f"{base_url}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    results: List[Any] = []
    session = requests.Session()
    try:
        while True:
            response = session.get(
                url,
                headers=headers,
                params=params,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            if not paginate:
                return payload

            if isinstance(payload, list):
                results.extend(payload)
            else:
                results.append(payload)

            next_url = _next_link(response.headers.get("Link"))
            if not next_url:
                break
            url = next_url
            params = None  # Subsequent requests encode params in the link.
        return results
    finally:
        session.close()
