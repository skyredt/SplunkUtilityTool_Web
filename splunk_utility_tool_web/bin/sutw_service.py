"""Service-layer helpers for safe, non-destructive Splunk Utility Tool Web actions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sutw_clone_manager import execute_clone_preparation, get_clone_boundary_descriptors
from sutw_config import get_execution_boundary_settings
from sutw_kvstore import (
    create_batch_record,
    get_internal_batch_record,
    list_recent_batch_records,
    save_batch_record,
)
from sutw_report_inventory import list_eligible_reports
from sutw_verification import get_verification_boundary_descriptors

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
    "execution_mode": "controlled_clone_preparation",
    "execution_enabled": False,
    "message": (
        "Clone preparation is enabled as the first controlled real execution step. "
        "Dispatch, verification, cleanup, and locks remain disabled in this phase."
    ),
}
_PHASE_CAPABILITIES = {
    "execution_phase": "clone_preparation_enabled",
    "tracked_only": False,
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
            "key": "observe_clone_preparation",
            "label": "Observe Clone Preparation",
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
        {
            "key": "observe_clone_preparation",
            "label": "Observe Clone Preparation",
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
        {
            "key": "observe_clone_preparation",
            "label": "Observe Clone Preparation",
            "intent": "observe",
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
    batch_record = {
        "batch_id": batch_id,
        "mode": "tracked_stub",
        "lifecycle_state": initial_stage["key"],
        "lifecycle_label": initial_stage["label"],
        "state_message": initial_stage["state_message"],
        "clone_preparation_result": None,
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
    _apply_execution_metadata(
        batch_record=batch_record,
        selected_reports=selected_reports,
        submission=submission_record,
        terminal=False,
        prepare_clone=False,
    )
    return batch_record


def _advance_batch_record(batch_record: dict[str, Any]) -> dict[str, Any]:
    if batch_record.get("terminal"):
        submission = batch_record.get("submission") or {}
        selected_reports = submission.get("selected_reports") or []
        _apply_execution_metadata(
            batch_record=batch_record,
            selected_reports=selected_reports,
            submission=submission,
            terminal=True,
            prepare_clone=batch_record.get("lifecycle_state") != "accepted",
        )
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
    _apply_execution_metadata(
        batch_record=batch_record,
        selected_reports=selected_reports,
        submission=submission,
        terminal=batch_record["terminal"],
        prepare_clone=stage_index >= 1,
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


def _apply_execution_metadata(
    batch_record: dict[str, Any],
    selected_reports: list[dict[str, Any]],
    submission: dict[str, Any],
    terminal: bool,
    prepare_clone: bool,
) -> None:
    clone_preparation_result = batch_record.get("clone_preparation_result")

    if prepare_clone and not (clone_preparation_result and clone_preparation_result.get("executed")):
        clone_preparation_result = execute_clone_preparation(
            batch_id=batch_record.get("batch_id", ""),
            selected_reports=selected_reports,
            time_range=submission.get("time_range") or {},
        )

    batch_record["clone_preparation_result"] = clone_preparation_result
    batch_record["execution_readiness"] = _build_execution_readiness(clone_preparation_result)
    batch_record["phase_capabilities"] = _build_phase_capabilities(terminal)
    batch_record["transition_policy"] = _build_transition_policy(terminal)
    batch_record["action_intents"] = _build_action_intents(terminal)
    batch_record["execution_plan"] = _build_execution_plan(selected_reports, clone_preparation_result)
    batch_record["execution_request_preview"] = _build_execution_request_preview(
        batch_record.get("batch_id", ""),
        submission,
    )
    batch_record["execution_enablement"] = _build_execution_enablement(clone_preparation_result)
    batch_record["execution_action_review"] = _build_execution_action_review(
        batch_record["execution_readiness"],
        batch_record["phase_capabilities"],
        batch_record["transition_policy"],
        batch_record["action_intents"],
        batch_record["execution_plan"],
        batch_record["execution_request_preview"],
        batch_record["execution_enablement"],
    )
    batch_record["execution_phase_roadmap"] = _build_execution_phase_roadmap(
        batch_record["phase_capabilities"],
        batch_record["execution_action_review"],
        batch_record["execution_enablement"],
    )


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


def _build_execution_readiness(clone_preparation_result: dict[str, Any] | None) -> dict[str, Any]:
    execution_readiness = dict(_EXECUTION_READINESS)

    if clone_preparation_result and clone_preparation_result.get("executed"):
        execution_readiness["message"] = (
            "Clone preparation executed safely and is now observable in tracked batch status. "
            "Dispatch, verification, cleanup, and locks remain disabled."
        )
    else:
        execution_readiness["message"] = (
            "Clone preparation is enabled as the first controlled real execution step. "
            "It will run automatically after safe validation completes, while downstream phases remain disabled."
        )

    return execution_readiness


def _build_phase_capabilities(terminal: bool) -> dict[str, Any]:
    if terminal:
        message = (
            "Clone preparation remains the only enabled execution boundary after stub completion. "
            "Dispatch, verification, cleanup, and locks remain disabled."
        )
        next_allowed_transition = "review_terminal_batch"
    else:
        message = (
            "Clone preparation is enabled and observable in this phase. "
            "Dispatch, verification, cleanup, and locks remain disabled."
        )
        next_allowed_transition = "dispatch_enablement_review"

    return {
        "execution_phase": _PHASE_CAPABILITIES["execution_phase"],
        "tracked_only": _PHASE_CAPABILITIES["tracked_only"],
        "next_allowed_transition": next_allowed_transition,
        "capabilities": [dict(capability) for capability in _PHASE_CAPABILITIES["capabilities"]],
        "message": message,
    }


def _build_transition_policy(terminal: bool) -> dict[str, Any]:
    if terminal:
        next_backend_phase = "dispatch_enablement_review"
        policy_message = (
            "Clone preparation may remain observable on this terminal tracked batch, "
            "but dispatch, verification, cleanup, and locks stay disabled pending later review."
        )
    else:
        next_backend_phase = "dispatch_enablement_review"
        policy_message = (
            "Clone preparation is the only enabled real execution step in this phase. "
            "Dispatch, verification, cleanup, and locks remain disabled until later enablement review."
        )

    return {
        "next_backend_phase": next_backend_phase,
        "allowed_actions": [dict(action) for action in _TRANSITION_POLICY["allowed_actions"]],
        "disallowed_actions": [dict(action) for action in _TRANSITION_POLICY["disallowed_actions"]],
        "policy_message": policy_message,
    }


def _build_action_intents(terminal: bool) -> dict[str, Any]:
    if terminal:
        enabled_reason = (
            "Review-oriented actions and clone-preparation observation remain available after stub completion "
            "so operators can inspect the tracked batch safely."
        )
        disabled_reason = (
            "Dispatch, verification, cleanup, and full execution-backed actions remain server-side gated "
            "even after terminal stub completion."
        )
    else:
        enabled_reason = (
            "Read-only review, navigation, and clone-preparation observation are allowed while the tracked batch "
            "continues through safe lifecycle polling."
        )
        disabled_reason = (
            "Dispatch, verification, cleanup, and full execution-backed actions remain server-side gated "
            "until a later execution-enabled phase."
        )

    return {
        "enabled_actions": [dict(action) for action in _ACTION_INTENTS["enabled_actions"]],
        "disabled_actions": [dict(action) for action in _ACTION_INTENTS["disabled_actions"]],
        "action_reasoning": {
            "enabled": enabled_reason,
            "disabled": disabled_reason,
        },
        "message": (
            "Action intents now include safe clone-preparation observation. "
            "Dispatch, verification, cleanup, and full execution remain gated in this phase."
        ),
    }


def _build_execution_plan(
    selected_reports: list[dict[str, Any]],
    clone_preparation_result: dict[str, Any] | None,
) -> dict[str, Any]:
    clone_preparation_step = {
        "key": "clone_preparation",
        "label": "Clone Preparation",
        "status": "enabled_waiting",
        "message": (
            "Clone preparation is enabled as the first controlled real execution step and will run "
            "after safe validation completes."
        ),
    }

    if clone_preparation_result and clone_preparation_result.get("executed"):
        clone_preparation_step = {
            "key": "clone_preparation",
            "label": "Clone Preparation",
            "status": "executed_safe",
            "message": clone_preparation_result.get(
                "message",
                "Clone preparation executed safely with no clone job, SPL dispatch, or report modification created.",
            ),
        }

    return {
        "plan_state": "controlled_clone_preparation",
        "preview_only": False,
        "planned_reports": [
            {
                "report_id": report.get("id", ""),
                "report_label": report.get("title", ""),
            }
            for report in selected_reports
        ],
        "planned_steps": [clone_preparation_step]
        + [
            {
                "key": step["key"],
                "label": step["label"],
                "status": "preview_only",
                "message": step["message"],
            }
            for step in _EXECUTION_PLAN_STEPS
            if step["key"] != "clone_preparation"
        ],
        "message": (
            "Clone preparation is the only enabled real execution step in this phase. "
            "Dispatch, verification, cleanup, and locks remain preview-only or disabled."
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


def _build_execution_enablement(clone_preparation_result: dict[str, Any] | None) -> dict[str, Any]:
    settings = get_execution_boundary_settings()
    boundary_descriptors = _get_internal_execution_boundaries(clone_preparation_result)
    enabled_boundary = next(
        (
            {
                "key": boundary["phase_key"],
                "label": boundary["phase_label"],
                "state": boundary["state"],
            }
            for boundary in boundary_descriptors
            if boundary.get("state") == "enabled"
        ),
        {
            "key": settings["enabled_boundary"]["key"],
            "label": settings["enabled_boundary"]["label"],
            "state": settings["enablement_state"],
        },
    )
    blocked_boundaries = [
        {
            "key": boundary["phase_key"],
            "label": boundary["phase_label"],
            "state": boundary["state"],
        }
        for boundary in boundary_descriptors
        if boundary.get("state") != "enabled"
    ]

    if clone_preparation_result and clone_preparation_result.get("executed"):
        observation = {
            "state": clone_preparation_result.get("execution_state", "prepared"),
            "prepared_report_count": clone_preparation_result.get("prepared_report_count", 0),
            "executed_at": clone_preparation_result.get("executed_at", ""),
            "message": clone_preparation_result.get("message", ""),
        }
    else:
        observation = {
            "state": "waiting_for_validation",
            "prepared_report_count": 0,
            "executed_at": "",
            "message": (
                "Clone preparation is enabled and waiting for the batch to reach safe validation "
                "before it executes."
            ),
        }

    return {
        "current_enablement_state": settings["enablement_state"],
        "enabled_boundary": enabled_boundary,
        "overall_preview_only": settings["preview_only"],
        "overall_execution_enabled": settings["execution_enabled"],
        "blocked_boundaries": blocked_boundaries,
        "boundary_statuses": [
            {
                "boundary": boundary["phase_key"],
                "label": boundary["phase_label"],
                "state": boundary["state"],
                "message": boundary["summary"],
            }
            for boundary in boundary_descriptors
        ],
        "clone_preparation_observation": observation,
        "message": settings["message"],
    }


def _build_execution_action_review(
    execution_readiness: dict[str, Any],
    phase_capabilities: dict[str, Any],
    transition_policy: dict[str, Any],
    action_intents: dict[str, Any],
    execution_plan: dict[str, Any],
    execution_request_preview: dict[str, Any],
    execution_enablement: dict[str, Any],
) -> dict[str, Any]:
    execution_enabled = bool(execution_readiness.get("execution_enabled"))
    tracked_only = phase_capabilities.get("tracked_only") is True
    preview_only = bool(execution_plan.get("preview_only")) or bool(execution_request_preview.get("preview_only"))
    policy_blocks_start = any(
        action.get("key") == "start_execution" for action in transition_policy.get("disallowed_actions") or []
    )
    intents_block_start = any(
        action.get("key") == "start_execution" for action in action_intents.get("disabled_actions") or []
    )
    next_backend_step = transition_policy.get("next_backend_phase", "tracked_status_progression")
    planned_steps = execution_plan.get("planned_steps") or []
    request_shape = execution_request_preview.get("request_shape", "future_execution_submission")

    execution_allowed = (
        execution_enabled
        and not tracked_only
        and not preview_only
        and not policy_blocks_start
        and not intents_block_start
    )

    if execution_allowed:
        review_state = "execution_allowed"
        decision_reason = "Execution is allowed by the current batch review metadata."
    else:
        review_state = "execution_blocked"
        decision_reason = (
            "Execution remains blocked overall because only clone preparation is enabled in this phase, "
            "while dispatch, verification, cleanup, and locks remain server-side gated."
        )

    return {
        "review_state": review_state,
        "execution_allowed": execution_allowed,
        "preview_only": bool(execution_enablement.get("overall_preview_only")),
        "decision_reason": decision_reason,
        "next_backend_step": next_backend_step,
        "decision_inputs": [
            {
                "source": "execution_readiness",
                "summary": (
                    "Overall execution remains disabled while execution mode is limited to controlled clone preparation."
                    if not execution_enabled
                    else "Execution enabled is Yes."
                ),
            },
            {
                "source": "phase_capabilities",
                "summary": (
                    "Execution phase is "
                    f"{phase_capabilities.get('execution_phase', 'clone_preparation_enabled')} "
                    "and the next allowed transition is "
                    f"{phase_capabilities.get('next_allowed_transition', 'dispatch_enablement_review')}."
                ),
            },
            {
                "source": "transition_policy",
                "summary": (
                    "Start Execution remains listed as a disallowed action, and the next backend phase is "
                    f"{next_backend_step}."
                ),
            },
            {
                "source": "action_intents",
                "summary": "Execution-oriented intents beyond clone preparation remain disabled by server-side gating.",
            },
            {
                "source": "execution_plan",
                "summary": (
                    f"The execution plan now includes {len(planned_steps)} high-level steps, with clone preparation "
                    "enabled and later phases remaining preview-only."
                ),
            },
            {
                "source": "execution_request_preview",
                "summary": (
                    f"The backend-generated {request_shape} payload remains preflight-only for operator review."
                ),
            },
            {
                "source": "execution_enablement",
                "summary": (
                    "Clone Preparation is enabled as the only real execution boundary, while downstream "
                    "boundaries remain blocked or under enablement review."
                ),
            },
        ],
        "message": (
            "This execution-action review is backend-generated for controlled preflight review. "
            "Clone preparation may execute safely, but dispatch, verification, cleanup, and locks remain disabled."
        ),
    }


def _build_execution_phase_roadmap(
    phase_capabilities: dict[str, Any],
    execution_action_review: dict[str, Any],
    execution_enablement: dict[str, Any],
) -> dict[str, Any]:
    settings = get_execution_boundary_settings()
    current_phase = phase_capabilities.get("execution_phase", settings["current_phase"])
    next_phase = settings["next_phase"]
    enablement_milestone = settings["enablement_milestone"]
    roadmap_boundary_steps = [
        {
            "phase": boundary["boundary"],
            "label": boundary["label"],
            "status": boundary["state"],
            "message": boundary["message"],
        }
        for boundary in execution_enablement.get("boundary_statuses") or []
        if boundary.get("boundary") != "clone_preparation"
    ]
    roadmap_steps = [
        {
            "phase": current_phase,
            "label": "Clone Preparation Enabled",
            "status": "current",
            "message": (
                execution_enablement.get("clone_preparation_observation", {}).get("message")
                or "Clone preparation is enabled as the first controlled real execution step."
            ),
        },
        {
            "phase": next_phase,
            "label": "Dispatch Enablement Review",
            "status": "next",
            "message": enablement_milestone["summary"],
        },
    ]
    roadmap_steps.extend(roadmap_boundary_steps)

    return {
        "current_phase": current_phase,
        "next_phase": next_phase,
        "execution_blocked": not bool(execution_action_review.get("execution_allowed")),
        "blocked_reason": execution_action_review.get(
            "decision_reason",
            "Execution remains blocked until a later backend-controlled enablement phase.",
        ),
        "enablement_milestone": {
            "key": enablement_milestone["key"],
            "label": enablement_milestone["label"],
            "summary": enablement_milestone["summary"],
        },
        "preview_only": bool(settings["preview_only"]),
        "roadmap_steps": roadmap_steps,
        "message": (
            "This execution-phase roadmap is backend-generated for planning only. "
            "Clone preparation is enabled and observable, while dispatch, verification, cleanup, and locks remain disabled."
        ),
    }


def _get_internal_execution_boundaries(
    clone_preparation_result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    return [
        *get_clone_boundary_descriptors(clone_preparation_result),
        *get_verification_boundary_descriptors(),
    ]


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
