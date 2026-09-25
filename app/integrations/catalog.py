from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrationProviderDefinition:
    code: str
    label: str
    description: str
    category: str
    availability: str
    default_source: str
    default_channel: str
    supports_multiple: bool
    capabilities: tuple[str, ...]


PROVIDER_CATALOG: tuple[IntegrationProviderDefinition, ...] = (
    IntegrationProviderDefinition(
        code="api_intake",
        label="API / Lead Intake",
        description=(
            "Entrada padronizada para leads enviados por sistemas, formulários "
            "e conectores autorizados."
        ),
        category="api",
        availability="available",
        default_source="api",
        default_channel="api",
        supports_multiple=True,
        capabilities=(
            "lead_intake",
            "external_intake",
            "deduplication",
            "routing_defaults",
        ),
    ),
    IntegrationProviderDefinition(
        code="website",
        label="Site e formulários",
        description=(
            "Base para formulários próprios, landing pages e captação vinda do site."
        ),
        category="web",
        availability="available",
        default_source="website",
        default_channel="form",
        supports_multiple=True,
        capabilities=("lead_intake", "external_intake", "routing_defaults"),
    ),
    IntegrationProviderDefinition(
        code="webhook",
        label="Webhook",
        description=(
            "Origem genérica para automações e sistemas que enviam dados ao CRM."
        ),
        category="api",
        availability="available",
        default_source="webhook",
        default_channel="webhook",
        supports_multiple=True,
        capabilities=("lead_intake", "external_intake", "routing_defaults"),
    ),
    IntegrationProviderDefinition(
        code="csv",
        label="Importação CSV",
        description="Fonte preparada para importações em lote e migrações de leads.",
        category="import",
        availability="available",
        default_source="csv",
        default_channel="import",
        supports_multiple=True,
        capabilities=(
            "csv_import",
            "batch_intake",
            "deduplication",
            "routing_defaults",
        ),
    ),
    IntegrationProviderDefinition(
        code="custom_api",
        label="API personalizada",
        description=(
            "Cadastro de origem para integrações próprias ou sistemas de terceiros."
        ),
        category="api",
        availability="available",
        default_source="api",
        default_channel="custom",
        supports_multiple=True,
        capabilities=("lead_intake", "external_intake", "routing_defaults"),
    ),
    IntegrationProviderDefinition(
        code="meta",
        label="Instagram / Meta Lead Ads",
        description=(
            "Conector para Lead Ads via webhook oficial e Meta Graph API. "
            "A autorização OAuth automática pode ser adicionada em etapa futura."
        ),
        category="social",
        availability="available",
        default_source="instagram",
        default_channel="lead_ads",
        supports_multiple=True,
        capabilities=(
            "routing_defaults",
            "meta_lead_ads",
            "meta_webhook",
            "meta_graph_api",
            "future_oauth",
        ),
    ),
    IntegrationProviderDefinition(
        code="whatsapp",
        label="WhatsApp Cloud API",
        description=(
            "Conector oficial para receber mensagens, atualizar leads, "
            "registrar interações e enviar textos com confirmação."
        ),
        category="messaging",
        availability="available",
        default_source="whatsapp",
        default_channel="inbound",
        supports_multiple=True,
        capabilities=(
            "routing_defaults",
            "whatsapp_cloud",
            "whatsapp_webhook",
            "whatsapp_messages",
            "controlled_send",
            "approved_templates",
            "template_preview_confirmation",
        ),
    ),
)

PROVIDER_BY_CODE = {item.code: item for item in PROVIDER_CATALOG}


def get_provider_definition(code: str) -> IntegrationProviderDefinition | None:
    return PROVIDER_BY_CODE.get(code.strip().lower())
