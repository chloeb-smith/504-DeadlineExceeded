from datetime import datetime, timezone

from firebase_init import get_db


def add_item(uid: str, title: str):
    db = get_db()
    doc = {
        "title": title,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    return db.collection("users").document(uid).collection("items").add(doc)


def list_items(uid: str):
    db = get_db()
    snaps = (
        db.collection("users")
        .document(uid)
        .collection("items")
        .order_by("createdAt")
        .stream()
    )
    return [snap.to_dict() | {"id": snap.id} for snap in snaps]
