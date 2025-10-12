import os
from dataclasses import dataclass
from typing import Dict, Optional

import requests


@dataclass
class AuthServiceError(Exception):
    code: str
    message: str

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise AuthServiceError("configuration-error", f"Environment variable {name} is required for Auth0.")
    return value


def _auth0_domain() -> str:
    domain = _required_env("AUTH0_DOMAIN").strip().rstrip("/")
    if not domain.startswith("https://"):
        domain = f"https://{domain}"
    return domain


def _auth0_client_id() -> str:
    return _required_env("AUTH0_CLIENT_ID")


def _auth0_client_secret() -> str:
    return _required_env("AUTH0_CLIENT_SECRET")


def _auth0_audience() -> str:
    audience = os.getenv("AUTH0_AUDIENCE")
    if audience:
        return audience
    domain = _auth0_domain()
    return f"{domain}/api/v2/"


def _auth0_connection() -> str:
    return os.getenv("AUTH0_CONNECTION", "Username-Password-Authentication")


def _handle_auth0_error(response: requests.Response, default_code: str) -> AuthServiceError:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error") or payload.get("code") or default_code
    description = (
        payload.get("error_description")
        or payload.get("message")
        or payload.get("description")
        or None
    )
    if not description:
        snippet = response.text.strip()
        if len(snippet) > 200:
            snippet = snippet[:200] + "…"
        description = f"Auth0 request failed (status {response.status_code}). {snippet or 'No response body.'}"
    code_map: Dict[str, str] = {
        "invalid_signup": "invalid-argument",
        "user_exists": "email-already-exists",
        "invalid_password": "weak-password",
        "invalid_grant": "invalid-credentials",
        "access_denied": "access-denied",
    }
    mapped = code_map.get(str(error), default_code)
    return AuthServiceError(mapped, description)


def register_user(email: str, password: str, display_name: Optional[str] = None) -> dict:
    """Create an Auth0 user via the Authentication API and return the new profile."""
    email = (email or "").strip()
    password = (password or "").strip()
    display_name = (display_name or "").strip() or None

    if not email or not password:
        raise AuthServiceError("invalid-argument", "Email and password are required.")

    domain = _auth0_domain()
    payload: Dict[str, Optional[str]] = {
        "client_id": _auth0_client_id(),
        "email": email,
        "password": password,
        "connection": _auth0_connection(),
        "name": display_name,
    }

    try:
        response = requests.post(f"{domain}/dbconnections/signup", json=payload, timeout=10)
    except requests.RequestException as exc:
        raise AuthServiceError("network-error", "Failed to reach Auth0 signup endpoint.") from exc

    if response.status_code >= 400:
        raise _handle_auth0_error(response, "auth0-signup-error")

    data = response.json()
    return {
        "user_id": data.get("_id") or data.get("user_id"),
        "email": data.get("email") or email,
        "name": data.get("name") or display_name,
    }


def login_user(email: str, password: str, scope: str = "openid profile email") -> dict:
    """Authenticate against Auth0 using the Resource Owner Password flow."""
    email = (email or "").strip()
    password = (password or "").strip()
    if not email or not password:
        raise AuthServiceError("invalid-argument", "Email and password are required.")

    domain = _auth0_domain()
    payload = {
        "grant_type": "http://auth0.com/oauth/grant-type/password-realm",
        "username": email,
        "password": password,
        "audience": _auth0_audience(),
        "scope": scope,
        "client_id": _auth0_client_id(),
        "client_secret": _auth0_client_secret(),
        "realm": _auth0_connection(),
    }

    try:
        response = requests.post(f"{domain}/oauth/token", json=payload, timeout=10)
    except requests.RequestException as exc:
        raise AuthServiceError("network-error", "Failed to reach Auth0 login endpoint.") from exc

    if response.status_code >= 400:
        raise _handle_auth0_error(response, "auth0-login-error")

    data = response.json()
    return {
        "access_token": data.get("access_token"),
        "id_token": data.get("id_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in"),
        "token_type": data.get("token_type"),
        "scope": data.get("scope"),
    }
