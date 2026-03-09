# Endpoint Contract

## Status

Phase 27 implemented for eligible report retrieval, read-only submission preview, tracked start-batch submission, read-only recent batch retrieval, and read-only batch status retrieval with safe lifecycle progression, timeline events, per-report tracked statuses, per-report transition history, recent-batch refresh, explicit execution-readiness metadata, explicit phase-capability metadata, a lifecycle-policy block, action-intent metadata, an execution-plan block, a backend-generated execution-request preview block, a backend-generated execution-enablement checkpoint block, a backend-generated execution-action review block, a backend-generated execution-phase roadmap block, and controlled internal execution-boundary descriptors with clone preparation enabled as the first safe real execution step.

## Lifecycle Model

- Start-batch submission creates a server-generated batch ID
- The backend stores a lightweight non-destructive in-memory batch record for this phase
- Each status refresh advances the selected reports through safe non-destructive per-report states
- The overall batch lifecycle is derived from the shared report-level progression
- Each tracked batch includes a simple display-oriented lifecycle timeline
- Each tracked batch includes a safe per-report status list for the selected reports
- Each report status entry includes a small safe transition history
- The backend can return a caller-scoped recent batch list so the frontend can reopen previously tracked batches
- Each tracked batch now includes safe execution-readiness metadata for later execution-phase alignment
- Each tracked batch now includes safe phase-capability metadata for future execution-backed behavior alignment
- Each tracked batch now includes safe lifecycle-policy metadata for future backend transition alignment
- Each tracked batch now includes safe action-intent metadata for future server-gated action alignment
- Each tracked batch now includes a safe execution-plan block that mixes one controlled real step with later preview-only phases
- Each tracked batch now includes a safe backend-generated execution-request preview for future execution-backed preflight alignment
- Each tracked batch now includes a safe backend-generated execution-enablement checkpoint showing which internal boundaries are enabled or still blocked
- Each tracked batch now includes a safe backend-generated execution-action review for operator-facing preflight decision summary
- Each tracked batch now includes a safe backend-generated execution-phase roadmap for later execution enablement planning
- The backend now defines controlled internal execution-boundary descriptors for `clone_preparation`, `dispatch_handoff`, `verification_handoff`, and `cleanup_handoff`
- `clone_preparation` is the only enabled real execution boundary in this phase and it executes safely after validation without dispatching jobs or modifying reports
- Current tracked batches remain temporary process-memory records for this phase and are not yet durable execution records
- Current lifecycle states are `accepted`, `validated`, `queued`, and `stub_complete`
- Current report states are `pending`, `validated`, `queued`, and `stub_complete`
- No clone, dispatch, verification, cleanup, locks, or destructive execution is performed

## Presentation Note

- Phase 27 does not change the backend request surface
- The existing batch status response now drives a dedicated frontend batch detail panel
- That panel now groups recent tracked batch selection, manual recent-batch refresh, temporary-retention hints, batch overview, execution-readiness metadata, phase-capability metadata, lifecycle-policy metadata, action-intent metadata, execution-plan metadata, execution-request preview metadata, execution-enablement checkpoint metadata, execution-action review metadata, execution-phase roadmap metadata, batch lifecycle timeline, per-report current statuses, and per-report transition histories in one place
- The current tracked-state model is intentionally kept aligned with the future execution model through stable `batch_id` reuse, while storage remains temporary and non-destructive in this phase

## Internal Execution Boundary

- The backend now defines controlled internal execution-boundary descriptors for `clone_preparation`, `dispatch_handoff`, `verification_handoff`, and `cleanup_handoff`
- These descriptors are represented as safe service-layer placeholders and execution-phase descriptors only; they are not independently invokable endpoints in this phase
- The execution-enablement checkpoint and roadmap blocks are generated from these internal boundaries plus the existing readiness, policy, intent, and preview metadata
- `clone_preparation` is enabled as the first controlled real execution boundary in this phase
- `dispatch_handoff`, `verification_handoff`, `cleanup_handoff`, and locks remain disabled in this phase

## Endpoint 1

`GET /servicesNS/-/splunk_utility_tool_web/sutw/v1/reports`

This endpoint is exposed to Splunk Web through `splunkd/__raw` and returns the eligible report list used by the frontend selection step.

