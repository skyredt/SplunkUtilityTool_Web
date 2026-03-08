"""Eligible report inventory retrieval for Splunk Utility Tool Web."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

import splunk.rest as splunk_rest

_DESCRIPTION_TAG_PATTERN = re.compile(r"<[^>]+>")
_MAX_DESCRIPTION_LENGTH = 240


class ReportInventoryError(Exception):
    """Raised when eligible report retrieval fails."""

    def __init__(self, message: str, status_code: int = 502, code: str = "REPORT_INVENTORY_ERROR") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def list_eligible_reports(session_key: str) -> list[dict[str, str]]:
    """Return safe metadata for eligible saved searches visible to the caller."""
    try:
        _, payload = splunk_rest.simpleRequest(
            "/servicesNS/-/-/saved/searches",
            sessionKey=session_key,
            method="GET",
            getargs={
                "count": "0",
                "output_mode": "json",
            },
        )
    except Exception as exc:  # pragma: no cover - exercised in Splunk runtime.
        raise ReportInventoryError("Unable to retrieve eligible reports from Splunk.", 502, "REPORT_LOOKUP_FAILED") from exc

    data = _decode_payload(payload)
    entries = data.get("entry")
    if not isinstance(entries, list):
        raise ReportInventoryError("Splunk returned an unexpected report inventory response.", 502, "INVALID_REPORT_RESPONSE")

    reports: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for entry in entries:
        report = _build_safe_report(entry)
        if report is None or report["id"] in seen_ids:
            continue

        seen_ids.add(report["id"])
        reports.append(report)

    reports.sort(key=lambda item: (item["title"].lower(), item["app"].lower(), item["owner"].lower(), item["name"].lower()))
    return reports


def _build_safe_report(entry: Any) -> dict[str, str] | None:
    if not isinstance(entry, Mapping):
        return None

    content = entry.get("content")
    acl = entry.get("acl") or entry.get("eai:acl")
    if not isinstance(content, Mapping) or not isinstance(acl, Mapping):
        return None

    name = _clean_text(entry.get("name"))
    search = _clean_text(content.get("search"))
    app = _clean_text(acl.get("app"))
    owner = _clean_text(acl.get("owner"))

    if not name or not search or not app or not owner:
        return None

    if name.startswith("_") or _as_bool(content.get("disabled")):
        return None

    description = _sanitize_description(content.get("description"))
    title = name

    return {
        "id": f"{owner}:{app}:{name}",
        "name": name,
        "title": title,
        "app": app,
        "owner": owner,
        "description": description,
    }


def _decode_payload(payload: Any) -> Mapping[str, Any]:
    try:
        if isinstance(payload, bytes):
            decoded = payload.decode("utf-8")
        else:
            decoded = str(payload)

        data = json.loads(decoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReportInventoryError("Splunk returned a non-JSON report inventory response.", 502, "INVALID_REPORT_RESPONSE") from exc

    if not isinstance(data, Mapping):
        raise ReportInventoryError("Splunk returned an invalid report inventory payload.", 502, "INVALID_REPORT_RESPONSE")

    return data


def _sanitize_description(value: Any) -> str:
    description = _clean_text(value)
    description = _DESCRIPTION_TAG_PATTERN.sub("", description)
    description = " ".join(description.split())
    return description[:_MAX_DESCRIPTION_LENGTH]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes"}

    return False


def _clean_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    return ""
