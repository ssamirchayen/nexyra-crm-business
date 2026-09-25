from __future__ import annotations

ATLAS_CONTRACT_NAME = "nexyra-crm-atlas"

SUPPORTED_ATLAS_ACTIONS: tuple[str, ...] = (
    "lead.update",
    "opportunity.move",
    "activity.create",
    "activity.complete",
)

ATLAS_CAPABILITIES: tuple[str, ...] = (
    "workspace_context",
    "lead_source_tracking",
    "lead_intake",
    "action_preview",
    "action_execute_with_confirmation",
    "role_permission_gate",
    "audit_trail",
    "multi_workspace_isolation",
)
