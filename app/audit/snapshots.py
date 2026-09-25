from __future__ import annotations

from app.models import (
    Activity,
    Lead,
    Opportunity,
    Workspace,
    WorkspaceMembership,
    WorkspaceSegmentConfig,
)


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def workspace_snapshot(workspace: Workspace) -> dict[str, object]:
    return {
        "public_id": workspace.public_id,
        "name": workspace.name,
        "slug": workspace.slug,
        "segment": workspace.segment,
        "active": workspace.active,
    }


def membership_snapshot(
    membership: WorkspaceMembership,
    *,
    user_public_id: str,
) -> dict[str, object]:
    return {
        "user_public_id": user_public_id,
        "role": membership.role,
        "active": membership.active,
    }


def segment_config_snapshot(
    config: WorkspaceSegmentConfig,
) -> dict[str, object]:
    return {
        "segment_code": config.segment_code,
        "interest_label": config.interest_label,
        "pipeline": list(config.pipeline),
        "custom_fields": list(config.custom_fields),
    }


def lead_snapshot(
    lead: Lead,
    *,
    owner_user_public_id: str | None,
) -> dict[str, object]:
    return {
        "public_id": lead.public_id,
        "name": lead.name,
        "phone": lead.phone,
        "email": lead.email,
        "external_id": lead.external_id,
        "interest": lead.interest,
        "source": lead.source,
        "channel": lead.channel,
        "campaign": lead.campaign,
        "message": lead.message,
        "status": lead.status,
        "priority": lead.priority,
        "custom_fields": dict(lead.custom_fields),
        "owner_user_public_id": owner_user_public_id,
        "consent": lead.consent,
        "active": lead.active,
    }


def opportunity_snapshot(
    opportunity: Opportunity,
    *,
    lead_public_id: str,
    owner_user_public_id: str | None,
) -> dict[str, object]:
    return {
        "public_id": opportunity.public_id,
        "lead_public_id": lead_public_id,
        "owner_user_public_id": owner_user_public_id,
        "title": opportunity.title,
        "value_amount": str(opportunity.value_amount),
        "currency": opportunity.currency,
        "stage": opportunity.stage,
        "status": opportunity.status,
        "expected_close_date": _iso(opportunity.expected_close_date),
        "loss_reason": opportunity.loss_reason,
        "won_at": _iso(opportunity.won_at),
        "lost_at": _iso(opportunity.lost_at),
    }


def activity_snapshot(
    activity: Activity,
    *,
    lead_public_id: str | None,
    opportunity_public_id: str | None,
    owner_user_public_id: str | None,
) -> dict[str, object]:
    return {
        "public_id": activity.public_id,
        "activity_type": activity.activity_type,
        "title": activity.title,
        "description": activity.description,
        "status": activity.status,
        "due_at": _iso(activity.due_at),
        "completed_at": _iso(activity.completed_at),
        "cancelled_at": _iso(activity.cancelled_at),
        "lead_public_id": lead_public_id,
        "opportunity_public_id": opportunity_public_id,
        "owner_user_public_id": owner_user_public_id,
    }