### Request Rules

- Method: `GET` only
- Query string: not supported, except for Splunk's optional cache-buster key `_` on GET requests
- Request body: not supported
- Authentication: required
- Authorization model: current Splunk session token is used to read only reports the caller can already access

### Successful Response

```json
{
  "count": 2,
  "reports": [
    {
      "id": "admin:search:Executive Summary Dashboard",
      "name": "Executive Summary Dashboard",
      "title": "Executive Summary Dashboard",
      "app": "search",
      "owner": "admin",
      "description": "Short plain-text description"
    }
  ]
}
```

### Safe Metadata Returned

- `id`: stable frontend identifier composed from owner, app, and report name
- `name`: saved search name
- `title`: display label for the frontend
- `app`: app namespace
- `owner`: Splunk owner namespace
- `description`: sanitized plain-text description, truncated for UI use

The backend does not return SPL, dispatch settings, tokens, sharing secrets, or any mutable execution data.

## Endpoint 2

`POST /servicesNS/-/splunk_utility_tool_web/sutw/v1/batches/preview`

This endpoint provides a safe read-only preview of the current submission payload. It validates the same core fields used by start-batch, re-checks any selected report IDs against the caller's eligible inventory, and returns non-destructive readiness data for the progress section before a batch exists.

### Request Body

```json
{
  "acknowledged": false,
  "report_ids": [
    "admin:search:Executive Summary Dashboard"
  ],
  "time_range": {
    "label": "Last 24 hours",
    "earliest": "-24h@h",
    "latest": "now"
  }
}
```

### Request Rules

- Method: `POST` only
- Query string: not supported
- Authentication: required
- `acknowledged` must be a boolean
- `report_ids` must be an array of unique strings and may be empty for preview
- `time_range` must contain only `label`, `earliest`, and `latest`
- Submitted report IDs, if any, must still be present in the caller's eligible report inventory

### Successful Response

```json
{
  "mode": "preview",
  "message": "Preview validated. Submission is ready to create a tracked non-destructive batch.",
  "preview": {
    "acknowledged": true,
    "can_submit": true,
    "report_count": 1,
    "selected_reports": [
      {
        "id": "admin:search:Executive Summary Dashboard",
        "title": "Executive Summary Dashboard",
        "app": "search",
        "owner": "admin"
      }
    ],
    "time_range": {
      "label": "Last 24 hours",
      "earliest": "-24h@h",
      "latest": "now"
    },
    "progress": {
      "current_stage": "ready_for_tracked_submission",
      "percent": 100,
      "ready_steps": 3,
      "summary": "3 of 3 draft preparation stages are ready.",
      "total_steps": 3
    }
  }
}
```

### Read-Only Behavior

- The backend validates and echoes safe readiness data only
- No batch record is created
- No jobs are created
- No clone, dispatch, verification, cleanup, or lock activity occurs
- No SPL or internal execution details are exposed in the response

## Endpoint 3

`POST /servicesNS/-/splunk_utility_tool_web/sutw/v1/batches`

This endpoint accepts the validated start-batch submission, re-checks that each selected report is still eligible, creates a lightweight non-destructive tracked batch record, and returns a server-generated batch ID.

### Request Body

```json
{
  "acknowledged": true,
  "report_ids": [
    "admin:search:Executive Summary Dashboard"
  ],
  "time_range": {
    "label": "Last 24 hours",
    "earliest": "-24h@h",
    "latest": "now"
  }
}
```

### Request Rules

- Method: `POST` only
- Query string: not supported
- Authentication: required
- `acknowledged` must be `true`
- `report_ids` must be a non-empty array of unique strings
- `time_range` must contain only `label`, `earliest`, and `latest`
- Submitted report IDs must still be present in the caller's eligible report inventory

### Successful Response

```json
{
  "accepted": true,
  "batch_id": "sutw_batch_1234567890abcdef1234567890abcdef",
  "message": "Start-batch request accepted. The tracked non-destructive lifecycle is ready for status refresh.",
  "mode": "tracked_stub",
  "status_endpoint": {
    "method": "GET",
    "path": "/servicesNS/-/splunk_utility_tool_web/sutw/v1/batches/status",
    "query": {
      "batch_id": "sutw_batch_1234567890abcdef1234567890abcdef"
    }
  }
}
```

