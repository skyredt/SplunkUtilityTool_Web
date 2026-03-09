"""Configuration helpers for safe, disabled execution-boundary metadata."""

from __future__ import annotations

from typing import Any

_EXECUTION_BOUNDARY_SETTINGS = {
    "boundary_mode": "controlled_clone_preparation",
    "preview_only": False,
    "execution_enabled": False,
    "current_phase": "clone_preparation_enabled",
    "next_phase": "dispatch_enablement_review",
    "enablement_state": "enabled",
    "enabled_boundary": {
        "key": "clone_preparation",
        "label": "Clone Preparation",
    },
    "enablement_milestone": {
        "key": "dispatch_enablement_review",
        "label": "Dispatch Enablement Review",
        "summary": (
            "A future backend-controlled review must approve the dispatch handoff boundary "
            "before the batch can move beyond safe clone preparation."
        ),
    },
    "message": (
        "Clone preparation is the only enabled real execution boundary in this phase. "
        "Dispatch handoff, verification handoff, cleanup handoff, and locks remain disabled."
    ),
}


def get_execution_boundary_settings() -> dict[str, Any]:
    """Return safe internal execution-boundary settings for the current phase."""
    milestone = _EXECUTION_BOUNDARY_SETTINGS["enablement_milestone"]

    return {
        "boundary_mode": _EXECUTION_BOUNDARY_SETTINGS["boundary_mode"],
        "preview_only": _EXECUTION_BOUNDARY_SETTINGS["preview_only"],
        "execution_enabled": _EXECUTION_BOUNDARY_SETTINGS["execution_enabled"],
        "current_phase": _EXECUTION_BOUNDARY_SETTINGS["current_phase"],
        "next_phase": _EXECUTION_BOUNDARY_SETTINGS["next_phase"],
        "enablement_state": _EXECUTION_BOUNDARY_SETTINGS["enablement_state"],
        "enabled_boundary": {
            "key": _EXECUTION_BOUNDARY_SETTINGS["enabled_boundary"]["key"],
            "label": _EXECUTION_BOUNDARY_SETTINGS["enabled_boundary"]["label"],
        },
        "enablement_milestone": {
            "key": milestone["key"],
            "label": milestone["label"],
            "summary": milestone["summary"],
        },
        "message": _EXECUTION_BOUNDARY_SETTINGS["message"],
    }
