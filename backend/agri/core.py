"""Shared plumbing: errors, input checks, passwords, login tokens, points."""
from __future__ import annotations

import datetime as dt
import re
from functools import wraps

import jwt
from bson import ObjectId
from bson.errors import InvalidId
from flask import g, request
from werkzeug.security import check_password_hash, generate_password_hash

from .config import Config
from .db import get_db, mark_dirty


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


# ----------------------------------------------------------------- time
def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def today() -> dt.date:
    """Today's date in India, where the farms are."""
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=5, minutes=30)).date()


def parse_date(value, field="date") -> dt.date:
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        raise ApiError(f"{field} must be a date like 2026-11-20")


# ----------------------------------------------------------------- input checks
def body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Send the details as JSON")
    return data


def text(data: dict, key: str, *, required=True, max_len=200, min_len=1, label=None) -> str:
    value = data.get(key)
    label = label or key.replace("_", " ").capitalize()
    if value is None or str(value).strip() == "":
        if required:
            raise ApiError(f"{label} is required")
        return ""
    value = re.sub(r"\s+", " ", str(value)).strip()
    if len(value) < min_len:
        raise ApiError(f"{label} is too short")
    if len(value) > max_len:
        raise ApiError(f"{label} must be at most {max_len} characters")
    return value


def long_text(data: dict, key: str, *, required=True, max_len=4000, label=None) -> str:
    value = data.get(key)
    label = label or key.replace("_", " ").capitalize()
    if value is None or str(value).strip() == "":
        if required:
            raise ApiError(f"{label} is required")
        return ""
    value = str(value).strip()
    if len(value) > max_len:
        raise ApiError(f"{label} must be at most {max_len} characters")
    return value


def number(data: dict, key: str, *, required=True, lo=None, hi=None, label=None):
    value = data.get(key)
    label = label or key.replace("_", " ").capitalize()
    if value is None or value == "":
        if required:
            raise ApiError(f"{label} is required")
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ApiError(f"{label} must be a number")
    if value != value or value in (float("inf"), float("-inf")):
        raise ApiError(f"{label} must be a number")
    if lo is not None and value < lo:
        raise ApiError(f"{label} must be at least {lo:g}")
    if hi is not None and value > hi:
        raise ApiError(f"{label} must be at most {hi:g}")
    return value


def choice(data: dict, key: str, options, *, required=True, label=None):
    value = data.get(key)
    label = label or key.replace("_", " ").capitalize()
    if value is None or value == "":
        if required:
            raise ApiError(f"{label} is required")
        return None
    if value not in options:
        raise ApiError(f"{label} must be one of: {', '.join(map(str, options))}")
    return value


def oid(value) -> ObjectId:
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        raise ApiError("Not found", 404)


def clean(doc):
    """Make a database document safe to send as JSON."""
    if isinstance(doc, list):
        return [clean(d) for d in doc]
    if isinstance(doc, dict):
        out = {}
        for k, v in doc.items():
            if k == "password":
                continue
            out["id" if k == "_id" else k] = clean(v)
        return out
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, dt.datetime):
        return doc.isoformat(timespec="seconds") + "Z"
    if isinstance(doc, dt.date):
        return doc.isoformat()
    return doc


# ----------------------------------------------------------------- accounts
def hash_password(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256:600000")


def verify_password(stored: str, password: str) -> bool:
    return check_password_hash(stored, password)


def make_token(user_id) -> str:
    payload = {"sub": str(user_id), "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=Config.TOKEN_DAYS)}
    return jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise ApiError("Please log in", 401)
        try:
            payload = jwt.decode(header[7:], Config.JWT_SECRET, algorithms=["HS256"])
            user = get_db().users.find_one({"_id": ObjectId(payload["sub"])})
        except (jwt.PyJWTError, InvalidId, KeyError):
            raise ApiError("Your session has expired. Please log in again.", 401)
        if not user:
            raise ApiError("Your session has expired. Please log in again.", 401)
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


# ----------------------------------------------------------------- points ("farm score")
POINTS = {"task": 10, "log": 15, "scan": 5, "post": 5, "reply": 10, "solved": 25, "harvest": 50, "plan": 20}
LEVELS = [(0, "Seedling"), (100, "Sprout"), (300, "Grower"), (700, "Cultivator"), (1500, "Master farmer")]


def award(user_id, kind: str, note: str, ref: str | None = None) -> int:
    """Give points once per (kind, ref). Returns the points given (0 if already given)."""
    db = get_db()
    if ref and db.points.find_one({"user_id": user_id, "kind": kind, "ref": ref}):
        return 0
    amount = POINTS[kind]
    db.points.insert_one({"user_id": user_id, "kind": kind, "ref": ref, "note": note, "points": amount, "created_at": now()})
    db.users.update_one({"_id": user_id}, {"$inc": {"points": amount}})
    mark_dirty()
    return amount


def revoke(user_id, kind: str, ref: str) -> None:
    db = get_db()
    entry = db.points.find_one({"user_id": user_id, "kind": kind, "ref": ref})
    if entry:
        db.points.delete_one({"_id": entry["_id"]})
        db.users.update_one({"_id": user_id}, {"$inc": {"points": -entry["points"]}})
        mark_dirty()


def level_for(points: int) -> dict:
    points = max(0, int(points or 0))
    idx = max(i for i, (need, _) in enumerate(LEVELS) if points >= need)
    nxt = LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None
    return {"points": points, "level": LEVELS[idx][1], "level_number": idx + 1,
            "next_level": nxt[1] if nxt else None, "next_at": nxt[0] if nxt else None,
            "level_start": LEVELS[idx][0]}