### Tracked Behavior

- The backend creates a server-generated batch ID
- The backend stores a lightweight in-memory batch record scoped to the current caller session
- The created batch record starts in a safe tracked lifecycle and can be refreshed through the status endpoint
- No clone, dispatch, verification, cleanup, or destructive execution is started
- No SPL or internal execution details are exposed in the response

## Endpoint 4

`GET /servicesNS/-/splunk_utility_tool_web/sutw/v1/batches/status?batch_id=...`

This endpoint returns safe tracked status data for a previously accepted batch. In Phase 27 it remains safe and non-destructive overall, but it may execute the enabled clone-preparation boundary once the batch reaches safe validation.

### Request Rules

- Method: `GET` only
- Authentication: required
- Request body: not supported
- Query string: `batch_id` is required; Splunk's optional cache-buster key `_` is ignored if present
- `batch_id` must match the server-generated batch ID format exactly
- The batch record must exist and belong to the current caller session scope

### Lifecycle Progression

- The status endpoint progresses the stored batch through safe states when it is refreshed or polled
- The per-report progression is `pending` -> `validated` -> `queued` -> `stub_complete`
- The batch progression is `accepted` -> `validated` -> `queued` -> `stub_complete`
- Once the batch reaches safe validation, clone preparation may execute once as the first controlled real execution step
- `stub_complete` is the terminal non-destructive state for this phase
- Once the batch reaches `stub_complete`, later reads return the same terminal record without further progression

### Timeline Events

- Each lifecycle transition is recorded as a simple safe event entry
- Each event contains only display-oriented fields: `sequence`, `state`, `label`, `timestamp`, and `message`
- The event list is ordered from oldest to newest and is safe for direct frontend display

### Per-Report Statuses

- Each selected report is represented in `report_statuses`
- Each report status entry contains only safe display-oriented fields: `report_id`, `report_label`, `current_state`, `sequence`, `timestamp`, and `message`
- Report entries advance independently, while the batch lifecycle advances only when all reports reach the next shared stage
- Each report status entry includes a `history` list containing only `state`, `sequence`, `timestamp`, and `message`
- History entries are appended only when a report actually changes state, not on every poll

### Execution-Readiness Metadata

- Each tracked batch includes an `execution_readiness` object for operator display and later execution-phase alignment
- This metadata contains only safe display-oriented fields: `tracking_mode`, `storage_mode`, `execution_mode`, `execution_enabled`, and `message`
- `execution_enabled` remains `false` for overall execution in this phase
- The metadata now reflects that clone preparation is enabled while dispatch, verification, cleanup, and locks remain disabled

### Phase-Capability Metadata

- Each tracked batch includes a `phase_capabilities` object for operator display and later execution-backed phase alignment
- This metadata contains only safe display-oriented fields such as `execution_phase`, `tracked_only`, `next_allowed_transition`, `capabilities`, and `message`
- Each capability entry contains only `key`, `label`, and `enabled`
- The capability block now reflects that clone preparation observation is enabled while later boundaries remain gated

### Lifecycle-Policy Metadata

- Each tracked batch includes a `transition_policy` object for operator display and later backend transition alignment
- This metadata contains only safe display-oriented fields such as `next_backend_phase`, `allowed_actions`, `disallowed_actions`, and `policy_message`
- Each action entry contains only `key` and `label`
- The lifecycle-policy block now reflects that dispatch enablement review is the next backend-controlled milestone

### Action-Intent Metadata

- Each tracked batch includes an `action_intents` object for operator display and later server-gated action alignment
- This metadata contains only safe display-oriented fields such as `enabled_actions`, `disabled_actions`, `action_reasoning`, and `message`
- Each action entry contains only `key`, `label`, and `intent`
- The action-intent block now includes safe clone-preparation observation while full execution-backed actions remain gated

### Execution-Plan Metadata

- Each tracked batch includes an `execution_plan` object for operator display and later execution-backed preview alignment
- This metadata contains only safe display-oriented fields such as `plan_state`, `preview_only`, `planned_reports`, `planned_steps`, and `message`
- Each planned report entry contains only `report_id` and `report_label`
- Each planned step entry contains only `key`, `label`, `status`, and `message`
- The execution-plan block now reflects one controlled real step for clone preparation while later phases remain preview-only or disabled

