# Endpoint Contract

## Status

Phase 23 implemented for eligible report retrieval, read-only submission preview, tracked start-batch submission, read-only recent batch retrieval, and read-only batch status retrieval with safe lifecycle progression, timeline events, per-report tracked statuses, per-report transition history, recent-batch refresh, explicit execution-readiness metadata, explicit phase-capability metadata, a lifecycle-policy block, action-intent metadata, an execution-plan preview block, and a backend-generated execution-request preview block in the tracked batch model.

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
- Each tracked batch now includes a safe execution-plan preview for future execution-backed behavior alignment
- Each tracked batch now includes a safe backend-generated execution-request preview for future execution-backed preflight alignment
- Current tracked batches remain temporary process-memory records for this phase and are not yet durable execution records
- Current lifecycle states are `accepted`, `validated`, `queued`, and `stub_complete`
- Current report states are `pending`, `validated`, `queued`, and `stub_complete`
- No clone, dispatch, verification, cleanup, locks, or destructive execution is performed

## Presentation Note

- Phase 23 does not change the backend request surface
- The existing batch status response now drives a dedicated frontend batch detail panel
- That panel now groups recent tracked batch selection, manual recent-batch refresh, temporary-retention hints, batch overview, execution-readiness metadata, phase-capability metadata, lifecycle-policy metadata, action-intent metadata, execution-plan preview metadata, execution-request preview metadata, batch lifecycle timeline, per-report current statuses, and per-report transition histories in one place
- The current tracked-state model is intentionally kept aligned with the future execution model through stable `batch_id` reuse, while storage remains temporary and non-destructive in this phase

## Endpoint 1

`GET /servicesNS/-/splunk_utility_tool_web/sutw/v1/reports`

This endpoint is exposed to Splunk Web through `splunkd/__raw` and returns the eligible report list used by the frontend selection step.

### Request Rules

- Method: `GET` only
- Query string: not supported
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

This endpoint returns safe tracked status data for a previously accepted batch. It is read-only and is used by the frontend progress and final summary sections after submission.

### Request Rules

- Method: `GET` only
- Authentication: required
- Request body: not supported
- Query string: only `batch_id` is supported
- `batch_id` must match the server-generated batch ID format exactly
- The batch record must exist and belong to the current caller session scope

### Lifecycle Progression

- The status endpoint progresses the stored batch through safe states when it is refreshed or polled
- The per-report progression is `pending` -> `validated` -> `queued` -> `stub_complete`
- The batch progression is `accepted` -> `validated` -> `queued` -> `stub_complete`
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
- `execution_enabled` remains `false` for this phase
- The metadata is descriptive only and does not enable clone, dispatch, verification, cleanup, or lock behavior

### Phase-Capability Metadata

- Each tracked batch includes a `phase_capabilities` object for operator display and later execution-backed phase alignment
- This metadata contains only safe display-oriented fields such as `execution_phase`, `tracked_only`, `next_allowed_transition`, `capabilities`, and `message`
- Each capability entry contains only `key`, `label`, and `enabled`
- The capability block is descriptive only and does not enable clone, dispatch, verification, cleanup, or lock behavior

### Lifecycle-Policy Metadata

- Each tracked batch includes a `transition_policy` object for operator display and later backend transition alignment
- This metadata contains only safe display-oriented fields such as `next_backend_phase`, `allowed_actions`, `disallowed_actions`, and `policy_message`
- Each action entry contains only `key` and `label`
- The lifecycle-policy block is descriptive only and does not enable clone, dispatch, verification, cleanup, or lock behavior

### Action-Intent Metadata

- Each tracked batch includes an `action_intents` object for operator display and later server-gated action alignment
- This metadata contains only safe display-oriented fields such as `enabled_actions`, `disabled_actions`, `action_reasoning`, and `message`
- Each action entry contains only `key`, `label`, and `intent`
- The action-intent block is descriptive only and does not enable clone, dispatch, verification, cleanup, or lock behavior

### Execution-Plan Preview Metadata

- Each tracked batch includes an `execution_plan` object for operator display and later execution-backed preview alignment
- This metadata contains only safe display-oriented fields such as `plan_state`, `preview_only`, `planned_reports`, `planned_steps`, and `message`
- Each planned report entry contains only `report_id` and `report_label`
- Each planned step entry contains only `key`, `label`, `status`, and `message`
- The execution-plan block is descriptive only and does not enable clone, dispatch, verification, cleanup, or lock behavior

### Execution-Request Preview Metadata

- Each tracked batch includes an `execution_request_preview` object for operator display and later execution-backed preflight alignment
- This metadata contains only safe display-oriented fields such as `request_shape`, `preview_only`, `batch_id`, `report_ids`, `time_range`, `acknowledged`, `execution_phases`, and `message`
- `report_ids` contains only the selected safe report identifiers already accepted into the tracked batch record
- `time_range` contains only the submitted high-level range fields: `label`, `earliest`, and `latest`
- The execution-request preview block is descriptive only and does not enable clone, dispatch, verification, cleanup, or lock behavior

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
      "execution_mode": "stub_non_destructive",
      "execution_enabled": false,
      "message": "Tracked status is available for operator review, but real execution remains disabled. Batch data stays in temporary process memory only in this phase."
    },
    "phase_capabilities": {
      "execution_phase": "tracked_only",
      "tracked_only": true,
      "next_allowed_transition": "status_refresh",
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
          "key": "start_execution",
          "label": "Start Execution",
          "enabled": false
        }
      ],
      "message": "This batch supports tracked review only. Real execution transitions remain disabled in this phase."
    },
    "transition_policy": {
      "next_backend_phase": "tracked_status_progression",
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
      "policy_message": "This batch may continue through tracked status refresh only. Execution-backed transitions remain disabled until a later phase."
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
        "enabled": "Read-only review and navigation actions are allowed while the tracked batch continues through safe lifecycle polling.",
        "disabled": "Execution-backed actions remain server-side gated until a later execution-enabled phase."
      },
      "message": "Action intents are descriptive only. Server-side gating keeps execution disabled in this phase."
    },
    "execution_plan": {
      "plan_state": "preview_only",
      "preview_only": true,
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
          "status": "preview_only",
          "message": "Would prepare the selected reports for a future clone-oriented execution phase."
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
      "message": "This execution plan is a high-level preview only. No clone, dispatch, verification, or cleanup action runs in this phase."
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

### Read-Only Behavior

- The backend reads and safely advances only the previously stored non-destructive batch record
- No jobs are created
- No clone, dispatch, verification, cleanup, or lock activity occurs
- No SPL or unsafe execution details are exposed

## Endpoint 5

`GET /servicesNS/-/splunk_utility_tool_web/sutw/v1/batches/recent`

This endpoint returns a simple caller-scoped list of recent tracked batches so the frontend can reopen an existing batch in the current batch detail panel without creating any new backend state.

### Request Rules

- Method: `GET` only
- Authentication: required
- Query string: not supported
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
