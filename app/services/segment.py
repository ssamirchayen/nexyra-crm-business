from __future__ import annotations

from sqlalchemy.orm import Session

from app.audit import segment_config_snapshot
from app.models import WorkspaceSegmentConfig
from app.repositories import (
    WorkspaceRepository,
    WorkspaceSegmentConfigRepository,
)
from app.schemas import WorkspaceSegmentConfigUpdate
from app.segments import (
    SegmentDefinition,
    get_segment_definition,
    list_segment_definitions,
)
from app.services.audit import AuditService
from app.services.workspace import WorkspaceNotFoundError


class SegmentNotFoundError(ValueError):
    pass


class WorkspaceSegmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspaces = WorkspaceRepository(db)
        self.configs = WorkspaceSegmentConfigRepository(db)
        self.audit = AuditService(db)

    def list_catalog(self) -> tuple[SegmentDefinition, ...]:
        return list_segment_definitions()

    def get_catalog_item(self, code: str) -> SegmentDefinition:
        definition = get_segment_definition(code)
        if definition is None:
            raise SegmentNotFoundError(
                f"Segmento não encontrado: {code}"
            )
        return definition

    def get_workspace_config(
        self,
        workspace_public_id: str,
    ) -> WorkspaceSegmentConfig:
        workspace = self.workspaces.get_by_public_id(
            workspace_public_id
        )
        if workspace is None:
            raise WorkspaceNotFoundError(
                f"Empresa não encontrada: {workspace_public_id}"
            )

        config = self.configs.get_by_workspace_id(workspace.id)
        if config is not None:
            return config

        definition = self.get_catalog_item(workspace.segment)

        config = WorkspaceSegmentConfig(
            workspace_id=workspace.id,
            segment_code=definition.code,
            interest_label=definition.interest_label,
            pipeline=list(definition.pipeline),
            custom_fields=list(definition.custom_fields),
        )

        self.configs.save(config)
        self.audit.record(
            workspace_id=workspace.id,
            entity_type="segment_config",
            entity_public_id=workspace.public_id,
            action="segment_config.initialized",
            after_data=segment_config_snapshot(config),
        )

        self.db.commit()
        self.db.refresh(config)
        return config

    def update_workspace_config(
        self,
        workspace_public_id: str,
        payload: WorkspaceSegmentConfigUpdate,
    ) -> WorkspaceSegmentConfig:
        workspace = self.workspaces.get_by_public_id(
            workspace_public_id
        )
        if workspace is None:
            raise WorkspaceNotFoundError(
                f"Empresa não encontrada: {workspace_public_id}"
            )

        definition = self.get_catalog_item(payload.segment_code)

        config = self.configs.get_by_workspace_id(workspace.id)
        before_data = (
            segment_config_snapshot(config)
            if config is not None
            else None
        )

        if config is None:
            config = WorkspaceSegmentConfig(
                workspace_id=workspace.id,
                segment_code=definition.code,
                interest_label=definition.interest_label,
                pipeline=list(definition.pipeline),
                custom_fields=list(definition.custom_fields),
            )

        config.segment_code = definition.code
        config.interest_label = (
            payload.interest_label
            if payload.interest_label is not None
            else definition.interest_label
        )
        config.pipeline = (
            list(payload.pipeline)
            if payload.pipeline is not None
            else list(definition.pipeline)
        )
        config.custom_fields = (
            list(payload.custom_fields)
            if payload.custom_fields is not None
            else list(definition.custom_fields)
        )

        workspace.segment = definition.code

        self.configs.save(config)
        self.workspaces.save(workspace)

        self.audit.record(
            workspace_id=workspace.id,
            entity_type="segment_config",
            entity_public_id=workspace.public_id,
            action="segment_config.updated",
            before_data=before_data,
            after_data=segment_config_snapshot(config),
        )

        self.db.commit()
        self.db.refresh(config)
        return config