### Execution-Request Preview Metadata

- Each tracked batch includes an `execution_request_preview` object for operator display and later execution-backed preflight alignment
- This metadata contains only safe display-oriented fields such as `request_shape`, `preview_only`, `batch_id`, `report_ids`, `time_range`, `acknowledged`, `execution_phases`, and `message`
- `report_ids` contains only the selected safe report identifiers already accepted into the tracked batch record
- `time_range` contains only the submitted high-level range fields: `label`, `earliest`, and `latest`
- The execution-request preview block is descriptive only and does not enable clone, dispatch, verification, cleanup, or lock behavior

### Execution-Enablement Checkpoint Metadata

- Each tracked batch includes an `execution_enablement` object for operator display and controlled enablement reporting
- This metadata contains only safe display-oriented fields such as `current_enablement_state`, `enabled_boundary`, `overall_preview_only`, `overall_execution_enabled`, `blocked_boundaries`, `boundary_statuses`, `clone_preparation_observation`, and `message`
- Each `enabled_boundary` entry contains only `key`, `label`, and `state`
- Each `blocked_boundaries` entry contains only `key`, `label`, and `state`
- Each `boundary_statuses` entry contains only `boundary`, `label`, `state`, and `message`
- The `clone_preparation_observation` object contains only safe display-oriented fields: `state`, `prepared_report_count`, `executed_at`, and `message`
- The checkpoint block reflects that clone preparation is enabled while dispatch, verification, cleanup, and locks remain blocked

### Execution-Action Review Metadata

- Each tracked batch includes an `execution_action_review` object for operator display and later execution-backed preflight decision alignment
- This metadata contains only safe display-oriented fields such as `review_state`, `execution_allowed`, `preview_only`, `decision_reason`, `next_backend_step`, `decision_inputs`, and `message`
- Each `decision_inputs` entry contains only `source` and `summary`
- The review block summarizes the current high-level preflight decision using the existing readiness, capability, policy, intent, plan, and request-preview metadata
- The execution-action review block is descriptive only and does not enable clone, dispatch, verification, cleanup, or lock behavior

### Execution-Phase Roadmap Metadata

- Each tracked batch includes an `execution_phase_roadmap` object for operator display and later execution enablement planning
- This metadata contains only safe display-oriented fields such as `current_phase`, `next_phase`, `execution_blocked`, `blocked_reason`, `enablement_milestone`, `preview_only`, `roadmap_steps`, and `message`
- The `enablement_milestone` object contains only `key`, `label`, and `summary`
- Each `roadmap_steps` entry contains only `phase`, `label`, `status`, and `message`
- The roadmap block is descriptive only and does not enable clone, dispatch, verification, cleanup, or lock behavior

### Successful Response

