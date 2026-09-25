# Sprint 2 / Etapa 9 — Configurações profissionais

## Objetivo

Transformar a rota de Configurações em uma área administrativa real do Nexyra CRM, reutilizando as APIs estáveis do Core sem criar dependência do Atlas.

## Entregas

- edição de nome e slug do workspace
- identificação do workspace e status
- seleção de segmento
- edição do nome do interesse principal
- editor de pipeline com inclusão, remoção e reordenação
- editor de campos personalizados
- carregamento dos modelos de segmento existentes
- tema claro/escuro pela tela de configurações
- período padrão dos relatórios por workspace e dispositivo
- central visual de integrações preparada
- endpoint de Lead Intake visível para integrações externas
- Meta/Instagram, WhatsApp e Site/Webhook sinalizados como próxima fase, sem simular conexão existente

## Persistência

Configurações de empresa e operação comercial continuam persistidas no banco por meio dos endpoints já existentes. Preferências puramente visuais permanecem locais à instalação/dispositivo.

## Banco

Não há migration nova.

## Arquitetura

O Nexyra CRM continua um produto independente. Nenhuma dependência obrigatória do Atlas foi adicionada nesta etapa.
