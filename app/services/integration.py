from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations.catalog import PROVIDER_CATALOG, get_provider_definition
from app.models import IntegrationSource, Workspace
from app.repositories import IntegrationSourceRepository, WorkspaceRepository
from app.schemas.integration import IntegrationSourceCreate, IntegrationSourceUpdate
from app.security.integration_keys import (
    hash_integration_intake_key,
    integration_intake_key_prefix,
    new_integration_intake_key,
    verify_integration_intake_key,
)
from app.services.audit import AuditService


class IntegrationSourceNotFoundError(ValueError):
    pass


class IntegrationProviderError(ValueError):
    pass


class IntegrationSourceConflictError(ValueError):
    pass


class IntegrationSourceInactiveError(ValueError):
    pass


class IntegrationWorkspaceNotFoundError(ValueError):
    pass


class ExternalIntakeCredentialError(ValueError):
    pass


class ExternalIntakeUnsupportedError(ValueError):
    pass


def integration_snapshot(item: IntegrationSource) -> dict[str, object]:
    return {
        "public_id": item.public_id,
        "provider": item.provider,
        "name": item.name,
        "source": item.source,
        "channel": item.channel,
        "default_campaign": item.default_campaign,
        "routing_config": dict(item.routing_config or {}),
        "provider_config": dict(item.provider_config or {}),
        "active": item.active,
        "external_intake_enabled": item.external_intake_enabled,
        "intake_key_prefix": item.intake_key_prefix,
        "intake_count": item.intake_count,
    }


class IntegrationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)
        self.sources = IntegrationSourceRepository(db)
        self.audit = AuditService(db)

    def _workspace(self, public_id: str) -> Workspace:
        workspace = self.workspaces.get_by_public_id(public_id)
        if workspace is None:
            raise IntegrationWorkspaceNotFoundError(
                f"Empresa não encontrada: {public_id}"
            )
        return workspace

    def catalog(self):
        return PROVIDER_CATALOG

    def list_sources(self, workspace_public_id: str) -> list[IntegrationSource]:
        workspace = self._workspace(workspace_public_id)
        return self.sources.list_for_workspace(workspace.id)

    def get_source(
        self,
        workspace_public_id: str,
        integration_public_id: str,
    ) -> IntegrationSource:
        workspace = self._workspace(workspace_public_id)
        item = self.sources.get_by_public_id(
            workspace_id=workspace.id,
            public_id=integration_public_id,
        )
        if item is None:
            raise IntegrationSourceNotFoundError(
                f"Fonte de integração não encontrada: {integration_public_id}"
            )
        return item

    def require_active_source(
        self,
        workspace_public_id: str,
        integration_public_id: str,
    ) -> IntegrationSource:
        item = self.get_source(workspace_public_id, integration_public_id)
        if not item.active:
            raise IntegrationSourceInactiveError(
                "Esta fonte de integração está desativada."
            )
        return item

    def create_source(
        self,
        workspace_public_id: str,
        payload: IntegrationSourceCreate,
    ) -> IntegrationSource:
        workspace = self._workspace(workspace_public_id)
        provider = get_provider_definition(payload.provider)
        if provider is None:
            raise IntegrationProviderError(
                f"Provedor de integração inválido: {payload.provider}"
            )

        existing = self.sources.get_by_name(
            workspace_id=workspace.id,
            name=payload.name,
        )
        if existing is not None:
            raise IntegrationSourceConflictError(
                f"Já existe uma fonte chamada '{payload.name}' nesta empresa."
            )

        item = self.sources.create(
            workspace_id=workspace.id,
            provider=provider.code,
            name=payload.name,
            source=payload.source,
            channel=payload.channel,
            default_campaign=payload.default_campaign,
            routing_config=dict(payload.routing_config),
            provider_config=dict(payload.provider_config),
            active=payload.active,
        )
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="integration_source.created",
            after_data=integration_snapshot(item),
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise IntegrationSourceConflictError(
                "Não foi possível criar a fonte por conflito de dados."
            ) from exc
        self.db.refresh(item)
        return item

    def update_source(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        payload: IntegrationSourceUpdate,
    ) -> IntegrationSource:
        workspace = self._workspace(workspace_public_id)
        item = self.get_source(workspace_public_id, integration_public_id)
        before = integration_snapshot(item)
        changes = payload.model_dump(exclude_unset=True)

        new_name = changes.get("name")
        if isinstance(new_name, str) and new_name != item.name:
            existing = self.sources.get_by_name(
                workspace_id=workspace.id,
                name=new_name,
            )
            if existing is not None and existing.public_id != item.public_id:
                raise IntegrationSourceConflictError(
                    f"Já existe uma fonte chamada '{new_name}' nesta empresa."
                )

        for field_name, value in changes.items():
            if field_name in {"routing_config", "provider_config"} and value is not None:
                value = dict(value)
            setattr(item, field_name, value)

        self.sources.save(item)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="integration_source.updated",
            before_data=before,
            after_data=integration_snapshot(item),
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise IntegrationSourceConflictError(
                "Não foi possível atualizar a fonte por conflito de dados."
            ) from exc
        self.db.refresh(item)
        return item

    def set_active(
        self,
        workspace_public_id: str,
        integration_public_id: str,
        *,
        active: bool,
    ) -> IntegrationSource:
        workspace = self._workspace(workspace_public_id)
        item = self.get_source(workspace_public_id, integration_public_id)
        before = integration_snapshot(item)
        item.active = active
        self.sources.save(item)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action=(
                "integration_source.activated"
                if active
                else "integration_source.deactivated"
            ),
            before_data=before,
            after_data=integration_snapshot(item),
        )
        self.db.commit()
        self.db.refresh(item)
        return item

    def rotate_external_intake_key(
        self,
        workspace_public_id: str,
        integration_public_id: str,
    ) -> tuple[IntegrationSource, str]:
        workspace = self._workspace(workspace_public_id)
        item = self.get_source(workspace_public_id, integration_public_id)
        provider = get_provider_definition(item.provider)
        if provider is None or "external_intake" not in provider.capabilities:
            raise ExternalIntakeUnsupportedError(
                "Este tipo de integração não aceita intake externo nesta etapa."
            )

        before = integration_snapshot(item)
        raw_key = new_integration_intake_key()
        item.intake_key_hash = hash_integration_intake_key(raw_key)
        item.intake_key_prefix = integration_intake_key_prefix(raw_key)
        self.sources.save(item)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="integration_source.intake_key_rotated",
            before_data=before,
            after_data=integration_snapshot(item),
            metadata={"key_prefix": item.intake_key_prefix},
        )
        self.db.commit()
        self.db.refresh(item)
        return item, raw_key

    def revoke_external_intake_key(
        self,
        workspace_public_id: str,
        integration_public_id: str,
    ) -> IntegrationSource:
        workspace = self._workspace(workspace_public_id)
        item = self.get_source(workspace_public_id, integration_public_id)
        before = integration_snapshot(item)
        item.intake_key_hash = None
        item.intake_key_prefix = None
        self.sources.save(item)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="integration_source.intake_key_revoked",
            before_data=before,
            after_data=integration_snapshot(item),
        )
        self.db.commit()
        self.db.refresh(item)
        return item

    def authenticate_external_source(
        self,
        integration_public_id: str,
        raw_key: str | None,
    ) -> tuple[IntegrationSource, Workspace]:
        item = self.sources.get_global_by_public_id(integration_public_id)
        if (
            item is None
            or not raw_key
            or not item.intake_key_hash
            or not verify_integration_intake_key(raw_key, item.intake_key_hash)
        ):
            raise ExternalIntakeCredentialError(
                "Credencial de integração inválida."
            )
        if not item.active:
            raise IntegrationSourceInactiveError(
                "Esta fonte de integração está desativada."
            )
        workspace = self.workspaces.get_by_id(item.workspace_id)
        if workspace is None:
            raise ExternalIntakeCredentialError(
                "Credencial de integração inválida."
            )
        return item, workspace

    def record_external_intake(
        self,
        item: IntegrationSource,
        *,
        lead_public_id: str,
        action: str,
        request_id: str | None,
        idempotency_key: str | None,
        remote_ip: str | None,
    ) -> IntegrationSource:
        item.intake_count += 1
        item.last_intake_at = datetime.now(timezone.utc)
        self.sources.save(item)
        self.audit.record(
            workspace_id=item.workspace_id,
            entity_type="integration_source",
            entity_public_id=item.public_id,
            action="integration_source.external_intake_received",
            actor_type="integration",
            after_data={
                "lead_public_id": lead_public_id,
                "lead_action": action,
                "intake_count": item.intake_count,
            },
            metadata={
                "request_id": request_id,
                "idempotency_key": idempotency_key,
                "remote_ip": remote_ip,
            },
        )
        self.db.commit()
        self.db.refresh(item)
        return item