```json
{
  "message": "Batch validation is complete. The tracked lifecycle will move into the stub queue next.",
  "batch": {
    "batch_id": "sutw_batch_1234567890abcdef1234567890abcdef",
    "mode": "tracked_stub",
    "lifecycle_state": "validated",
    "lifecycle_label": "Validated",
    "state_message": "Batch validation is complete. The tracked lifecycle will move into the stub queue next.",
    "execution_readiness": {
      "tracking_mode": "tracked_batch",
      "storage_mode": "process_memory",
      "execution_mode": "controlled_clone_preparation",
      "execution_enabled": false,
      "message": "Clone preparation executed safely and is now observable in tracked batch status. Dispatch, verification, cleanup, and locks remain disabled."
    },
    "phase_capabilities": {
      "execution_phase": "clone_preparation_enabled",
      "tracked_only": false,
      "next_allowed_transition": "dispatch_enablement_review",
      "capabilities": [
        {
          "key": "view_tracked_status",
          "label": "View Tracked Status",
          "enabled": true
        },
        {
          "key": "reopen_recent_batch",
          "label": "Reopen Recent Batch",
          "enabled": true
        },
        {
          "key": "observe_clone_preparation",
          "label": "Observe Clone Preparation",
          "enabled": true
        },
        {
          "key": "start_execution",
          "label": "Start Execution",
          "enabled": false
        }
      ],
      "message": "Clone preparation is enabled and observable in this phase. Dispatch, verification, cleanup, and locks remain disabled."
    },
    "transition_policy": {
      "next_backend_phase": "dispatch_enablement_review",
      "allowed_actions": [
        {
          "key": "view_batch_details",
          "label": "View Batch Details"
        },
        {
          "key": "refresh_status",
          "label": "Refresh Status"
        },
        {
          "key": "reopen_recent_batch",
          "label": "Reopen Recent Batch"
        },
        {
          "key": "observe_clone_preparation",
          "label": "Observe Clone Preparation"
        }
      ],
      "disallowed_actions": [
        {
          "key": "start_execution",
          "label": "Start Execution"
        },
        {
          "key": "dispatch_clone",
          "label": "Dispatch Clone"
        },
        {
          "key": "run_verification",
          "label": "Run Verification"
        },
        {
          "key": "perform_cleanup",
          "label": "Perform Cleanup"
        }
      ],
      "policy_message": "Clone preparation is the only enabled real execution step in this phase. Dispatch, verification, cleanup, and locks remain disabled until later enablement review."
    },
    "action_intents": {
      "enabled_actions": [
        {
          "key": "view_batch_details",
          "label": "View Batch Details",
          "intent": "review"
        },
        {
          "key": "refresh_status",
          "label": "Refresh Status",
          "intent": "observe"
        },
        {
          "key": "reopen_recent_batch",
          "label": "Reopen Recent Batch",
          "intent": "review"
        },
        {
          "key": "observe_clone_preparation",
          "label": "Observe Clone Preparation",
          "intent": "observe"
        }
      ],
      "disabled_actions": [
        {
          "key": "start_execution",
          "label": "Start Execution",
          "intent": "execute"
        },
        {
          "key": "dispatch_clone",
          "label": "Dispatch Clone",
          "intent": "clone"
        },
        {
          "key": "run_verification",
          "label": "Run Verification",
          "intent": "verify"
        },
        {
          "key": "perform_cleanup",
          "label": "Perform Cleanup",
          "intent": "cleanup"
        }
      ],
      "action_reasoning": {
        "enabled": "Read-only review, navigation, and clone-preparation observation are allowed while the tracked batch continues through safe lifecycle polling.",
        "disabled": "Dispatch, verification, cleanup, and full execution-backed actions remain server-side gated until a later execution-enabled phase."
      },
      "message": "Action intents now include safe clone-preparation observation. Dispatch, verification, cleanup, and full execution remain gated in this phase."
    },
    "execution_plan": {
      "plan_state": "controlled_clone_preparation",
      "preview_only": false,
      "planned_reports": [
        {
          "report_id": "admin:search:Executive Summary Dashboard",
          "report_label": "Executive Summary Dashboard"
        }
      ],
      "planned_steps": [
        {
          "key": "clone_preparation",
          "label": "Clone Preparation",
          "status": "executed_safe",
          "message": "Clone preparation executed safely. Prepared report inputs are ready for later dispatch review, but no clone job, SPL dispatch, or report modification was created."
        },
        {
          "key": "dispatch_handoff",
          "label": "Dispatch Handoff",
          "status": "preview_only",
          "message": "Would hand prepared work into a future dispatch phase."
        },
        {
          "key": "verification_handoff",
          "label": "Verification Handoff",
          "status": "preview_only",
          "message": "Would hand completed work into a future verification phase."
        },
        {
          "key": "cleanup_handoff",
          "label": "Cleanup Handoff",
          "status": "preview_only",
          "message": "Would hand terminal work into a future cleanup phase."
        }
      ],
      "message": "Clone preparation is the only enabled real execution step in this phase. Dispatch, verification, cleanup, and locks remain preview-only or disabled."
    },
    "execution_request_preview": {
      "request_shape": "future_execution_submission",
      "preview_only": true,
      "batch_id": "sutw_batch_1234567890abcdef1234567890abcdef",
      "report_ids": [
        "admin:search:Executive Summary Dashboard"
      ],
      "time_range": {
        "label": "Last 24 hours",
        "earliest": "-24h@h",
        "latest": "now"
      },
      "acknowledged": true,
      "execution_phases": [
        "clone_preparation",
        "dispatch_handoff",
        "verification_handoff",
        "cleanup_handoff"
      ],
      "message": "This execution request preview is backend-generated for preflight review only. No clone, dispatch, verification, or cleanup action runs in this phase."
    },
    "execution_enablement": {
      "current_enablement_state": "enabled",
      "enabled_boundary": {
        "key": "clone_preparation",
        "label": "Clone Preparation",
        "state": "enabled"
      },
      "overall_preview_only": false,
      "overall_execution_enabled": false,
      "blocked_boundaries": [
        {
          "key": "dispatch_handoff",
          "label": "Dispatch Handoff",
          "state": "eligible_for_enablement_review"
        },
        {
          "key": "verification_handoff",
          "label": "Verification Handoff",
          "state": "defined_disabled"
        },
        {
          "key": "cleanup_handoff",
          "label": "Cleanup Handoff",
          "state": "defined_disabled"
        }
      ],
      "boundary_statuses": [
        {
          "boundary": "clone_preparation",
          "label": "Clone Preparation",
          "state": "enabled",
          "message": "Clone preparation executed safely. Prepared report inputs are ready for later dispatch review, but no clone job, SPL dispatch, or report modification was created."
        },
        {
          "boundary": "dispatch_handoff",
          "label": "Dispatch Handoff",
          "state": "eligible_for_enablement_review",
          "message": "Dispatch handoff is the next boundary eligible for enablement review, but it remains disabled."
        },
        {
          "boundary": "verification_handoff",
          "label": "Verification Handoff",
          "state": "defined_disabled",
          "message": "Internal verification-handoff boundaries are defined for a later execution-backed phase, but they remain disabled in this phase."
        },
        {
          "boundary": "cleanup_handoff",
          "label": "Cleanup Handoff",
          "state": "defined_disabled",
          "message": "Internal cleanup-handoff boundaries are defined so terminal execution work can move into a later cleanup phase after backend enablement."
        }
      ],
      "clone_preparation_observation": {
        "state": "prepared",
        "prepared_report_count": 1,
        "executed_at": "2026-03-09T08:00:02Z",
        "message": "Clone preparation executed safely. Prepared report inputs are ready for later dispatch review, but no clone job, SPL dispatch, or report modification was created."
      },
      "message": "Clone preparation is the only enabled real execution boundary in this phase. Dispatch handoff, verification handoff, cleanup handoff, and locks remain disabled."
    },
    "execution_action_review": {
      "review_state": "execution_blocked",
      "execution_allowed": false,
      "preview_only": false,
      "decision_reason": "Execution remains blocked overall because only clone preparation is enabled in this phase, while dispatch, verification, cleanup, and locks remain server-side gated.",
      "next_backend_step": "dispatch_enablement_review",
      "decision_inputs": [
        {
          "source": "execution_readiness",
          "summary": "Overall execution remains disabled while execution mode is limited to controlled clone preparation."
        },
        {
          "source": "phase_capabilities",
          "summary": "Execution phase is clone_preparation_enabled and the next allowed transition is dispatch_enablement_review."
        },
        {
          "source": "transition_policy",
          "summary": "Start Execution remains listed as a disallowed action, and the next backend phase is dispatch_enablement_review."
        },
        {
          "source": "action_intents",
          "summary": "Execution-oriented intents beyond clone preparation remain disabled by server-side gating."
        },
        {
          "source": "execution_plan",
          "summary": "The execution plan now includes 4 high-level steps, with clone preparation enabled and later phases remaining preview-only."
        },
        {
          "source": "execution_request_preview",
          "summary": "The backend-generated future_execution_submission payload remains preflight-only for operator review."
        },
        {
          "source": "execution_enablement",
          "summary": "Clone Preparation is enabled as the only real execution boundary, while downstream boundaries remain blocked or under enablement review."
        }
      ],
      "message": "This execution-action review is backend-generated for controlled preflight review. Clone preparation may execute safely, but dispatch, verification, cleanup, and locks remain disabled."
    },
    "execution_phase_roadmap": {
      "current_phase": "clone_preparation_enabled",
      "next_phase": "dispatch_enablement_review",
      "execution_blocked": true,
      "blocked_reason": "Execution remains blocked overall because only clone preparation is enabled in this phase, while dispatch, verification, cleanup, and locks remain server-side gated.",
      "enablement_milestone": {
        "key": "dispatch_enablement_review",
        "label": "Dispatch Enablement Review",
        "summary": "A future backend-controlled review must approve the dispatch handoff boundary before the batch can move beyond safe clone preparation."
      },
      "preview_only": false,
      "roadmap_steps": [
        {
          "phase": "clone_preparation_enabled",
          "label": "Clone Preparation Enabled",
          "status": "current",
          "message": "Clone preparation executed safely. Prepared report inputs are ready for later dispatch review, but no clone job, SPL dispatch, or report modification was created."
        },
        {
          "phase": "dispatch_enablement_review",
          "label": "Dispatch Enablement Review",
          "status": "next",
          "message": "A future backend-controlled review must approve the dispatch handoff boundary before the batch can move beyond safe clone preparation."
        },
        {
          "phase": "dispatch_handoff",
          "label": "Dispatch Handoff",
          "status": "eligible_for_enablement_review",
          "message": "Dispatch handoff is the next boundary eligible for enablement review, but it remains disabled."
        },
        {
          "phase": "verification_handoff",
          "label": "Verification Handoff",
          "status": "defined_disabled",
          "message": "Internal verification-handoff boundaries are defined for a later execution-backed phase, but they remain disabled in this phase."
        },
        {
          "phase": "cleanup_handoff",
          "label": "Cleanup Handoff",
          "status": "defined_disabled",
          "message": "Internal cleanup-handoff boundaries are defined so terminal execution work can move into a later cleanup phase after backend enablement."
        }
      ],
      "message": "This execution-phase roadmap is backend-generated for planning only. Clone preparation is enabled and observable, while dispatch, verification, cleanup, and locks remain disabled."
    },
    "terminal": false,
    "recommended_poll_interval_ms": 2000,
    "created_at": "2026-03-09T08:00:00Z",
    "updated_at": "2026-03-09T08:00:02Z",
    "submission": {
      "acknowledged": true,
      "report_count": 1,
      "selected_reports": [
        {
          "id": "admin:search:Executive Summary Dashboard",
          "title": "Executive Summary Dashboard",
          "app": "search",
          "owner": "admin"
        }
      ],
      "time_range": {
        "label": "Last 24 hours",
        "earliest": "-24h@h",
        "latest": "now"
      }
    },
    "report_statuses": [
      {
        "report_id": "admin:search:Executive Summary Dashboard",
        "report_label": "Executive Summary Dashboard",
        "current_state": "validated",
        "sequence": 2,
        "timestamp": "2026-03-09T08:00:02Z",
        "message": "Report passed safe validation and is ready for the queue stage.",
        "history": [
          {
            "state": "pending",
            "sequence": 1,
            "timestamp": "2026-03-09T08:00:00Z",
            "message": "Report is pending safe validation."
          },
          {
            "state": "validated",
            "sequence": 2,
            "timestamp": "2026-03-09T08:00:02Z",
            "message": "Report passed safe validation and is ready for the queue stage."
          }
        ]
      }
    ],
    "events": [
      {
        "sequence": 1,
        "state": "accepted",
        "label": "Accepted",
        "timestamp": "2026-03-09T08:00:00Z",
        "message": "Batch accepted. A safe validation checkpoint is the next tracked lifecycle step."
      },
      {
        "sequence": 2,
        "state": "validated",
        "label": "Validated",
        "timestamp": "2026-03-09T08:00:02Z",
        "message": "Batch validation is complete. The tracked lifecycle will move into the stub queue next."
      }
    ],
    "progress": {
      "current_stage": "validated",
      "percent": 50,
      "completed_transitions": 1,
      "summary": "1 of 3 report status transitions completed.",
      "total_transitions": 3,
      "stages": [
        {
          "key": "accepted",
          "label": "Accepted",
          "status": "complete"
        },
        {
          "key": "validated",
          "label": "Validated",
          "status": "current"
        },
        {
          "key": "queued",
          "label": "Queued",
          "status": "pending"
        },
        {
          "key": "stub_complete",
          "label": "Stub Complete",
          "status": "pending"
        }
      ]
    }
  }
}
```

