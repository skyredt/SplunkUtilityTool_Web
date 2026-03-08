require([
    "jquery",
    "splunkjs/mvc/simplexml/ready!"
], function($) {
    var appNamespace = "splunk_utility_tool_web";
    var defaultBatchPollIntervalMs = 2000;
    var $shell = $("#sutw-shell");
    var $reportList = $("#sutw-report-list");
    var $reportFeedback = $("#sutw-report-feedback");
    var $rangeOptions = $(".sutw-range-option");
    var $reviewAcknowledgement = $("#sutw-review-ack");
    var $startButton = $("#sutw-start-button");
    var $progressFill = $("#sutw-progress-fill");
    var $progressText = $("#sutw-progress-text");
    var $progressState = $("#sutw-progress-state");
    var $progressNote = $("#sutw-progress-note");
    var $summaryBatchId = $("#sutw-summary-batch-id");
    var $summaryStatus = $("#sutw-summary-status");
    var $summaryReportCount = $("#sutw-summary-report-count");
    var $summaryUpdatedAt = $("#sutw-summary-updated-at");
    var $summaryNote = $("#sutw-summary-note");
    var $executionTrackingMode = $("#sutw-execution-tracking-mode");
    var $executionStorageMode = $("#sutw-execution-storage-mode");
    var $executionMode = $("#sutw-execution-mode");
    var $executionEnabled = $("#sutw-execution-enabled");
    var $executionNote = $("#sutw-execution-note");
    var $capabilityPhase = $("#sutw-capability-phase");
    var $capabilityTrackedOnly = $("#sutw-capability-tracked-only");
    var $capabilityNextTransition = $("#sutw-capability-next-transition");
    var $capabilityList = $("#sutw-capability-list");
    var $capabilityNote = $("#sutw-capability-note");
    var $policyNextPhase = $("#sutw-policy-next-phase");
    var $policyAllowedActions = $("#sutw-policy-allowed-actions");
    var $policyDisallowedActions = $("#sutw-policy-disallowed-actions");
    var $policyNote = $("#sutw-policy-note");
    var $intentEnabledActions = $("#sutw-intent-enabled-actions");
    var $intentDisabledActions = $("#sutw-intent-disabled-actions");
    var $intentEnabledNote = $("#sutw-intent-enabled-note");
    var $intentDisabledNote = $("#sutw-intent-disabled-note");
    var $intentNote = $("#sutw-intent-note");
    var $planState = $("#sutw-plan-state");
    var $planPreviewOnly = $("#sutw-plan-preview-only");
    var $planReports = $("#sutw-plan-reports");
    var $planSteps = $("#sutw-plan-steps");
    var $planNote = $("#sutw-plan-note");
    var $requestShape = $("#sutw-request-shape");
    var $requestPreviewOnly = $("#sutw-request-preview-only");
    var $requestAcknowledged = $("#sutw-request-acknowledged");
    var $requestBatchId = $("#sutw-request-batch-id");
    var $requestTimeRange = $("#sutw-request-time-range");
    var $requestReportIds = $("#sutw-request-report-ids");
    var $requestPhases = $("#sutw-request-phases");
    var $requestNote = $("#sutw-request-note");
    var $batchDetailEmpty = $("#sutw-batch-detail-empty");
    var $batchDetailContent = $("#sutw-batch-detail-content");
    var $reportStatusList = $("#sutw-report-status-list");
    var $eventTimeline = $("#sutw-event-timeline");
    var $recentBatchList = $("#sutw-recent-batch-list");
    var $recentBatchRefreshButton = $("#sutw-recent-batch-refresh");
    var $recentBatchNote = $("#sutw-recent-batch-note");
    var defaultActionNote = "Select at least one report and acknowledge review to enable the tracked non-destructive start-batch submission.";
    var defaultReportLoadMessage = "Loading eligible reports...";
    var defaultProgressStateText = "Current state: Draft preview";
    var defaultSummaryNote = "No tracked batch yet. Submit a validated request to create the first server-generated batch ID. Current tracked batches are temporary process-memory records in this phase.";
    var defaultRecentBatchMessage = "No tracked batches yet.";
    var defaultRecentBatchNote = "Recent tracked batches are temporary process-memory records in this phase and may disappear after a Splunk restart or Python process recycle.";
    var defaultExecutionReadinessNote = "Tracked status is available for operator review, but real execution remains disabled. Batch data stays in temporary process memory only in this phase.";
    var defaultPhaseCapabilityNote = "This batch supports tracked review only. Real execution transitions remain disabled in this phase.";
    var defaultTransitionPolicyNote = "This batch may continue through tracked status refresh only. Execution-backed transitions remain disabled until a later phase.";
    var defaultActionIntentNote = "Action intents are descriptive only. Server-side gating keeps execution disabled in this phase.";
    var defaultExecutionPlanNote = "This execution plan is a high-level preview only. No clone, dispatch, verification, or cleanup action runs in this phase.";
    var defaultExecutionRequestPreviewNote = "This execution request preview is backend-generated for preflight review only. No clone, dispatch, verification, or cleanup action runs in this phase.";
    var isSubmitting = false;
    var hasLoadedPreview = false;
    var submissionActionNote = "";
    var currentBatchId = "";
    var batchStatusPollTimer = 0;
    var recentBatches = [];
    var isRefreshingRecentBatches = false;

    function getLocaleRoot() {
        var pathParts = window.location.pathname.split("/");

        if (pathParts.length > 1 && pathParts[1]) {
            return "/" + pathParts[1];
        }

        return "";
    }

    function buildEligibleReportsUrl() {
        return getLocaleRoot() + "/splunkd/__raw/servicesNS/-/" + appNamespace + "/sutw/v1/reports";
    }

    function buildStartBatchPreviewUrl() {
        return getLocaleRoot() + "/splunkd/__raw/servicesNS/-/" + appNamespace + "/sutw/v1/batches/preview";
    }

    function buildStartBatchUrl() {
        return getLocaleRoot() + "/splunkd/__raw/servicesNS/-/" + appNamespace + "/sutw/v1/batches";
    }

    function buildRecentBatchesUrl() {
        return getLocaleRoot() + "/splunkd/__raw/servicesNS/-/" + appNamespace + "/sutw/v1/batches/recent";
    }

    function buildBatchStatusUrl(batchId) {
        return getLocaleRoot() + "/splunkd/__raw/servicesNS/-/" + appNamespace + "/sutw/v1/batches/status?batch_id=" + encodeURIComponent(batchId);
    }

    function escapeHtml(value) {
        return $("<div>").text(value || "").html();
    }

    function getRecentBatchRetentionHint() {
        return "Tracked batches stay in temporary process memory only in this phase and may disappear after a Splunk restart or Python process recycle.";
    }

    function formatLocalTime(value) {
        if (!(value instanceof Date) || isNaN(value.getTime())) {
            return "unknown time";
        }

        return value.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        });
    }

    function setRecentBatchNote(message) {
        $recentBatchNote.text(message || defaultRecentBatchNote);
    }

    function clearBatchStatusPoll() {
        if (batchStatusPollTimer) {
            window.clearTimeout(batchStatusPollTimer);
            batchStatusPollTimer = 0;
        }
    }

    function getReportRows() {
        return $reportList.find(".sutw-report-row");
    }

    function getSelectedReportRows() {
        return getReportRows().filter(".is-selected");
    }

    function getSelectedReportIds() {
        return getSelectedReportRows().map(function() {
            return $(this).data("reportId");
        }).get();
    }

    function setShellStatus(message) {
        $("#sutw-shell-status").text(message);
    }

    function setSummaryState(batchIdText, statusText, reportCountText, updatedAtText, noteText) {
        $summaryBatchId.text(batchIdText);
        $summaryStatus.text(statusText);
        $summaryReportCount.text(reportCountText);
        $summaryUpdatedAt.text(updatedAtText);
        $summaryNote.text(noteText);
    }

    function formatModeLabel(value, fallbackValue) {
        var rawValue = value || fallbackValue || "unknown";

        return rawValue
            .replace(/_/g, " ")
            .replace(/\b\w/g, function(character) {
                return character.toUpperCase();
            });
    }

    function setExecutionReadinessState(trackingModeText, storageModeText, executionModeText, executionEnabledText, noteText) {
        $executionTrackingMode.text(trackingModeText);
        $executionStorageMode.text(storageModeText);
        $executionMode.text(executionModeText);
        $executionEnabled.text(executionEnabledText);
        $executionNote.text(noteText);
    }

    function renderCapabilityList(capabilities, emptyMessage) {
        if (!Array.isArray(capabilities) || capabilities.length === 0) {
            $capabilityList.html("<li>" + escapeHtml(emptyMessage || "No phase capabilities available.") + "</li>");
            return;
        }

        $capabilityList.html($.map(capabilities, function(capability) {
            var label = capability && capability.label ? capability.label : formatModeLabel(capability && capability.key, "unknown_capability");
            var enabledText = capability && capability.enabled === true ? "Enabled" : "Disabled";

            return "<li>" + escapeHtml(label + " | " + enabledText) + "</li>";
        }).join(""));
    }

    function setPhaseCapabilitiesState(phaseText, trackedOnlyText, nextTransitionText, capabilities, noteText) {
        $capabilityPhase.text(phaseText);
        $capabilityTrackedOnly.text(trackedOnlyText);
        $capabilityNextTransition.text(nextTransitionText);
        $capabilityNote.text(noteText);
        renderCapabilityList(capabilities, "No phase capabilities available.");
    }

    function renderPolicyActionList($target, actions, emptyMessage) {
        if (!Array.isArray(actions) || actions.length === 0) {
            $target.html("<li>" + escapeHtml(emptyMessage || "No actions listed.") + "</li>");
            return;
        }

        $target.html($.map(actions, function(action) {
            var label = action && action.label ? action.label : formatModeLabel(action && action.key, "unknown_action");
            return "<li>" + escapeHtml(label) + "</li>";
        }).join(""));
    }

    function setTransitionPolicyState(nextPhaseText, allowedActions, disallowedActions, noteText) {
        $policyNextPhase.text(nextPhaseText);
        $policyNote.text(noteText);
        renderPolicyActionList($policyAllowedActions, allowedActions, "No allowed actions listed.");
        renderPolicyActionList($policyDisallowedActions, disallowedActions, "No disallowed actions listed.");
    }

    function renderActionIntentList($target, actions, emptyMessage) {
        if (!Array.isArray(actions) || actions.length === 0) {
            $target.html("<li>" + escapeHtml(emptyMessage || "No action intents listed.") + "</li>");
            return;
        }

        $target.html($.map(actions, function(action) {
            var label = action && action.label ? action.label : formatModeLabel(action && action.key, "unknown_action");
            var intent = action && action.intent ? formatModeLabel(action.intent, "unspecified") : "Unspecified";
            return "<li>" + escapeHtml(label + " | " + intent) + "</li>";
        }).join(""));
    }

    function setActionIntentState(enabledActions, disabledActions, enabledReasonText, disabledReasonText, noteText) {
        renderActionIntentList($intentEnabledActions, enabledActions, "No enabled action intents listed.");
        renderActionIntentList($intentDisabledActions, disabledActions, "No disabled action intents listed.");
        $intentEnabledNote.text(enabledReasonText);
        $intentDisabledNote.text(disabledReasonText);
        $intentNote.text(noteText);
    }

    function renderExecutionPlanReports(reports, emptyMessage) {
        if (!Array.isArray(reports) || reports.length === 0) {
            $planReports.html("<li>" + escapeHtml(emptyMessage || "No planned reports listed.") + "</li>");
            return;
        }

        $planReports.html($.map(reports, function(report) {
            var label = report && report.report_label ? report.report_label : "Unknown report";
            var reportId = report && report.report_id ? report.report_id : "unknown";
            return "<li>" + escapeHtml(label + " | " + reportId) + "</li>";
        }).join(""));
    }

    function renderExecutionPlanSteps(steps, emptyMessage) {
        if (!Array.isArray(steps) || steps.length === 0) {
            $planSteps.html("<li>" + escapeHtml(emptyMessage || "No planned steps listed.") + "</li>");
            return;
        }

        $planSteps.html($.map(steps, function(step) {
            var label = step && step.label ? step.label : formatModeLabel(step && step.key, "unknown_step");
            var status = step && step.status ? formatModeLabel(step.status, "preview_only") : "Preview Only";
            var message = step && step.message ? step.message : "No planned-step detail available.";
            return "<li>" + escapeHtml(label + " | " + status + " | " + message) + "</li>";
        }).join(""));
    }

    function setExecutionPlanState(planStateText, previewOnlyText, plannedReports, plannedSteps, noteText) {
        $planState.text(planStateText);
        $planPreviewOnly.text(previewOnlyText);
        $planNote.text(noteText);
        renderExecutionPlanReports(plannedReports, "No planned reports listed.");
        renderExecutionPlanSteps(plannedSteps, "No planned steps listed.");
    }

    function renderExecutionRequestList($target, items, emptyMessage) {
        if (!Array.isArray(items) || items.length === 0) {
            $target.html("<li>" + escapeHtml(emptyMessage || "No items listed.") + "</li>");
            return;
        }

        $target.html($.map(items, function(item) {
            return "<li>" + escapeHtml(item) + "</li>";
        }).join(""));
    }

    function formatExecutionRequestTimeRange(timeRange) {
        if (!timeRange || typeof timeRange !== "object") {
            return "No time range available.";
        }

        var label = timeRange.label || "Unknown range";
        var earliest = timeRange.earliest || "unknown";
        var latest = timeRange.latest || "unknown";

        return label + " | " + earliest + " to " + latest;
    }

    function setExecutionRequestPreviewState(requestShapeText, previewOnlyText, acknowledgedText, batchIdText, timeRangeText, reportIds, phases, noteText) {
        $requestShape.text(requestShapeText);
        $requestPreviewOnly.text(previewOnlyText);
        $requestAcknowledged.text(acknowledgedText);
        $requestBatchId.text(batchIdText);
        $requestTimeRange.text(timeRangeText);
        $requestNote.text(noteText);
        renderExecutionRequestList($requestReportIds, reportIds, "No report IDs listed.");
        renderExecutionRequestList($requestPhases, phases, "No execution phases listed.");
    }

    function setBatchDetailMode(hasTrackedBatch) {
        $batchDetailEmpty.prop("hidden", hasTrackedBatch);
        $batchDetailContent.prop("hidden", !hasTrackedBatch);
    }

    function sortRecentBatches() {
        recentBatches.sort(function(left, right) {
            var leftUpdatedAt = left && left.updated_at ? left.updated_at : "";
            var rightUpdatedAt = right && right.updated_at ? right.updated_at : "";
            var leftCreatedAt = left && left.created_at ? left.created_at : "";
            var rightCreatedAt = right && right.created_at ? right.created_at : "";
            var leftBatchId = left && left.batch_id ? left.batch_id : "";
            var rightBatchId = right && right.batch_id ? right.batch_id : "";

            if (rightUpdatedAt !== leftUpdatedAt) {
                return rightUpdatedAt.localeCompare(leftUpdatedAt);
            }

            if (rightCreatedAt !== leftCreatedAt) {
                return rightCreatedAt.localeCompare(leftCreatedAt);
            }

            return rightBatchId.localeCompare(leftBatchId);
        });
    }

    function summarizeBatch(batch) {
        var submission = batch && batch.submission ? batch.submission : null;
        var reportCount = submission && typeof submission.report_count === "number" ? submission.report_count : 0;

        return {
            batch_id: batch && batch.batch_id ? batch.batch_id : "",
            lifecycle_state: batch && batch.lifecycle_state ? batch.lifecycle_state : "",
            lifecycle_label: batch && batch.lifecycle_label ? batch.lifecycle_label : "",
            report_count: reportCount,
            created_at: batch && batch.created_at ? batch.created_at : "",
            updated_at: batch && batch.updated_at ? batch.updated_at : "",
            terminal: !!(batch && batch.terminal),
            message: batch && batch.state_message ? batch.state_message : ""
        };
    }

    function upsertRecentBatchSummary(batch) {
        var summary = summarizeBatch(batch);
        var didUpdate = false;

        if (!summary.batch_id) {
            return;
        }

        recentBatches = $.map(recentBatches, function(existingBatch) {
            if (existingBatch.batch_id === summary.batch_id) {
                didUpdate = true;
                return summary;
            }

            return existingBatch;
        });

        if (!didUpdate) {
            recentBatches.push(summary);
        }

        sortRecentBatches();
    }

    function renderRecentBatches(batches, emptyMessage) {
        if (!Array.isArray(batches) || batches.length === 0) {
            $recentBatchList.html("<li>" + escapeHtml(emptyMessage || defaultRecentBatchMessage) + "</li>");
            return;
        }

        $recentBatchList.html($.map(batches, function(batch) {
            var batchId = batch.batch_id || "Unknown batch";
            var lifecycleLabel = batch.lifecycle_label || batch.lifecycle_state || "Unknown state";
            var reportCount = typeof batch.report_count === "number" ? batch.report_count : 0;
            var updatedAt = batch.updated_at || batch.created_at || "Unknown update";
            var isActiveBatch = batchId === currentBatchId;
            var actionLabel = isActiveBatch ? "Viewing" : "Open";
            var metaText = lifecycleLabel + " | " + formatReportCount(reportCount) + " | Updated: " + updatedAt;

            if (batch.message) {
                metaText += " | " + batch.message;
            }

            return [
                "<li>",
                '  <button class="sutw-report-row sutw-recent-batch-select' + (isActiveBatch ? " is-selected" : "") + '" type="button" data-batch-id="' + escapeHtml(batchId) + '" data-batch-label="' + escapeHtml(batchId) + '">',
                '    <span class="sutw-report-row__main">',
                '      <span class="sutw-report-row__title">' + escapeHtml(batchId) + "</span>",
                '      <span class="sutw-report-row__meta">' + escapeHtml(metaText) + "</span>",
                "    </span>",
                '    <span class="sutw-report-row__state">' + escapeHtml(actionLabel) + "</span>",
                "  </button>",
                "</li>"
            ].join("");
        }).join(""));
    }

    function renderEventTimeline(events, emptyMessage) {
        if (!Array.isArray(events) || events.length === 0) {
            $eventTimeline.html("<li>" + escapeHtml(emptyMessage || "No lifecycle events yet.") + "</li>");
            return;
        }

        $eventTimeline.html($.map(events, function(event) {
            var label = event.label || event.state || "Unknown state";
            var sequence = typeof event.sequence === "number" ? "#" + event.sequence + " " : "";
            var timestamp = event.timestamp || "Unknown time";
            var message = event.message || "No event message available.";

            return [
                "<li>",
                "  <strong>" + escapeHtml(sequence + label) + "</strong><br />",
                "  <span>" + escapeHtml(timestamp + " - " + message) + "</span>",
                "</li>"
            ].join("");
        }).join(""));
    }

    function renderReportStatuses(reportStatuses, emptyMessage) {
        if (!Array.isArray(reportStatuses) || reportStatuses.length === 0) {
            $reportStatusList.html("<li>" + escapeHtml(emptyMessage || "No tracked report statuses yet.") + "</li>");
            return;
        }

        $reportStatusList.html($.map(reportStatuses, function(reportStatus) {
            var label = reportStatus.report_label || reportStatus.report_id || "Unknown report";
            var state = reportStatus.current_state || "unknown";
            var sequence = typeof reportStatus.sequence === "number" ? "Stage " + reportStatus.sequence : "Stage unknown";
            var timestamp = reportStatus.timestamp || "Unknown time";
            var message = reportStatus.message || "No status message available.";
            var history = Array.isArray(reportStatus.history) ? reportStatus.history : [];
            var historyHtml = history.length ? $.map(history, function(historyEntry) {
                var historyState = historyEntry.state || "unknown";
                var historySequence = typeof historyEntry.sequence === "number" ? "#" + historyEntry.sequence : "#?";
                var historyTimestamp = historyEntry.timestamp || "Unknown time";
                var historyMessage = historyEntry.message || "No history message available.";

                return [
                    "<li>",
                    "  <strong>" + escapeHtml(historySequence + " " + historyState) + "</strong><br />",
                    "  <span>" + escapeHtml(historyTimestamp + " - " + historyMessage) + "</span>",
                    "</li>"
                ].join("");
            }).join("") : "<li>No transition history yet.</li>";

            return [
                "<li>",
                "  <details>",
                "    <summary>" + escapeHtml(label + " | " + sequence + " | " + state) + "</summary>",
                "    <div>" + escapeHtml(timestamp + " - " + message) + "</div>",
                "    <ul>" + historyHtml + "</ul>",
                "  </details>",
                "</li>"
            ].join("");
        }).join(""));
    }

    function resetSummaryState() {
        setSummaryState(
            "No tracked batch yet",
            "Waiting for first submission",
            "0 reports",
            "No tracked status yet",
            defaultSummaryNote
        );
        setExecutionReadinessState(
            "Tracked Batch",
            "Process Memory",
            "Stub Non Destructive",
            "No",
            defaultExecutionReadinessNote
        );
        setPhaseCapabilitiesState(
            "Tracked Only",
            "Yes",
            "Status Refresh",
            [
                { label: "View Tracked Status", enabled: true },
                { label: "Reopen Recent Batch", enabled: true },
                { label: "Start Execution", enabled: false }
            ],
            defaultPhaseCapabilityNote
        );
        setTransitionPolicyState(
            "Tracked Status Progression",
            [
                { label: "View Batch Details" },
                { label: "Refresh Status" },
                { label: "Reopen Recent Batch" }
            ],
            [
                { label: "Start Execution" },
                { label: "Dispatch Clone" },
                { label: "Run Verification" },
                { label: "Perform Cleanup" }
            ],
            defaultTransitionPolicyNote
        );
        setActionIntentState(
            [
                { label: "View Batch Details", intent: "review" },
                { label: "Refresh Status", intent: "observe" },
                { label: "Reopen Recent Batch", intent: "review" }
            ],
            [
                { label: "Start Execution", intent: "execute" },
                { label: "Dispatch Clone", intent: "clone" },
                { label: "Run Verification", intent: "verify" },
                { label: "Perform Cleanup", intent: "cleanup" }
            ],
            "Read-only review and navigation actions are allowed while the tracked batch continues through safe lifecycle polling.",
            "Execution-backed actions remain server-side gated until a later execution-enabled phase.",
            defaultActionIntentNote
        );
        setExecutionPlanState(
            "Preview Only",
            "Yes",
            [],
            [
                { label: "Clone Preparation", status: "preview_only", message: "Would prepare the selected reports for a future clone-oriented execution phase." },
                { label: "Dispatch Handoff", status: "preview_only", message: "Would hand prepared work into a future dispatch phase." },
                { label: "Verification Handoff", status: "preview_only", message: "Would hand completed work into a future verification phase." },
                { label: "Cleanup Handoff", status: "preview_only", message: "Would hand terminal work into a future cleanup phase." }
            ],
            defaultExecutionPlanNote
        );
        setExecutionRequestPreviewState(
            "Future Execution Submission",
            "Yes",
            "Yes",
            "No tracked batch yet",
            "Last 24 hours | -24h@h to now",
            [],
            [
                "Clone Preparation",
                "Dispatch Handoff",
                "Verification Handoff",
                "Cleanup Handoff"
            ],
            defaultExecutionRequestPreviewNote
        );
        setBatchDetailMode(false);
        renderReportStatuses([], "No tracked report statuses yet.");
        renderEventTimeline([], "No tracked lifecycle events yet.");
    }

    function clearTrackedBatch() {
        clearBatchStatusPoll();

        if (currentBatchId) {
            hasLoadedPreview = false;
            setProgressState(
                0,
                "Loading submission preview...",
                "Fetching a safe read-only preview from the backend.",
                defaultProgressStateText
            );
        }

        currentBatchId = "";
        resetSummaryState();
        renderRecentBatches(recentBatches, defaultRecentBatchMessage);
    }

    function getActiveTimeRange() {
        var $activeRange = $rangeOptions.filter(".is-active").first();

        return {
            label: $activeRange.data("rangeLabel"),
            earliest: $activeRange.data("earliest"),
            latest: $activeRange.data("latest")
        };
    }

    function buildSubmissionPayload() {
        return {
            acknowledged: $reviewAcknowledgement.is(":checked"),
            report_ids: getSelectedReportIds(),
            time_range: getActiveTimeRange()
        };
    }

    function buildReportRow(report) {
        var title = report.title || report.name || "Unnamed Report";
        var metaText = "App: " + (report.app || "unknown") + " | Owner: " + (report.owner || "unknown");

        if (report.description) {
            metaText = report.description + " | " + metaText;
        }

        return [
            "<li>",
            '  <button class="sutw-report-row" type="button" data-report-id="' + escapeHtml(report.id) + '" data-report-label="' + escapeHtml(title) + '">',
            '    <span class="sutw-report-row__main">',
            '      <span class="sutw-report-row__title">' + escapeHtml(title) + "</span>",
            '      <span class="sutw-report-row__meta">' + escapeHtml(metaText) + "</span>",
            "    </span>",
            '    <span class="sutw-report-row__state">Click to select</span>',
            "  </button>",
            "</li>"
        ].join("");
    }

    function renderEligibleReports(reports) {
        if (!Array.isArray(reports) || reports.length === 0) {
            $reportList.empty();
            $reportFeedback.text("No eligible reports are available for this user.");
            updateDraftSelection();
            return;
        }

        $reportList.html($.map(reports, buildReportRow).join(""));
        $reportFeedback.text("Loaded " + reports.length + " eligible reports from the backend.");
        updateDraftSelection();
    }

    function extractErrorMessage(jqXHR, fallbackMessage) {
        var responseBody = jqXHR.responseJSON;

        if (!responseBody && jqXHR.responseText) {
            try {
                responseBody = JSON.parse(jqXHR.responseText);
            } catch (error) {
                responseBody = null;
            }
        }

        if (responseBody && responseBody.error && responseBody.error.message) {
            return responseBody.error.message;
        }

        return fallbackMessage;
    }

    function renderReportLoadFailure(message) {
        $reportList.empty();
        $reportFeedback.text(message);
        setShellStatus("Splunk Utility Tool Web loaded, but eligible report retrieval failed.");
        updateDraftSelection();
    }

    function setProgressState(percent, text, note, stateText) {
        $progressFill.css("width", Math.max(0, Math.min(100, percent)) + "%");
        $progressText.text(text);
        $progressNote.text(note);
        $progressState.text(stateText || defaultProgressStateText);
    }

    function formatReportCount(count) {
        return count + (count === 1 ? " report" : " reports");
    }

    function applyPreviewResponse(response) {
        var preview = response && response.preview ? response.preview : null;
        var progress = preview && preview.progress ? preview.progress : null;

        if (currentBatchId) {
            return;
        }

        if (!progress) {
            setProgressState(
                0,
                "Preview unavailable",
                "The backend returned an invalid preview response.",
                defaultProgressStateText
            );
            return;
        }

        setProgressState(
            progress.percent || 0,
            progress.summary || "Read-only preview loaded.",
            response.message || "Submission preview validated successfully.",
            defaultProgressStateText
        );
        hasLoadedPreview = true;
    }

    function scheduleBatchStatusPoll(batch) {
        var pollDelayMs;

        clearBatchStatusPoll();

        if (!batch || batch.terminal || !currentBatchId) {
            return;
        }

        pollDelayMs = typeof batch.recommended_poll_interval_ms === "number" && batch.recommended_poll_interval_ms > 0
            ? batch.recommended_poll_interval_ms
            : defaultBatchPollIntervalMs;

        batchStatusPollTimer = window.setTimeout(function() {
            if (!currentBatchId) {
                return;
            }

            loadBatchStatus(currentBatchId, true);
        }, pollDelayMs);
    }

    function applyBatchStatusResponse(response) {
        var batch = response && response.batch ? response.batch : null;
        var progress = batch && batch.progress ? batch.progress : null;
        var submission = batch && batch.submission ? batch.submission : null;
        var reportStatuses = batch && Array.isArray(batch.report_statuses) ? batch.report_statuses : [];
        var events = batch && Array.isArray(batch.events) ? batch.events : [];
        var lifecycleLabel;
        var timeRangeLabel;
        var reportCount;
        var summaryNote;
        var shellMessage;
        var executionReadiness;
        var phaseCapabilities;
        var transitionPolicy;
        var actionIntents;
        var executionPlan;
        var executionRequestPreview;

        if (!batch || !progress || !submission) {
            clearBatchStatusPoll();
            setProgressState(
                0,
                "Tracked status unavailable",
                "The backend returned an invalid batch status response.",
                "Current state: Status unavailable"
            );
            setSummaryState(
                currentBatchId || "Unknown batch",
                "Status unavailable",
                "Unknown",
                "Unavailable",
                "The backend returned an invalid tracked batch status response."
            );
            setExecutionReadinessState(
                "Unavailable",
                "Unavailable",
                "Unavailable",
                "Unknown",
                "Execution-readiness metadata is unavailable because the tracked batch response was invalid."
            );
            setPhaseCapabilitiesState(
                "Unavailable",
                "Unknown",
                "Unavailable",
                [],
                "Phase-capability metadata is unavailable because the tracked batch response was invalid."
            );
            setTransitionPolicyState(
                "Unavailable",
                [],
                [],
                "Lifecycle-policy metadata is unavailable because the tracked batch response was invalid."
            );
            setActionIntentState(
                [],
                [],
                "Enabled action-intent metadata is unavailable because the tracked batch response was invalid.",
                "Disabled action-intent metadata is unavailable because the tracked batch response was invalid.",
                "Action-intent metadata is unavailable because the tracked batch response was invalid."
            );
            setExecutionPlanState(
                "Unavailable",
                "Unknown",
                [],
                [],
                "Execution-plan preview metadata is unavailable because the tracked batch response was invalid."
            );
            setExecutionRequestPreviewState(
                "Unavailable",
                "Unknown",
                "Unknown",
                currentBatchId || "Unknown batch",
                "Unavailable",
                [],
                [],
                "Execution-request preview metadata is unavailable because the tracked batch response was invalid."
            );
            setBatchDetailMode(true);
            renderReportStatuses([], "Per-report status list unavailable.");
            renderEventTimeline([], "Lifecycle timeline unavailable.");
            renderRecentBatches(recentBatches, defaultRecentBatchMessage);
            return;
        }

        lifecycleLabel = batch.lifecycle_label || batch.lifecycle_state || "Tracked";
        timeRangeLabel = submission.time_range && submission.time_range.label ? submission.time_range.label : "Unknown";
        reportCount = typeof submission.report_count === "number" ? submission.report_count : 0;
        executionReadiness = batch.execution_readiness || {};
        phaseCapabilities = batch.phase_capabilities || {};
        transitionPolicy = batch.transition_policy || {};
        actionIntents = batch.action_intents || {};
        executionPlan = batch.execution_plan || {};
        executionRequestPreview = batch.execution_request_preview || {};
        summaryNote = (batch.state_message || response.message || "Tracked batch status loaded.")
            + " Time range: " + timeRangeLabel
            + ". Acknowledged: " + (submission.acknowledged ? "Yes" : "No") + ".";
        if (!batch.terminal) {
            summaryNote += " Refreshing automatically.";
        }
        summaryNote += " " + getRecentBatchRetentionHint();

        setProgressState(
            progress.percent || 0,
            progress.summary || "Tracked batch status loaded.",
            response.message || "Tracked batch status loaded successfully.",
            "Current state: " + lifecycleLabel
        );
        setSummaryState(
            batch.batch_id || "Unknown batch",
            lifecycleLabel,
            formatReportCount(reportCount),
            batch.updated_at || batch.created_at || "Unknown",
            summaryNote
        );
        setExecutionReadinessState(
            formatModeLabel(executionReadiness.tracking_mode, "tracked_batch"),
            formatModeLabel(executionReadiness.storage_mode, "process_memory"),
            formatModeLabel(executionReadiness.execution_mode, "stub_non_destructive"),
            executionReadiness.execution_enabled === true ? "Yes" : "No",
            executionReadiness.message || defaultExecutionReadinessNote
        );
        setPhaseCapabilitiesState(
            formatModeLabel(phaseCapabilities.execution_phase, "tracked_only"),
            phaseCapabilities.tracked_only === true ? "Yes" : (phaseCapabilities.tracked_only === false ? "No" : "Unknown"),
            formatModeLabel(phaseCapabilities.next_allowed_transition, "status_refresh"),
            phaseCapabilities.capabilities,
            phaseCapabilities.message || defaultPhaseCapabilityNote
        );
        setTransitionPolicyState(
            formatModeLabel(transitionPolicy.next_backend_phase, "tracked_status_progression"),
            transitionPolicy.allowed_actions,
            transitionPolicy.disallowed_actions,
            transitionPolicy.policy_message || defaultTransitionPolicyNote
        );
        setActionIntentState(
            actionIntents.enabled_actions,
            actionIntents.disabled_actions,
            actionIntents.action_reasoning && actionIntents.action_reasoning.enabled
                ? actionIntents.action_reasoning.enabled
                : "Enabled action intents are unavailable.",
            actionIntents.action_reasoning && actionIntents.action_reasoning.disabled
                ? actionIntents.action_reasoning.disabled
                : "Disabled action intents are unavailable.",
            actionIntents.message || defaultActionIntentNote
        );
        setExecutionPlanState(
            formatModeLabel(executionPlan.plan_state, "preview_only"),
            executionPlan.preview_only === true ? "Yes" : (executionPlan.preview_only === false ? "No" : "Unknown"),
            executionPlan.planned_reports,
            executionPlan.planned_steps,
            executionPlan.message || defaultExecutionPlanNote
        );
        setExecutionRequestPreviewState(
            formatModeLabel(executionRequestPreview.request_shape, "future_execution_submission"),
            executionRequestPreview.preview_only === true ? "Yes" : (executionRequestPreview.preview_only === false ? "No" : "Unknown"),
            executionRequestPreview.acknowledged === true ? "Yes" : (executionRequestPreview.acknowledged === false ? "No" : "Unknown"),
            executionRequestPreview.batch_id || batch.batch_id || "Unknown batch",
            formatExecutionRequestTimeRange(executionRequestPreview.time_range),
            executionRequestPreview.report_ids,
            $.map(executionRequestPreview.execution_phases || [], function(phase) {
                return formatModeLabel(phase, phase || "unknown_phase");
            }),
            executionRequestPreview.message || defaultExecutionRequestPreviewNote
        );
        upsertRecentBatchSummary(batch);
        setBatchDetailMode(true);
        renderRecentBatches(recentBatches, defaultRecentBatchMessage);
        renderReportStatuses(reportStatuses, "No report status entries recorded yet.");
        renderEventTimeline(events, "No lifecycle events recorded yet.");

        if (batch.terminal) {
            shellMessage = "Tracked backend batch " + (batch.batch_id || currentBatchId) + " reached stub completion. Execution remains non-destructive.";
        } else {
            shellMessage = "Tracking backend batch " + (batch.batch_id || currentBatchId) + ". Current state: " + lifecycleLabel + ".";
        }

        setShellStatus(shellMessage);
        scheduleBatchStatusPoll(batch);
    }

    function renderBatchStatusFailure(batchId, message) {
        clearBatchStatusPoll();
        setProgressState(
            0,
            "Tracked status unavailable",
            message,
            "Current state: Status unavailable"
        );
        setSummaryState(
            batchId || "Unknown batch",
            "Status unavailable",
            "Unknown",
            "Unavailable",
            message
        );
        setExecutionReadinessState(
            "Unavailable",
            "Unavailable",
            "Unavailable",
            "Unknown",
            "Execution-readiness metadata could not be loaded for this tracked batch."
        );
        setPhaseCapabilitiesState(
            "Unavailable",
            "Unknown",
            "Unavailable",
            [],
            "Phase-capability metadata could not be loaded for this tracked batch."
        );
        setTransitionPolicyState(
            "Unavailable",
            [],
            [],
            "Lifecycle-policy metadata could not be loaded for this tracked batch."
        );
        setActionIntentState(
            [],
            [],
            "Enabled action-intent metadata could not be loaded for this tracked batch.",
            "Disabled action-intent metadata could not be loaded for this tracked batch.",
            "Action-intent metadata could not be loaded for this tracked batch."
        );
        setExecutionPlanState(
            "Unavailable",
            "Unknown",
            [],
            [],
            "Execution-plan preview metadata could not be loaded for this tracked batch."
        );
        setExecutionRequestPreviewState(
            "Unavailable",
            "Unknown",
            "Unknown",
            batchId || "Unknown batch",
            "Unavailable",
            [],
            [],
            "Execution-request preview metadata could not be loaded for this tracked batch."
        );
        setBatchDetailMode(true);
        renderReportStatuses([], message);
        renderEventTimeline([], message);
        renderRecentBatches(recentBatches, defaultRecentBatchMessage);
        setShellStatus("Tracked batch status could not be loaded.");
    }

    function updateReportStates() {
        getReportRows().each(function() {
            var $row = $(this);
            var $state = $row.find(".sutw-report-row__state");
            var isSelected = $row.hasClass("is-selected");

            $row.attr("aria-pressed", isSelected ? "true" : "false");

            if (isSelected) {
                $state.text("Selected");
                return;
            }

            $state.text("Click to select");
        });
    }

    function updateDraftSelection(preserveSubmissionFeedback) {
        var selectedReports = getSelectedReportRows().map(function() {
            return $(this).data("reportLabel");
        }).get();
        var selectedCount = selectedReports.length;
        var activeRange = getActiveTimeRange();
        var isAcknowledged = $reviewAcknowledgement.is(":checked");
        var isStartEnabled = selectedCount > 0 && isAcknowledged;
        var readinessText = "Select at least one report";
        var reportSummary = "No reports selected.";
        var actionNote = defaultActionNote;

        if (selectedCount > 0) {
            reportSummary = "Selected reports: " + selectedReports.join(", ") + ". Mock time range: " + activeRange.label + ".";
            readinessText = "Acknowledge review to enable tracked submission";
            actionNote = "Review the current selection and acknowledge it to enable the non-destructive tracked submission.";
        }

        if (isStartEnabled) {
            readinessText = "Ready for tracked submission";
            actionNote = "Submission is enabled. The backend will validate the payload, create a tracked batch ID, and keep execution disabled.";
        }

        $("#sutw-selected-count").text(selectedCount);
        $("#sutw-confirmation-count").text(selectedCount);
        $("#sutw-range-label").text(activeRange.label);
        $("#sutw-range-earliest").text(activeRange.earliest);
        $("#sutw-range-latest").text(activeRange.latest);
        $("#sutw-confirmation-range").text(activeRange.label);
        $("#sutw-confirmation-status")
            .toggleClass("is-ready", isStartEnabled)
            .text(readinessText);
        $("#sutw-confirmation-reports").text(reportSummary);

        if (!isSubmitting) {
            if (preserveSubmissionFeedback && submissionActionNote) {
                $("#sutw-action-note").text(submissionActionNote);
            } else {
                $("#sutw-action-note").text(actionNote);
            }
        }

        $startButton.prop("disabled", !isStartEnabled || isSubmitting);
        updateReportStates();
    }

    function loadSubmissionPreview() {
        if (currentBatchId) {
            return;
        }

        if (!hasLoadedPreview) {
            setProgressState(
                0,
                "Loading submission preview...",
                "Fetching a safe read-only preview from the backend.",
                defaultProgressStateText
            );
        }

        $.ajax({
            url: buildStartBatchPreviewUrl(),
            method: "POST",
            contentType: "application/json",
            dataType: "json",
            processData: false,
            data: JSON.stringify(buildSubmissionPayload())
        }).done(function(response) {
            applyPreviewResponse(response);
        }).fail(function(jqXHR) {
            if (currentBatchId) {
                return;
            }

            setProgressState(
                0,
                "Preview unavailable",
                extractErrorMessage(jqXHR, "Submission preview could not be loaded."),
                defaultProgressStateText
            );
        });
    }

    function loadBatchStatus(batchId, isBackgroundPoll) {
        if (!batchId) {
            return;
        }

        if (!isBackgroundPoll) {
            setBatchDetailMode(true);
            setProgressState(
                0,
                "Loading tracked batch status...",
                "Fetching tracked backend status for batch " + batchId + ".",
                "Current state: Loading"
            );
            setSummaryState(batchId, "Loading status...", "Loading...", "Loading...", "Fetching the tracked batch record from the backend.");
            renderReportStatuses([], "Loading tracked report statuses...");
            renderEventTimeline([], "Loading tracked batch lifecycle...");
        }

        $.ajax({
            url: buildBatchStatusUrl(batchId),
            method: "GET",
            dataType: "json"
        }).done(function(response) {
            if (currentBatchId !== batchId) {
                return;
            }

            applyBatchStatusResponse(response);
        }).fail(function(jqXHR) {
            if (currentBatchId !== batchId) {
                return;
            }

            renderBatchStatusFailure(batchId, extractErrorMessage(jqXHR, "Tracked batch status could not be loaded."));
        });
    }

    function loadRecentBatches(options) {
        var requestOptions = options || {};
        var preserveExistingList = !!requestOptions.preserveExistingList;
        var loadingLabel = requestOptions.manual ? "Refreshing recent tracked batches..." : "Loading recent tracked batches...";

        if (isRefreshingRecentBatches) {
            return;
        }

        isRefreshingRecentBatches = true;
        $recentBatchRefreshButton.prop("disabled", true);
        setRecentBatchNote(loadingLabel + " " + getRecentBatchRetentionHint());

        if (!preserveExistingList || recentBatches.length === 0) {
            $recentBatchList.html("<li>Loading recent tracked batches...</li>");
        }

        $.ajax({
            url: buildRecentBatchesUrl(),
            method: "GET",
            dataType: "json"
        }).done(function(response) {
            if (!response || !Array.isArray(response.batches)) {
                if (preserveExistingList && recentBatches.length > 0) {
                    renderRecentBatches(recentBatches, defaultRecentBatchMessage);
                } else {
                    renderRecentBatches([], "Recent tracked batches returned an invalid response.");
                }
                setRecentBatchNote("Recent tracked batches returned an invalid response. " + getRecentBatchRetentionHint());
                return;
            }

            recentBatches = response.batches.slice(0);
            sortRecentBatches();
            renderRecentBatches(recentBatches, defaultRecentBatchMessage);
            setRecentBatchNote("Recent tracked batches refreshed at " + formatLocalTime(new Date()) + ". " + getRecentBatchRetentionHint());
        }).fail(function(jqXHR) {
            if (preserveExistingList && recentBatches.length > 0) {
                renderRecentBatches(recentBatches, defaultRecentBatchMessage);
            } else {
                renderRecentBatches([], extractErrorMessage(jqXHR, "Recent tracked batches could not be loaded."));
            }
            setRecentBatchNote(extractErrorMessage(jqXHR, "Recent tracked batches could not be loaded.") + " " + getRecentBatchRetentionHint());
        }).always(function() {
            isRefreshingRecentBatches = false;
            $recentBatchRefreshButton.prop("disabled", false);
        });
    }

    function loadEligibleReports() {
        $reportList.empty();
        $reportFeedback.text(defaultReportLoadMessage);
        setShellStatus("Loading eligible reports from the backend...");

        $.ajax({
            url: buildEligibleReportsUrl(),
            method: "GET",
            dataType: "json"
        }).done(function(response) {
            if (!response || !Array.isArray(response.reports)) {
                renderReportLoadFailure("Eligible reports returned an invalid response.");
                loadSubmissionPreview();
                return;
            }

            renderEligibleReports(response.reports);
            setShellStatus("Splunk Utility Tool Web loaded successfully. Eligible reports are now coming from the backend.");
            loadSubmissionPreview();
        }).fail(function(jqXHR) {
            renderReportLoadFailure(extractErrorMessage(jqXHR, "Eligible reports could not be loaded."));
            loadSubmissionPreview();
        });
    }

    function submitStartBatch() {
        isSubmitting = true;
        $startButton.prop("disabled", true);
        clearBatchStatusPoll();
        $("#sutw-action-note").text("Submitting the validated start-batch request...");
        setShellStatus("Submitting start-batch request to the backend...");

        $.ajax({
            url: buildStartBatchUrl(),
            method: "POST",
            contentType: "application/json",
            dataType: "json",
            processData: false,
            data: JSON.stringify(buildSubmissionPayload())
        }).done(function(response) {
            var message = response && response.message ? response.message : "Start-batch request accepted.";

            if (!response || !response.batch_id) {
                submissionActionNote = "The backend accepted the request but did not return a batch ID.";
                $("#sutw-action-note").text(submissionActionNote);
                setShellStatus("Start-batch request returned an invalid response.");
                loadSubmissionPreview();
                return;
            }

            currentBatchId = response.batch_id;
            submissionActionNote = message + " Batch ID: " + currentBatchId + ".";
            $("#sutw-action-note").text(submissionActionNote);
            setShellStatus("Start-batch request accepted. Loading tracked status for batch " + currentBatchId + ".");
            renderRecentBatches(recentBatches, defaultRecentBatchMessage);
            loadRecentBatches({ preserveExistingList: true });
            loadBatchStatus(currentBatchId, false);
        }).fail(function(jqXHR) {
            submissionActionNote = extractErrorMessage(jqXHR, "The start-batch submission failed.");
            $("#sutw-action-note").text(submissionActionNote);
            setShellStatus("Start-batch submission failed validation or could not be processed.");
            loadSubmissionPreview();
        }).always(function() {
            isSubmitting = false;
            updateDraftSelection(true);
        });
    }

    $reportList.on("click", ".sutw-report-row", function() {
        submissionActionNote = "";
        clearTrackedBatch();
        $(this).toggleClass("is-selected");
        updateDraftSelection();
        loadSubmissionPreview();
    });

    $rangeOptions.on("click", function() {
        submissionActionNote = "";
        clearTrackedBatch();
        $rangeOptions.removeClass("is-active");
        $(this).addClass("is-active");
        updateDraftSelection();
        loadSubmissionPreview();
    });

    $reviewAcknowledgement.on("change", function() {
        submissionActionNote = "";
        clearTrackedBatch();
        updateDraftSelection();
        loadSubmissionPreview();
    });

    $recentBatchList.on("click", ".sutw-recent-batch-select", function() {
        var batchId = $(this).data("batchId");

        if (!batchId) {
            return;
        }

        clearBatchStatusPoll();
        currentBatchId = batchId;
        renderRecentBatches(recentBatches, defaultRecentBatchMessage);
        setShellStatus("Loading tracked status for recent batch " + batchId + ".");
        loadBatchStatus(batchId, false);
    });

    $recentBatchRefreshButton.on("click", function() {
        loadRecentBatches({
            manual: true,
            preserveExistingList: true
        });
    });

    $startButton.on("click", function() {
        if ($startButton.prop("disabled")) {
            return;
        }

        submitStartBatch();
    });

    $shell.addClass("is-ready");
    resetSummaryState();
    setRecentBatchNote(defaultRecentBatchNote);
    renderRecentBatches(recentBatches, "Loading recent tracked batches...");
    setProgressState(
        0,
        "Loading submission preview...",
        "Fetching a safe read-only preview from the backend.",
        defaultProgressStateText
    );
    updateDraftSelection();
    loadRecentBatches();
    loadEligibleReports();
});
