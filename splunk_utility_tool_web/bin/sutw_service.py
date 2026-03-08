"""Service-layer helpers for safe, non-destructive Splunk Utility Tool Web actions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sutw_kvstore import (
    create_batch_record,
    get_internal_batch_record,
    list_recent_batch_records,
    save_batch_record,
)
from sutw_report_inventory import list_eligible_reports

_NON_TERMINAL_POLL_INTERVAL_MS = 2000
_LIFECYCLE_STAGES = [
    {
        "key": "accepted",
        "label": "Accepted",
        "state_message": "Batch accepted. At least one selected report is still pending safe validation.",
    },
    {
        "key": "validated",
        "label": "Validated",
        "state_message": "All selected reports reached safe validation. The tracked lifecycle will move into the stub queue next.",
    },
    {
        "key": "queued",
        "label": "Queued",
        "state_message": "All selected reports reached the non-destructive queue stage. Stub completion is next.",
    },
    {
        "key": "stub_complete",
        "label": "Stub Complete",
        "state_message": "All selected reports reached non-destructive stub completion. No clone, dispatch, or destructive execution was performed.",
    },
]
_REPORT_STATUS_STAGES = [
    {
        "key": "pending",
        "label": "Pending",
        "state_message": "Report is pending safe validation.",
    },
    {
        "key": "validated",
        "label": "Validated",
        "state_message": "Report passed safe validation and is ready for the queue stage.",
    },
    {
        "key": "queued",
        "label": "Queued",
        "state_message": "Report is queued for non-destructive stub completion.",
    },
    {
        "key": "stub_complete",
        "label": "Stub Complete",
        "state_message": "Report reached non-destructive stub completion.",
    },
]
_REPORT_STAGE_INDEX = {stage["key"]: index for index, stage in enumerate(_REPORT_STATUS_STAGES)}
_EXECUTION_READINESS = {
    "tracking_mode": "tracked_batch",
    "storage_mode": "process_memory",
    "execution_mode": "stub_non_destructive",
    "execution_enabled": False,
    "message": (
        "Tracked status is available for operator review, but real execution remains disabled. "
        "Batch data stays in temporary process memory only in this phase."
    ),
}
_PHASE_CAPABILITIES = {
    "execution_phase": "tracked_only",
    "tracked_only": True,
    "capabilities": [
        {
            "key": "view_tracked_status",
            "label": "View Tracked Status",
            "enabled": True,
        },
        {
            "key": "reopen_recent_batch",
            "label": "Reopen Recent Batch",
            "enabled": True,
        },
        {
            "key": "start_execution",
            "label": "Start Execution",
            "enabled": False,
        },
    ],
}
_TRANSITION_POLICY = {
    "allowed_actions": [
        {
            "key": "view_batch_details",
            "label": "View Batch Details",
        },
        {
            "key": "refresh_status",
            "label": "Refresh Status",
        },
        {
            "key": "reopen_recent_batch",
            "label": "Reopen Recent Batch",
        },
    ],
    "disallowed_actions": [
        {
            "key": "start_execution",
            "label": "Start Execution",
        },
        {
            "key": "dispatch_clone",
            "label": "Dispatch Clone",
        },
        {
            "key": "run_verification",
            "label": "Run Verification",
        },
        {
            "key": "perform_cleanup",
            "label": "Perform Cleanup",
        },
    ],
}
_ACTION_INTENTS = {
    "enabled_actions": [
        {
            "key": "view_batch_details",
            "label": "View Batch Details",
            "intent": "review",
        },
        {
            "key": "refresh_status",
            "label": "Refresh Status",
            "intent": "observe",
        },
        {
            "key": "reopen_recent_batch",
            "label": "Reopen Recent Batch",
            "intent": "review",
        },
    ],
    "disabled_actions": [
        {
            "key": "start_execution",
            "label": "Start Execution",
            "intent": "execute",
        },
        {
            "key": "dispatch_clone",
            "label": "Dispatch Clone",
            "intent": "clone",
        },
        {
            "key": "run_verification",
            "label": "Run Verification",
            "intent": "verify",
        },
        {
            "key": "perform_cleanup",
            "label": "Perform Cleanup",
            "intent": "cleanup",
        },
    ],
}
_EXECUTION_PLAN_STEPS = [
    {
        "key": "clone_preparation",
        "label": "Clone Preparation",
        "message": "Would prepare the selected reports for a future clone-oriented execution phase.",
    },
    {
        "key": "dispatch_handoff",
        "label": "Dispatch Handoff",
        "message": "Would hand prepared work into a future dispatch phase.",
    },
    {
        "key": "verification_handoff",
        "label": "Verification Handoff",
        "message": "Would hand completed work into a future verification phase.",
    },
    {
        "key": "cleanup_handoff",
        "label": "Cleanup Handoff",
        "message": "Would hand terminal work into a future cleanup phase.",
    },
]
_EXECUTION_REQUEST_PHASES = [
    "clone_preparation",
    "dispatch_handoff",
    "verification_handoff",
    "cleanup_handoff",
]


class ServiceError(Exception):
    """Raised when a validated service request cannot be completed safely."""

    def __init__(self, message: str, status_code: int = 400, code: str = "SERVICE_ERROR") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def preview_start_batch(session_key: str, submission: dict[str, Any]) -> dict[str, Any]:
    """Return a safe, read-only preview of the current submission payload."""
    selected_reports = _resolve_selected_reports(session_key, submission["report_ids"])
    report_count = len(selected_reports)
    acknowledged = submission["acknowledged"]
    can_submit = report_count > 0 and acknowledged

    stages = [
        {
            "key": "report_selection",
            "label": "Report Selection",
            "status": "ready" if report_count > 0 else "needs_input",
        },
        {
            "key": "review_acknowledgement",
            "label": "Review Acknowledgement",
            "status": "ready" if acknowledged else "needs_input",
        },
        {
            "key": "tracked_submission",
            "label": "Tracked Submission",
            "status": "ready" if can_submit else "blocked",
        },
    ]
    ready_steps = sum(1 for stage in stages if stage["status"] == "ready")
    total_steps = len(stages)
    percent = int(round((ready_steps / total_steps) * 100)) if total_steps else 0

    if report_count == 0:
        message = "Preview validated. Select at least one eligible report to continue."
    elif not acknowledged:
        message = "Preview validated. Review acknowledgement is still required before submission."
    else:
        message = "Preview validated. Submission is ready to create a tracked non-destructive batch."

    return {
        "message": message,
        "mode": "preview",
        "preview": {
            "acknowledged": acknowledged,
            "can_submit": can_submit,
            "report_count": report_count,
            "selected_reports": selected_reports,
            "time_range": submission["time_range"],
            "progress": {
                "current_stage": "ready_for_tracked_submission" if can_submit else "awaiting_input",
                "percent": percent,
                "ready_steps": ready_steps,
                "summary": f"{ready_steps} of {total_steps} draft preparation stages are ready.",
                "total_steps": total_steps,
                "stages": stages,
            },
        },
    }


def submit_start_batch(session_key: str, submission: dict[str, Any]) -> dict[str, Any]:
    """Create a tracked non-destructive batch record and return its server-generated ID."""
    selected_reports = _resolve_selected_reports(session_key, submission["report_ids"])
    batch_record = _build_batch_record(submission, selected_reports)
    stored_record = create_batch_record(session_key, batch_record)
    batch_id = stored_record["batch_id"]

    return {
        "accepted": True,
        "batch_id": batch_id,
        "message": "Start-batch request accepted. The tracked non-destructive lifecycle is ready for status refresh.",
        "mode": stored_record["mode"],
        "status_endpoint": {
            "method": "GET",
            "path": "/servicesNS/-/splunk_utility_tool_web/sutw/v1/batches/status",
            "query": {
                "batch_id": batch_id,
            },
        },
    }


def list_recent_batches(session_key: str, limit: int = 10) -> dict[str, Any]:
    """Return recent tracked batches for the current caller only."""
    records = list_recent_batch_records(session_key, limit=limit)
    recent_batches = []

    for record in records:
        submission = record.get("submission") or {}
        report_count = submission.get("report_count")
        if not isinstance(report_count, int):
            report_count = 0

        recent_batches.append(
            {
                "batch_id": record.get("batch_id", ""),
                "lifecycle_state": record.get("lifecycle_state", ""),
                "lifecycle_label": record.get("lifecycle_label", ""),
                "report_count": report_count,
                "created_at": record.get("created_at", ""),
                "updated_at": record.get("updated_at", ""),
                "terminal": bool(record.get("terminal")),
                "message": record.get("state_message", ""),
            }
        )

    return {
        "count": len(recent_batches),
        "batches": recent_batches,
    }


def get_batch_status(session_key: str, batch_id: str) -> dict[str, Any]:
    """Return the evolving tracked non-destructive status for a previously accepted batch."""
    batch_record = get_internal_batch_record(session_key, batch_id)
    if batch_record is None:
        raise ServiceError("The requested batch was not found.", 404, "BATCH_NOT_FOUND")

    updated_record = _advance_batch_record(batch_record)
    stored_record = save_batch_record(session_key, updated_record)
    if stored_record is None:
        raise ServiceError("The requested batch was not found.", 404, "BATCH_NOT_FOUND")

    return {
        "message": stored_record["state_message"],
        "batch": stored_record,
    }


def _build_batch_record(submission: dict[str, Any], selected_reports: list[dict[str, str]]) -> dict[str, Any]:
    timestamp = _utc_now()
    batch_id = _generate_batch_id()
    initial_stage = _LIFECYCLE_STAGES[0]
    report_statuses = _build_initial_report_statuses(selected_reports, timestamp)
    submission_record = {
        "acknowledged": True,
        "report_count": len(selected_reports),
        "selected_reports": selected_reports,
        "time_range": submission["time_range"],
    }

    return {
        "batch_id": batch_id,
        "mode": "tracked_stub",
        "lifecycle_state": initial_stage["key"],
        "lifecycle_label": initial_stage["label"],
        "state_message": initial_stage["state_message"],
        "execution_readiness": dict(_EXECUTION_READINESS),
        "phase_capabilities": _build_phase_capabilities(terminal=False),
        "transition_policy": _build_transition_policy(terminal=False),
        "action_intents": _build_action_intents(terminal=False),
        "execution_plan": _build_execution_plan(selected_reports),
        "execution_request_preview": _build_execution_request_preview(batch_id, submission_record),
        "terminal": False,
        "recommended_poll_interval_ms": _NON_TERMINAL_POLL_INTERVAL_MS,
        "status_checks": 0,
        "created_at": timestamp,
        "updated_at": timestamp,
        "events": [
            _build_lifecycle_event(
                sequence=1,
                stage=initial_stage,
                timestamp=timestamp,
            )
        ],
        "submission": submission_record,
        "report_statuses": report_statuses,
        "progress": _build_lifecycle_progress(report_statuses, 0),
    }


def _advance_batch_record(batch_record: dict[str, Any]) -> dict[str, Any]:
    if batch_record.get("terminal"):
        return batch_record

    current_state = batch_record.get("lifecycle_state")
    submission = batch_record.get("submission") or {}
    selected_reports = submission.get("selected_reports") or []
    status_checks = int(batch_record.get("status_checks", 0)) + 1
    timestamp = _utc_now()
    report_statuses = _advance_report_statuses(
        report_statuses=list(batch_record.get("report_statuses") or []),
        status_checks=status_checks,
        timestamp=timestamp,
    )
    stage_index, stage = _derive_batch_stage(report_statuses)

    batch_record["status_checks"] = status_checks
    batch_record["lifecycle_state"] = stage["key"]
    batch_record["lifecycle_label"] = stage["label"]
    batch_record["state_message"] = stage["state_message"]
    batch_record["report_statuses"] = report_statuses
    batch_record["progress"] = _build_lifecycle_progress(report_statuses, stage_index)
    batch_record["updated_at"] = timestamp
    batch_record["terminal"] = stage_index == len(_LIFECYCLE_STAGES) - 1
    batch_record["recommended_poll_interval_ms"] = 0 if batch_record["terminal"] else _NON_TERMINAL_POLL_INTERVAL_MS
    batch_record["phase_capabilities"] = _build_phase_capabilities(batch_record["terminal"])
    batch_record["transition_policy"] = _build_transition_policy(batch_record["terminal"])
    batch_record["action_intents"] = _build_action_intents(batch_record["terminal"])
    batch_record["execution_plan"] = _build_execution_plan(selected_reports)
    batch_record["execution_request_preview"] = _build_execution_request_preview(
        batch_record.get("batch_id", ""),
        submission,
    )

    if current_state != stage["key"]:
        events = list(batch_record.get("events") or [])
        events.append(
            _build_lifecycle_event(
                sequence=len(events) + 1,
                stage=stage,
                timestamp=timestamp,
            )
        )
        batch_record["events"] = events

    return batch_record


def _build_initial_report_statuses(selected_reports: list[dict[str, str]], timestamp: str) -> list[dict[str, Any]]:
    initial_stage = _REPORT_STATUS_STAGES[0]
    return [
        _build_report_status(report=report, stage=initial_stage, timestamp=timestamp)
        for report in selected_reports
    ]


def _advance_report_statuses(report_statuses: list[dict[str, Any]], status_checks: int, timestamp: str) -> list[dict[str, Any]]:
    if not report_statuses or status_checks <= 1:
        return report_statuses

    transition_step = status_checks - 2
    report_count = len(report_statuses)
    report_index = transition_step % report_count
    stage_round = (transition_step // report_count) + 1
    target_stage_index = min(stage_round, len(_REPORT_STATUS_STAGES) - 1)
    target_stage = _REPORT_STATUS_STAGES[target_stage_index]
    current_stage_index = _REPORT_STAGE_INDEX.get(report_statuses[report_index].get("current_state"), 0)

    if target_stage_index <= current_stage_index:
        return report_statuses

    report_statuses[report_index].update(
        {
            "current_state": target_stage["key"],
            "sequence": target_stage_index + 1,
            "timestamp": timestamp,
            "message": target_stage["state_message"],
        }
    )
    history = list(report_statuses[report_index].get("history") or [])
    history.append(
        _build_report_history_event(
            stage=target_stage,
            timestamp=timestamp,
        )
    )
    report_statuses[report_index]["history"] = history
    return report_statuses


def _derive_batch_stage(report_statuses: list[dict[str, Any]]) -> tuple[int, dict[str, str]]:
    if not report_statuses:
        return 0, _LIFECYCLE_STAGES[0]

    minimum_stage_index = min(_REPORT_STAGE_INDEX.get(status.get("current_state"), 0) for status in report_statuses)
    batch_stage_index = min(minimum_stage_index, len(_LIFECYCLE_STAGES) - 1)
    return batch_stage_index, _LIFECYCLE_STAGES[batch_stage_index]


def _build_lifecycle_progress(report_statuses: list[dict[str, Any]], current_stage_index: int) -> dict[str, Any]:
    total_transitions = len(report_statuses) * (len(_REPORT_STATUS_STAGES) - 1)
    completed_transitions = sum(_REPORT_STAGE_INDEX.get(status.get("current_state"), 0) for status in report_statuses)
    percent = int(round((completed_transitions / total_transitions) * 100)) if total_transitions else 0
    stages = []

    for index, stage in enumerate(_LIFECYCLE_STAGES):
        if current_stage_index == len(_LIFECYCLE_STAGES) - 1:
            stage_status = "complete"
        elif index < current_stage_index:
            stage_status = "complete"
        elif index == current_stage_index:
            stage_status = "current"
        else:
            stage_status = "pending"

        stages.append(
            {
                "key": stage["key"],
                "label": stage["label"],
                "status": stage_status,
            }
        )

    return {
        "current_stage": _LIFECYCLE_STAGES[current_stage_index]["key"],
        "percent": percent,
        "completed_transitions": completed_transitions,
        "summary": f"{completed_transitions} of {total_transitions} report status transitions completed.",
        "total_transitions": total_transitions,
        "stages": stages,
    }


def _build_phase_capabilities(terminal: bool) -> dict[str, Any]:
    if terminal:
        message = "This batch reached non-destructive stub completion and remains review-only until a later execution-backed phase."
        next_allowed_transition = "review_terminal_batch"
    else:
        message = "This batch supports tracked review only. Real execution transitions remain disabled in this phase."
        next_allowed_transition = "status_refresh"

    return {
        "execution_phase": _PHASE_CAPABILITIES["execution_phase"],
        "tracked_only": _PHASE_CAPABILITIES["tracked_only"],
        "next_allowed_transition": next_allowed_transition,
        "capabilities": [dict(capability) for capability in _PHASE_CAPABILITIES["capabilities"]],
        "message": message,
    }


def _build_transition_policy(terminal: bool) -> dict[str, Any]:
    if terminal:
        next_backend_phase = "execution_enablement_pending"
        policy_message = (
            "This batch is terminal for the current tracked-only phase. "
            "Operator review remains allowed, but execution-backed actions stay disabled."
        )
    else:
        next_backend_phase = "tracked_status_progression"
        policy_message = (
            "This batch may continue through tracked status refresh only. "
            "Execution-backed transitions remain disabled until a later phase."
        )

    return {
        "next_backend_phase": next_backend_phase,
        "allowed_actions": [dict(action) for action in _TRANSITION_POLICY["allowed_actions"]],
        "disallowed_actions": [dict(action) for action in _TRANSITION_POLICY["disallowed_actions"]],
        "policy_message": policy_message,
    }


def _build_action_intents(terminal: bool) -> dict[str, Any]:
    if terminal:
        enabled_reason = "Review-oriented actions remain available after stub completion so operators can inspect the terminal tracked batch safely."
        disabled_reason = "Execution-backed actions remain server-side gated even after terminal stub completion."
    else:
        enabled_reason = "Read-only review and navigation actions are allowed while the tracked batch continues through safe lifecycle polling."
        disabled_reason = "Execution-backed actions remain server-side gated until a later execution-enabled phase."

    return {
        "enabled_actions": [dict(action) for action in _ACTION_INTENTS["enabled_actions"]],
        "disabled_actions": [dict(action) for action in _ACTION_INTENTS["disabled_actions"]],
        "action_reasoning": {
            "enabled": enabled_reason,
            "disabled": disabled_reason,
        },
        "message": "Action intents are descriptive only. Server-side gating keeps execution disabled in this phase.",
    }


def _build_execution_plan(selected_reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "plan_state": "preview_only",
        "preview_only": True,
        "planned_reports": [
            {
                "report_id": report.get("id", ""),
                "report_label": report.get("title", ""),
            }
            for report in selected_reports
        ],
        "planned_steps": [
            {
                "key": step["key"],
                "label": step["label"],
                "status": "preview_only",
                "message": step["message"],
            }
            for step in _EXECUTION_PLAN_STEPS
        ],
        "message": (
            "This execution plan is a high-level preview only. "
            "No clone, dispatch, verification, or cleanup action runs in this phase."
        ),
    }


def _build_execution_request_preview(batch_id: str, submission: dict[str, Any]) -> dict[str, Any]:
    selected_reports = submission.get("selected_reports") or []
    time_range = submission.get("time_range") or {}

    return {
        "request_shape": "future_execution_submission",
        "preview_only": True,
        "batch_id": batch_id,
        "report_ids": [report.get("id", "") for report in selected_reports if report.get("id")],
        "time_range": {
            "label": time_range.get("label", ""),
            "earliest": time_range.get("earliest", ""),
            "latest": time_range.get("latest", ""),
        },
        "acknowledged": bool(submission.get("acknowledged")),
        "execution_phases": list(_EXECUTION_REQUEST_PHASES),
        "message": (
            "This execution request preview is backend-generated for preflight review only. "
            "No clone, dispatch, verification, or cleanup action runs in this phase."
        ),
    }


def _build_lifecycle_event(sequence: int, stage: dict[str, str], timestamp: str) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "state": stage["key"],
        "label": stage["label"],
        "timestamp": timestamp,
        "message": stage["state_message"],
    }


def _build_report_status(report: dict[str, str], stage: dict[str, str], timestamp: str) -> dict[str, Any]:
    return {
        "report_id": report["id"],
        "report_label": report["title"],
        "current_state": stage["key"],
        "sequence": _REPORT_STAGE_INDEX[stage["key"]] + 1,
        "timestamp": timestamp,
        "message": stage["state_message"],
        "history": [
            _build_report_history_event(
                stage=stage,
                timestamp=timestamp,
            )
        ],
    }


def _build_report_history_event(stage: dict[str, str], timestamp: str) -> dict[str, Any]:
    return {
        "state": stage["key"],
        "sequence": _REPORT_STAGE_INDEX[stage["key"]] + 1,
        "timestamp": timestamp,
        "message": stage["state_message"],
    }


def _generate_batch_id() -> str:
    return f"sutw_batch_{uuid4().hex}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_selected_reports(session_key: str, report_ids: list[str]) -> list[dict[str, str]]:
    eligible_reports = {report["id"]: report for report in list_eligible_reports(session_key)}
    selected_reports = []

    for report_id in report_ids:
        report = eligible_reports.get(report_id)
        if report is None:
            raise ServiceError("One or more selected reports are not eligible for submission.", 400, "INELIGIBLE_REPORT")

        selected_reports.append(
            {
                "id": report["id"],
                "title": report["title"],
                "app": report["app"],
                "owner": report["owner"],
            }
        )

    return selected_reports
