"""Disabled internal execution-boundary descriptors for future verification work."""

from __future__ import annotations

from typing import Any

from sutw_config import get_execution_boundary_settings


def get_verification_boundary_descriptors() -> list[dict[str, Any]]:
    """Return disabled boundary descriptors for future verification and cleanup phases."""
    settings = get_execution_boundary_settings()

    return [
        {
            "phase_key": "verification_handoff",
            "phase_label": "Verification Handoff",
            "boundary_owner": "sutw_verification",
            "boundary_mode": settings["boundary_mode"],
            "preview_only": settings["preview_only"],
            "execution_enabled": settings["execution_enabled"],
            "state": "defined_disabled",
            "real_step_executed": False,
            "summary": (
                "Internal verification-handoff boundaries are defined for a later execution-backed phase, "
                "but they remain disabled in this phase."
            ),
        },
        {
            "phase_key": "cleanup_handoff",
            "phase_label": "Cleanup Handoff",
            "boundary_owner": "sutw_verification",
            "boundary_mode": settings["boundary_mode"],
            "preview_only": settings["preview_only"],
            "execution_enabled": settings["execution_enabled"],
            "state": "defined_disabled",
            "real_step_executed": False,
            "summary": (
                "Internal cleanup-handoff boundaries are defined so terminal execution work can move into "
                "a later cleanup phase after backend enablement."
            ),
        },
    ]
