# Sprint 1 / Etapa 4 — Segmentos configuráveis

## Objetivo

Permitir que o mesmo Nexyra CRM atenda vários tipos de negócio sem criar
um sistema separado para cada segmento.

## Catálogo inicial

### Educação

Interesse principal: curso.

Campos iniciais:

- curso
- turno
- modalidade
- unidade
- bolsa

Pipeline padrão:

- novo
- contatado
- interessado
- proposta
- matricula
- perdido

### Imobiliária

Interesse principal: imóvel.

Inclui visita, proposta e contrato no pipeline.

### Automóveis

Interesse principal: veículo.

Inclui test drive, financiamento e venda.

### Varejo

Interesse principal: produto.

Inclui orçamento, pedido, venda e pós-venda.

### Atacado

Interesse principal: produto.

Inclui cotação, negociação, pedido e recorrência.

### Serviços

Interesse principal: serviço.

Inclui diagnóstico, proposta, contrato e entrega.

### Personalizado

Permite configurar pipeline e campos para negócios que não se encaixem
nos modelos existentes.

## Persistência

A configuração de cada empresa fica na tabela:

`workspace_segment_configs`

Existe uma configuração por workspace.

## Arquitetura

A camada de segmento pertence ao Nexyra CRM.

O Atlas não precisa conhecer internamente cada tabela ou regra do CRM.
Na integração futura, ele receberá o contrato do workspace, incluindo:

- segmento
- pipeline
- campos
- permissões
- contexto comercial

Assim o mesmo Atlas poderá operar em vários negócios.

## Próxima etapa

Sprint 1 / Etapa 5:

Usuários, vendedores e permissões multiempresa.