### Controlled Behavior

- The backend reads and safely advances the previously stored non-destructive batch record
- The backend may execute clone preparation once after safe validation is reached
- No clone jobs are created
- No dispatch, verification, cleanup, or lock activity occurs
- No SPL or unsafe execution details are exposed

## Endpoint 5

`GET /servicesNS/-/splunk_utility_tool_web/sutw/v1/batches/recent`

This endpoint returns a simple caller-scoped list of recent tracked batches so the frontend can reopen an existing batch in the current batch detail panel without creating any new backend state.

### Request Rules

- Method: `GET` only
- Authentication: required
- Query string: not supported, except for Splunk's optional cache-buster key `_` on GET requests
- Request body: not supported
- Only batches owned by the current caller session scope are returned
- The frontend may call this endpoint again at any time to refresh the recent-batch list

### Successful Response

```json
{
  "count": 2,
  "batches": [
    {
      "batch_id": "sutw_batch_1234567890abcdef1234567890abcdef",
      "lifecycle_state": "queued",
      "lifecycle_label": "Queued",
      "report_count": 2,
      "created_at": "2026-03-09T08:00:00Z",
      "updated_at": "2026-03-09T08:00:06Z",
      "terminal": false,
      "message": "All selected reports reached the non-destructive queue stage. Stub completion is next."
    }
  ]
}
```

