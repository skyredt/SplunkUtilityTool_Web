"""Controlled internal execution-boundary helpers for clone-oriented work."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sutw_config import get_execution_boundary_settings


def execute_clone_preparation(
    batch_id: str,
    selected_reports: list[dict[str, Any]],
    time_range: dict[str, Any],
) -> dict[str, Any]:
    """Run the first safe real execution step: clone preparation only."""
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    prepared_reports = [
        {
            "report_id": report.get("id", ""),
            "report_label": report.get("title", ""),
        }
        for report in selected_reports
        if report.get("id")
    ]

    return {
        "boundary_key": "clone_preparation",
        "boundary_label": "Clone Preparation",
        "execution_state": "prepared",
        "executed": True,
        "executed_at": timestamp,
        "batch_id": batch_id,
        "prepared_report_count": len(prepared_reports),
        "prepared_reports": prepared_reports,
        "time_range": {
            "label": time_range.get("label", ""),
            "earliest": time_range.get("earliest", ""),
            "latest": time_range.get("latest", ""),
        },
        "message": (
            "Clone preparation executed safely. Prepared report inputs are ready for later dispatch review, "
            "but no clone job, SPL dispatch, or report modification was created."
        ),
    }


def get_clone_boundary_descriptors(
    clone_preparation_result: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return internal boundary descriptors for clone preparation and dispatch handoff."""
    settings = get_execution_boundary_settings()
    clone_preparation_executed = bool(clone_preparation_result and clone_preparation_result.get("executed"))
    clone_preparation_summary = (
        clone_preparation_result.get("message")
        if clone_preparation_executed
        else (
            "Clone preparation is enabled as the first controlled real execution step. "
            "It will execute automatically once the batch reaches safe validation."
        )
    )
    dispatch_state = "eligible_for_enablement_review" if clone_preparation_executed else "defined_disabled"
    dispatch_summary = (
        "Dispatch handoff is the next boundary eligible for enablement review, but it remains disabled."
        if clone_preparation_executed
        else (
            "Dispatch handoff remains disabled until clone preparation completes and a later "
            "backend-controlled review approves it."
        )
    )

    return [
        {
            "phase_key": "clone_preparation",
            "phase_label": "Clone Preparation",
            "boundary_owner": "sutw_clone_manager",
            "boundary_mode": settings["boundary_mode"],
            "preview_only": False,
            "execution_enabled": True,
            "state": "enabled",
            "real_step_executed": clone_preparation_executed,
            "summary": clone_preparation_summary,
        },
        {
            "phase_key": "dispatch_handoff",
            "phase_label": "Dispatch Handoff",
            "boundary_owner": "sutw_clone_manager",
            "boundary_mode": settings["boundary_mode"],
            "preview_only": settings["preview_only"],
            "execution_enabled": settings["execution_enabled"],
            "state": dispatch_state,
            "real_step_executed": False,
            "summary": dispatch_summary,
        },
    ]
