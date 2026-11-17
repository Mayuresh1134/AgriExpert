"""Database access. MongoDB when available, otherwise a small local store with the same API."""
from __future__ import annotations

import atexit
import os
import tempfile
import threading

from .config import APP_DATA_DIR, Config

_db = None
_dirty = threading.Event()
_lock = threading.Lock()
LOCAL_FILE = APP_DATA_DIR / "local_db.json"


def _load_local(db) -> None:
    from bson import json_util

    if not LOCAL_FILE.exists():
        return
    try:
        data = json_util.loads(LOCAL_FILE.read_text())
    except Exception as exc:  # never overwrite a file we could not read
        backup = LOCAL_FILE.with_suffix(".unreadable.json")
        LOCAL_FILE.replace(backup)
        print(f"[db] could not read {LOCAL_FILE.name} ({exc}); kept it as {backup.name} and started empty")
        return
    for name, docs in data.items():
        if docs:
            db[name].insert_many(docs)


def save_local(force: bool = False) -> None:
    """Write the local store to disk if anything changed since the last save."""
    if Config.DB_MODE != "local" or _db is None or not (force or _dirty.is_set()):
        return
    from bson import json_util

    with _lock:
        _dirty.clear()
        data = {name: list(_db[name].find()) for name in _db.list_collection_names()}
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=APP_DATA_DIR, suffix=".tmp")
        with os.fdopen(fd, "w") as fh:
            fh.write(json_util.dumps(data))
        os.replace(tmp, LOCAL_FILE)  # atomic: a crash never leaves a half-written file


def mark_dirty() -> None:
    _dirty.set()


def get_db():
    global _db
    if _db is not None:
        return _db
    mode = Config.DB_MODE
    if mode == "mongo":
        from pymongo import MongoClient

        client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=4000)
        client.admin.command("ping")
        _db = client[Config.MONGO_DB]
    else:
        import mongomock

        _db = mongomock.MongoClient()[Config.MONGO_DB]
        if mode == "local":
            _load_local(_db)
            atexit.register(save_local, True)
    _ensure_indexes(_db)
    return _db


def reset_for_tests() -> None:
    global _db
    _db = None


def _ensure_indexes(db) -> None:
    db.users.create_index("login", unique=True)
    db.farms.create_index("user_id", unique=True)
    db.cycles.create_index([("user_id", 1), ("created_at", -1)])
    db.scans.create_index([("user_id", 1), ("created_at", -1)])
    db.chats.create_index([("user_id", 1), ("created_at", -1)])
    db.posts.create_index([("created_at", -1)])
    db.replies.create_index([("post_id", 1), ("created_at", 1)])
    db.points.create_index([("user_id", 1), ("created_at", -1)])
    db.logs.create_index([("cycle_id", 1), ("date", -1)])
