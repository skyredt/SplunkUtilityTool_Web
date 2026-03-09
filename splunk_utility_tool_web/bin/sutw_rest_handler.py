"""Persistent REST handler for Splunk Utility Tool Web."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from typing import Any

from splunk.persistconn.application import PersistentServerConnectionApplication

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

from sutw_report_inventory import ReportInventoryError, list_eligible_reports
from sutw_service import ServiceError, get_batch_status, list_recent_batches, preview_start_batch, submit_start_batch
from sutw_validation import (
    BATCH_STATUS_PATH,
    LIST_REPORTS_PATH,
    RECENT_BATCHES_PATH,
    START_BATCH_PATH,
    START_BATCH_PREVIEW_PATH,
    ValidationError,
    get_request_target,
    validate_batch_status_request,
    validate_list_reports_request,
    validate_recent_batches_request,
    validate_start_batch_preview_request,
    validate_start_batch_request,
)


class SutwRestHandler(PersistentServerConnectionApplication):
    """Handle eligible report list, preview, tracked submission, and batch status requests."""

    def __init__(self, command_line: list[str] | None = None, command_arg: Any = None) -> None:
        super().__init__()

    def handle(self, in_string: str) -> dict[str, Any]:
        try:
            request = _parse_request(in_string)
            response_payload = _dispatch_request(request)
        except RequestParseError as exc:
            return _json_response(exc.status_code, _error_payload(exc.code, str(exc)))
        except ValidationError as exc:
            return _json_response(exc.status_code, _error_payload(exc.code, str(exc)))
        except ReportInventoryError as exc:
            return _json_response(exc.status_code, _error_payload(exc.code, str(exc)))
        except ServiceError as exc:
            return _json_response(exc.status_code, _error_payload(exc.code, str(exc)))
        except Exception:
            return _json_response(500, _error_payload("INTERNAL_ERROR", "An unexpected error occurred while processing the request."))

        return _json_response(200, response_payload)


class RequestParseError(Exception):
    """Raised when the persistent endpoint request cannot be parsed."""

    def __init__(self, message: str, status_code: int = 400, code: str = "INVALID_REQUEST") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def _parse_request(in_string: str) -> Mapping[str, Any]:
    if not in_string:
        return {}

    try:
        request = json.loads(in_string)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RequestParseError("The incoming request could not be parsed.") from exc

    if not isinstance(request, Mapping):
        raise RequestParseError("The incoming request payload must be a JSON object.")

    return request


def _error_payload(code: str, message: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
        }
    }


def _dispatch_request(request: Mapping[str, Any]) -> Mapping[str, Any]:
    _, path = get_request_target(request)

    if path == LIST_REPORTS_PATH:
        session_key = validate_list_reports_request(request)
        reports = list_eligible_reports(session_key)
        return {
            "count": len(reports),
            "reports": reports,
        }

    if path == START_BATCH_PREVIEW_PATH:
        session_key, submission = validate_start_batch_preview_request(request)
        return preview_start_batch(session_key, submission)

    if path == START_BATCH_PATH:
        session_key, submission = validate_start_batch_request(request)
        return submit_start_batch(session_key, submission)

    if path == RECENT_BATCHES_PATH:
        session_key = validate_recent_batches_request(request)
        return list_recent_batches(session_key)

    if path == BATCH_STATUS_PATH:
        session_key, batch_id = validate_batch_status_request(request)
        return get_batch_status(session_key, batch_id)

    raise ValidationError("The requested endpoint is not supported.", 404, "ENDPOINT_NOT_FOUND")


def _json_response(status_code: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "headers": {
            "Content-Type": "application/json",
        },
        "payload": json.dumps(payload),
        "status": status_code,
    }