### Safe Metadata Returned

- `batch_id`: the existing server-generated batch identifier
- `lifecycle_state`: the internal-safe display state key for the batch
- `lifecycle_label`: the display label for the current batch state
- `report_count`: the count of selected reports in the tracked batch
- `created_at`: the batch creation timestamp
- `updated_at`: the latest tracked batch update timestamp
- `terminal`: whether the batch reached terminal non-destructive stub completion
- `message`: the current safe display-oriented lifecycle message

The backend does not return report SPL, report payloads, session information, owner hashes, or any unsafe internal tracking details.

### Retention Note

- The returned recent-batch list reflects only the current process-memory tracked state for this phase
- Recent batches may disappear after a Splunk restart or Python process recycle
- No durable execution store is introduced by this endpoint

## Error Shape

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Human-readable error message"
  }
}
```

## Error Cases

- `400 INVALID_REQUEST` for malformed requests
- `400 MISSING_BODY` when a required request body is missing
- `400 INVALID_JSON_BODY` when a request body is not valid JSON
- `400 UNEXPECTED_FIELDS` when unsupported top-level fields are supplied
- `400 UNEXPECTED_TIME_RANGE_FIELDS` when unsupported `time_range` fields are supplied
- `400 INVALID_REPORT_IDS` when `report_ids` is not a valid array of strings
- `400 NO_REPORTS_SELECTED` when no report IDs are supplied for start-batch submission
- `400 DUPLICATE_REPORT_IDS` when duplicate report IDs are supplied
- `400 INVALID_TIME_RANGE` when the time range payload is invalid
- `400 INVALID_ACKNOWLEDGEMENT` when `acknowledged` is not a boolean
- `400 ACKNOWLEDGEMENT_REQUIRED` when review acknowledgement is not `true` for start-batch submission
- `400 UNSUPPORTED_QUERY` when unsupported query parameters are sent
- `400 UNSUPPORTED_BODY` when a request body is sent to a read-only endpoint that does not accept one
- `400 MISSING_BATCH_ID` when `batch_id` is not supplied for status retrieval
- `400 INVALID_BATCH_ID` when `batch_id` does not match the required format
- `400 INELIGIBLE_REPORT` when a submitted report is no longer eligible
- `401 AUTH_REQUIRED` when the Splunk session token is unavailable
- `404 ENDPOINT_NOT_FOUND` for unsupported paths
- `404 BATCH_NOT_FOUND` when the batch record does not exist in the current caller scope
- `405 METHOD_NOT_ALLOWED` for unsupported methods
- `502 REPORT_LOOKUP_FAILED` when Splunk report inventory cannot be retrieved
- `502 INVALID_REPORT_RESPONSE` when Splunk returns an unexpected payload


