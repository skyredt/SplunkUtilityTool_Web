"""Validation helpers for Splunk Utility Tool Web REST endpoints."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qs

LIST_REPORTS_METHOD = "GET"
LIST_REPORTS_PATH = "/sutw/v1/reports"
START_BATCH_PREVIEW_METHOD = "POST"
START_BATCH_PREVIEW_PATH = "/sutw/v1/batches/preview"
START_BATCH_METHOD = "POST"
START_BATCH_PATH = "/sutw/v1/batches"
RECENT_BATCHES_METHOD = "GET"
RECENT_BATCHES_PATH = "/sutw/v1/batches/recent"
BATCH_STATUS_METHOD = "GET"
BATCH_STATUS_PATH = "/sutw/v1/batches/status"
_ALLOWED_TIME_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 @._:/+-]{0,63}$")
_ALLOWED_TIME_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9@._:+-]{1,64}$")
_ALLOWED_BATCH_ID_PATTERN = re.compile(r"^sutw_batch_[a-f0-9]{32}$")
_ALLOWED_CACHE_BUSTER_PATTERN = re.compile(r"^[0-9]{1,20}$")
_MAX_REPORT_IDS = 100


class ValidationError(Exception):
    """Raised when a REST request fails validation."""

    def __init__(self, message: str, status_code: int = 400, code: str = "INVALID_REQUEST") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def validate_list_reports_request(request: Mapping[str, Any]) -> str:
    """Validate the eligible report list request and return the caller session token."""
    method, path = get_request_target(request)

    if method != LIST_REPORTS_METHOD:
        raise ValidationError("Only GET is supported for eligible report retrieval.", 405, "METHOD_NOT_ALLOWED")

    if path != LIST_REPORTS_PATH:
        raise ValidationError("The requested endpoint is not supported.", 404, "ENDPOINT_NOT_FOUND")

    query_map = _parse_query_map(request.get("query"))
    _validate_allowed_query_keys(query_map, set(), "eligible report retrieval")

    if _has_values(request.get("form")) or _has_values(request.get("payload")):
        raise ValidationError("Request bodies are not supported for eligible report retrieval.", 400, "UNSUPPORTED_BODY")

    session_key = _extract_session_key(request.get("session"))
    if not session_key:
        raise ValidationError("A valid Splunk session token is required.", 401, "AUTH_REQUIRED")

    return session_key


def validate_start_batch_preview_request(request: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    """Validate the read-only submission preview request and return sanitized input."""
    return _validate_submission_request(
        request=request,
        expected_method=START_BATCH_PREVIEW_METHOD,
        expected_path=START_BATCH_PREVIEW_PATH,
        action_label="start-batch preview",
        allow_empty_report_ids=True,
        require_acknowledgement_true=False,
    )


def validate_start_batch_request(request: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    """Validate the tracked start-batch submission and return sanitized input."""
    return _validate_submission_request(
        request=request,
        expected_method=START_BATCH_METHOD,
        expected_path=START_BATCH_PATH,
        action_label="start-batch submission",
        allow_empty_report_ids=False,
        require_acknowledgement_true=True,
    )


def validate_batch_status_request(request: Mapping[str, Any]) -> tuple[str, str]:
    """Validate the tracked batch status request and return session token plus batch ID."""
    method, path = get_request_target(request)

    if method != BATCH_STATUS_METHOD:
        raise ValidationError("Only GET is supported for batch status retrieval.", 405, "METHOD_NOT_ALLOWED")

    if path != BATCH_STATUS_PATH:
        raise ValidationError("The requested endpoint is not supported.", 404, "ENDPOINT_NOT_FOUND")

    if _has_values(request.get("form")) or _has_values(request.get("payload")):
        raise ValidationError("Request bodies are not supported for batch status retrieval.", 400, "UNSUPPORTED_BODY")

    session_key = _extract_session_key(request.get("session"))
    if not session_key:
        raise ValidationError("A valid Splunk session token is required.", 401, "AUTH_REQUIRED")

    batch_id = _extract_batch_id(request.get("query"))
    return session_key, batch_id


def validate_recent_batches_request(request: Mapping[str, Any]) -> str:
    """Validate the recent batch list request and return the caller session token."""
    method, path = get_request_target(request)

    if method != RECENT_BATCHES_METHOD:
        raise ValidationError("Only GET is supported for recent batch retrieval.", 405, "METHOD_NOT_ALLOWED")

    if path != RECENT_BATCHES_PATH:
        raise ValidationError("The requested endpoint is not supported.", 404, "ENDPOINT_NOT_FOUND")

    query_map = _parse_query_map(request.get("query"))
    _validate_allowed_query_keys(query_map, set(), "recent batch retrieval")

    if _has_values(request.get("form")) or _has_values(request.get("payload")):
        raise ValidationError("Request bodies are not supported for recent batch retrieval.", 400, "UNSUPPORTED_BODY")

    session_key = _extract_session_key(request.get("session"))
    if not session_key:
        raise ValidationError("A valid Splunk session token is required.", 401, "AUTH_REQUIRED")

    return session_key


def get_request_target(request: Mapping[str, Any]) -> tuple[str, str]:
    """Return the normalized request method and path."""
    method = _as_string(request.get("method")).upper()
    path = _normalize_path(request.get("path_info") or request.get("rest_path"))
    return method, path


def _extract_session_key(session: Any) -> str:
    if not isinstance(session, Mapping):
        return ""

    for key in ("authtoken", "sessionKey"):
        value = _as_string(session.get(key))
        if value:
            return value

    return ""


def _extract_batch_id(query: Any) -> str:
    query_map = _parse_query_map(query)
    _validate_allowed_query_keys(query_map, {"batch_id"}, "batch status retrieval")

    batch_id_values = query_map.get("batch_id")
    if not batch_id_values:
        raise ValidationError("batch_id is required for batch status retrieval.", 400, "MISSING_BATCH_ID")

    if len(batch_id_values) != 1:
        raise ValidationError("Only one batch_id may be supplied.", 400, "INVALID_BATCH_ID")

    batch_id = _as_string(batch_id_values[0])
    if not batch_id or not _ALLOWED_BATCH_ID_PATTERN.fullmatch(batch_id):
        raise ValidationError("batch_id is invalid.", 400, "INVALID_BATCH_ID")

    return batch_id


def _validate_allowed_query_keys(query_map: Mapping[str, list[str]], allowed_keys: set[str], action_label: str) -> None:
    unexpected_keys = sorted(set(query_map.keys()) - allowed_keys - {"_"})
    if unexpected_keys:
        raise ValidationError(f"Unexpected query parameters were supplied for {action_label}.", 400, "UNSUPPORTED_QUERY")

    cache_buster_values = query_map.get("_")
    if cache_buster_values is None:
        return

    if len(cache_buster_values) != 1:
        raise ValidationError(f"The optional cache-buster parameter is invalid for {action_label}.", 400, "UNSUPPORTED_QUERY")

    cache_buster = _as_string(cache_buster_values[0])
    if not cache_buster or not _ALLOWED_CACHE_BUSTER_PATTERN.fullmatch(cache_buster):
        raise ValidationError(f"The optional cache-buster parameter is invalid for {action_label}.", 400, "UNSUPPORTED_QUERY")

def _parse_query_map(query: Any) -> dict[str, list[str]]:
    if query is None:
        return {}

    if isinstance(query, str):
        stripped_query = query.strip()
        if not stripped_query:
            return {}
        return {key: values for key, values in parse_qs(stripped_query, keep_blank_values=True).items()}

    if not isinstance(query, Mapping):
        raise ValidationError("Unsupported query parameter format.", 400, "UNSUPPORTED_QUERY")

    parsed_query: dict[str, list[str]] = {}
    for raw_key, raw_value in query.items():
        key = _as_string(raw_key)
        if not key:
            raise ValidationError("Query parameter keys must be non-empty strings.", 400, "UNSUPPORTED_QUERY")

        if isinstance(raw_value, Sequence) and not isinstance(raw_value, (str, bytes, bytearray)):
            values = [_as_string(item) for item in raw_value]
        else:
            values = [_as_string(raw_value)]

        parsed_query[key] = values

    return parsed_query


def _has_values(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        stripped = value.strip()
        return bool(stripped) and stripped not in {"{}", "[]"}

    if isinstance(value, Mapping):
        return any(_has_values(item) for item in value.values())

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_has_values(item) for item in value)

    return True


def _normalize_path(value: Any) -> str:
    normalized = _as_string(value)
    if not normalized:
        return ""

    normalized = normalized.rstrip("/")
    if not normalized.startswith("/"):
        normalized = "/" + normalized

    for allowed_path in (
        LIST_REPORTS_PATH,
        START_BATCH_PREVIEW_PATH,
        BATCH_STATUS_PATH,
        RECENT_BATCHES_PATH,
        START_BATCH_PATH,
    ):
        if normalized.endswith(allowed_path):
            return allowed_path

    return normalized


def _parse_json_object(value: Any, action_label: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value

    if isinstance(value, bytes):
        raw_value = value.decode("utf-8")
    elif isinstance(value, str):
        raw_value = value.strip()
    else:
        raw_value = ""

    if not raw_value:
        raise ValidationError(f"A JSON request body is required for {action_label}.", 400, "MISSING_BODY")

    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValidationError(f"The {action_label} body must be valid JSON.", 400, "INVALID_JSON_BODY") from exc

    if not isinstance(parsed, Mapping):
        raise ValidationError(f"The {action_label} body must be a JSON object.", 400, "INVALID_JSON_BODY")

    return parsed


def _validate_submission_request(
    request: Mapping[str, Any],
    expected_method: str,
    expected_path: str,
    action_label: str,
    allow_empty_report_ids: bool,
    require_acknowledgement_true: bool,
) -> tuple[str, dict[str, Any]]:
    method, path = get_request_target(request)

    if method != expected_method:
        raise ValidationError(f"Only {expected_method} is supported for {action_label}.", 405, "METHOD_NOT_ALLOWED")

    if path != expected_path:
        raise ValidationError("The requested endpoint is not supported.", 404, "ENDPOINT_NOT_FOUND")

    if _has_values(request.get("query")):
        raise ValidationError(f"Query parameters are not supported for {action_label}.", 400, "UNSUPPORTED_QUERY")

    if _has_values(request.get("form")):
        raise ValidationError(f"Form-encoded submissions are not supported for {action_label}.", 400, "UNSUPPORTED_BODY")

    session_key = _extract_session_key(request.get("session"))
    if not session_key:
        raise ValidationError("A valid Splunk session token is required.", 401, "AUTH_REQUIRED")

    payload = _parse_json_object(request.get("payload"), action_label)
    sanitized_payload = _validate_submission_payload(payload, allow_empty_report_ids, require_acknowledgement_true)
    return session_key, sanitized_payload


def _validate_submission_payload(
    payload: Mapping[str, Any],
    allow_empty_report_ids: bool,
    require_acknowledgement_true: bool,
) -> dict[str, Any]:
    allowed_keys = {"acknowledged", "report_ids", "time_range"}
    unexpected_keys = sorted(set(payload.keys()) - allowed_keys)
    if unexpected_keys:
        raise ValidationError("Unexpected fields were supplied in the submission request.", 400, "UNEXPECTED_FIELDS")

    report_ids = _validate_report_ids(payload.get("report_ids"), allow_empty=allow_empty_report_ids)
    time_range = _validate_time_range(payload.get("time_range"))
    acknowledged = _validate_acknowledgement(payload.get("acknowledged"), require_acknowledgement_true)

    return {
        "acknowledged": acknowledged,
        "report_ids": report_ids,
        "time_range": time_range,
    }


def _validate_report_ids(value: Any, allow_empty: bool) -> list[str]:
    if not isinstance(value, list):
        raise ValidationError("report_ids must be an array of strings.", 400, "INVALID_REPORT_IDS")

    if not value and not allow_empty:
        raise ValidationError("At least one report must be selected.", 400, "NO_REPORTS_SELECTED")

    if len(value) > _MAX_REPORT_IDS:
        raise ValidationError("Too many report IDs were supplied.", 400, "TOO_MANY_REPORTS")

    sanitized_ids: list[str] = []
    seen_ids: set[str] = set()
    for item in value:
        report_id = _as_string(item)
        if not report_id:
            raise ValidationError("Each report ID must be a non-empty string.", 400, "INVALID_REPORT_IDS")

        if report_id in seen_ids:
            raise ValidationError("Duplicate report IDs are not allowed.", 400, "DUPLICATE_REPORT_IDS")

        seen_ids.add(report_id)
        sanitized_ids.append(report_id)

    return sanitized_ids


def _validate_acknowledgement(value: Any, require_true: bool) -> bool:
    if not isinstance(value, bool):
        raise ValidationError("acknowledged must be a boolean value.", 400, "INVALID_ACKNOWLEDGEMENT")

    if require_true and value is not True:
        raise ValidationError("Review acknowledgement must be true before submission.", 400, "ACKNOWLEDGEMENT_REQUIRED")

    return value


def _validate_time_range(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValidationError("time_range must be a JSON object.", 400, "INVALID_TIME_RANGE")

    allowed_keys = {"earliest", "label", "latest"}
    unexpected_keys = sorted(set(value.keys()) - allowed_keys)
    if unexpected_keys:
        raise ValidationError("Unexpected time_range fields were supplied.", 400, "UNEXPECTED_TIME_RANGE_FIELDS")

    label = _as_string(value.get("label"))
    earliest = _as_string(value.get("earliest"))
    latest = _as_string(value.get("latest"))

    if not label or not _ALLOWED_TIME_LABEL_PATTERN.fullmatch(label):
        raise ValidationError("time_range.label is invalid.", 400, "INVALID_TIME_RANGE")

    if not earliest or not _ALLOWED_TIME_TOKEN_PATTERN.fullmatch(earliest):
        raise ValidationError("time_range.earliest is invalid.", 400, "INVALID_TIME_RANGE")

    if not latest or not _ALLOWED_TIME_TOKEN_PATTERN.fullmatch(latest):
        raise ValidationError("time_range.latest is invalid.", 400, "INVALID_TIME_RANGE")

    return {
        "label": label,
        "earliest": earliest,
        "latest": latest,
    }


def _as_string(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip()

    if isinstance(value, str):
        return value.strip()

    return ""


