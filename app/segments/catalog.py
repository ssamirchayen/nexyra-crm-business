from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentDefinition:
    code: str
    label: str
    interest_label: str
    pipeline: tuple[str, ...]
    custom_fields: tuple[str, ...]


_SEGMENTS: tuple[SegmentDefinition, ...] = (
    SegmentDefinition(
        code="generic",
        label="Negócio genérico",
        interest_label="Interesse",
        pipeline=(
            "novo",
            "qualificado",
            "negociacao",
            "ganho",
            "perdido",
        ),
        custom_fields=(),
    ),
    SegmentDefinition(
        code="education",
        label="Educação",
        interest_label="Curso",
        pipeline=(
            "novo",
            "contatado",
            "interessado",
            "proposta",
            "matricula",
            "perdido",
        ),
        custom_fields=(
            "curso",
            "turno",
            "modalidade",
            "unidade",
            "bolsa",
        ),
    ),
    SegmentDefinition(
        code="real_estate",
        label="Imobiliária",
        interest_label="Imóvel",
        pipeline=(
            "novo",
            "qualificado",
            "visita",
            "proposta",
            "contrato",
            "perdido",
        ),
        custom_fields=(
            "tipo_imovel",
            "bairro",
            "faixa_preco",
            "quartos",
        ),
    ),
    SegmentDefinition(
        code="automotive",
        label="Automóveis",
        interest_label="Veículo",
        pipeline=(
            "novo",
            "qualificado",
            "test_drive",
            "proposta",
            "financiamento",
            "venda",
            "perdido",
        ),
        custom_fields=(
            "veiculo",
            "modelo",
            "ano",
            "financiamento",
        ),
    ),
    SegmentDefinition(
        code="retail",
        label="Varejo",
        interest_label="Produto",
        pipeline=(
            "novo",
            "atendimento",
            "orcamento",
            "pedido",
            "venda",
            "pos_venda",
        ),
        custom_fields=(
            "produto",
            "categoria",
            "quantidade",
        ),
    ),
    SegmentDefinition(
        code="wholesale",
        label="Atacado",
        interest_label="Produto",
        pipeline=(
            "novo",
            "qualificado",
            "cotacao",
            "negociacao",
            "pedido",
            "recorrencia",
        ),
        custom_fields=(
            "produto",
            "categoria",
            "quantidade",
            "volume_compra",
        ),
    ),
    SegmentDefinition(
        code="services",
        label="Serviços",
        interest_label="Serviço",
        pipeline=(
            "novo",
            "qualificado",
            "diagnostico",
            "proposta",
            "contrato",
            "entrega",
        ),
        custom_fields=(
            "servico",
            "necessidade",
            "prazo",
        ),
    ),
    SegmentDefinition(
        code="custom",
        label="Personalizado",
        interest_label="Interesse",
        pipeline=(
            "novo",
            "qualificado",
            "negociacao",
            "ganho",
            "perdido",
        ),
        custom_fields=(),
    ),
)

_SEGMENT_MAP = {segment.code: segment for segment in _SEGMENTS}


def list_segment_definitions() -> tuple[SegmentDefinition, ...]:
    return _SEGMENTS


def get_segment_definition(code: str) -> SegmentDefinition | None:
    return _SEGMENT_MAP.get(code.strip().lower())
