"""Temporary in-memory batch storage for non-destructive tracked batch state."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from hashlib import sha256
from typing import Any

_MAX_BATCH_RECORDS = 200
_BATCH_STORE: OrderedDict[str, dict[str, Any]] = OrderedDict()


def create_batch_record(session_key: str, batch_record: dict[str, Any]) -> dict[str, Any]:
    """Store a safe batch record for the current caller and return a sanitized copy."""
    stored_record = deepcopy(batch_record)
    batch_id = stored_record["batch_id"]
    stored_record["_owner_key"] = _hash_session_key(session_key)
    _BATCH_STORE[batch_id] = stored_record
    _BATCH_STORE.move_to_end(batch_id)
    _trim_store()
    return _sanitize_record(stored_record)


def get_batch_record(session_key: str, batch_id: str) -> dict[str, Any] | None:
    """Return a sanitized batch record if it belongs to the current caller."""
    stored_record = _get_owned_record(session_key, batch_id)
    if stored_record is None:
        return None

    _BATCH_STORE.move_to_end(batch_id)
    return _sanitize_record(stored_record)


def get_internal_batch_record(session_key: str, batch_id: str) -> dict[str, Any] | None:
    """Return a deep copy of the full owned batch record for server-side updates."""
    stored_record = _get_owned_record(session_key, batch_id)
    if stored_record is None:
        return None

    _BATCH_STORE.move_to_end(batch_id)
    return deepcopy(stored_record)


def save_batch_record(session_key: str, batch_record: dict[str, Any]) -> dict[str, Any] | None:
    """Replace an existing owned batch record and return the sanitized stored copy."""
    batch_id = batch_record.get("batch_id")
    if not isinstance(batch_id, str) or not batch_id:
        return None

    existing_record = _get_owned_record(session_key, batch_id)
    if existing_record is None:
        return None

    stored_record = deepcopy(batch_record)
    stored_record["_owner_key"] = existing_record["_owner_key"]
    _BATCH_STORE[batch_id] = stored_record
    _BATCH_STORE.move_to_end(batch_id)
    _trim_store()
    return _sanitize_record(stored_record)


def list_recent_batch_records(session_key: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return the caller's recent sanitized batch records, newest first."""
    owner_key = _hash_session_key(session_key)
    matching_records = [
        _sanitize_record(stored_record)
        for stored_record in _BATCH_STORE.values()
        if stored_record.get("_owner_key") == owner_key
    ]
    matching_records.sort(
        key=lambda record: (
            record.get("updated_at", ""),
            record.get("created_at", ""),
            record.get("batch_id", ""),
        ),
        reverse=True,
    )
    return matching_records[: max(limit, 0)]


def _get_owned_record(session_key: str, batch_id: str) -> dict[str, Any] | None:
    stored_record = _BATCH_STORE.get(batch_id)
    if stored_record is None:
        return None

    if stored_record.get("_owner_key") != _hash_session_key(session_key):
        return None

    return stored_record


def _hash_session_key(session_key: str) -> str:
    return sha256(session_key.encode("utf-8")).hexdigest()


def _sanitize_record(batch_record: dict[str, Any]) -> dict[str, Any]:
    sanitized_record = deepcopy(batch_record)
    sanitized_record.pop("_owner_key", None)
    sanitized_record.pop("status_checks", None)
    return sanitized_record


def _trim_store() -> None:
    while len(_BATCH_STORE) > _MAX_BATCH_RECORDS:
        _BATCH_STORE.popitem(last=False)
