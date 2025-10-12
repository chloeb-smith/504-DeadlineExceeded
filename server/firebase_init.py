import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

_app = None
_db = None


def _build_credentials():
    """Build Firebase credentials from env, supporting inline JSON or file path."""
    json_blob = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if json_blob:
        try:
            data = json.loads(json_blob)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON") from exc
        return credentials.Certificate(data)

    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if path:
        expanded = os.path.expanduser(path)
        if not os.path.isabs(expanded):
            candidate = os.path.join(os.path.dirname(__file__), expanded)
            if os.path.exists(candidate):
                expanded = candidate
        return credentials.Certificate(expanded)

    return credentials.ApplicationDefault()


def init_firebase():
    global _app
    if _app:
        return _app

    cred = _build_credentials()
    _app = firebase_admin.initialize_app(cred)
    return _app


def get_db():
    global _db
    if _db:
        return _db

    init_firebase()
    _db = firestore.client()
    return _db
