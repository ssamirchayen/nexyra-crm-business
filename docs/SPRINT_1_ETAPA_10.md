# Sprint 1 / Etapa 10 — Atlas Integration Contract

## Objetivo

Formalizar a comunicação entre dois produtos separados:

`Atlas <-> API versionada <-> Nexyra CRM`

O Atlas continua sendo a camada de inteligência e automação. O CRM continua
funcionando independentemente dele.

## Princípios

1. Contrato versionado.
2. Nenhum import de código do Atlas dentro do CRM.
3. Ações de escrita exigem permissão.
4. Execução exige confirmação explícita.
5. Toda execução do Atlas deixa trilha de auditoria.
6. Workspace continua sendo a fronteira multiempresa.
7. Lead Hub usa o intake padrão do CRM.

## Contrato 1.0

### Leitura

- health
- capabilities
- contexto compacto do workspace
- métricas
- fontes de leads
- pendências comerciais

### Escrita

- intake de leads
- atualização de lead
- movimentação de oportunidade
- criação de atividade
- conclusão de atividade

## Preview -> confirmação -> execução

O fluxo recomendado para ações do Atlas é:

`Atlas sugere -> preview -> usuário confirma -> execute -> auditoria`

Isso evita que a IA altere o CRM silenciosamente.

## Segurança atual

Nesta fase há duas barreiras de contrato:

- token compartilhado da integração
- autorização RBAC do membership

Essa solução é adequada para a fundação e testes do contrato. Antes de exposição
pública/produção, deve ser complementada pela futura autenticação forte do CRM,
rotação de segredos, TLS e identidade de serviço.

## Sprint 1 concluída

A conclusão desta etapa encerra a primeira sprint do produto com:

- API
- banco/migrations
- multiempresa
- multissegmento
- usuários e RBAC
- leads
- oportunidades/pipeline
- atividades/follow-ups
- auditoria
- contrato oficial com Atlas

Próxima fase: frontend profissional do Nexyra CRM.
