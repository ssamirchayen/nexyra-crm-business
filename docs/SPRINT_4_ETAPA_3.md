# Sprint 4 / Etapa 3 — CSV e ingestão em lote

## Objetivo

Permitir que uma empresa migre bases antigas ou listas comerciais para o Nexyra CRM
com segurança, prévia, mapeamento e deduplicação, sem transformar o core do CRM em
um importador específico de uma vertical.

## Regras de produto

- o CSV nunca define livremente a origem/canal quando uma fonte CSV do workspace é
  selecionada;
- deduplicação reutiliza as regras oficiais de Leads;
- importações são isoladas por workspace;
- o histórico persiste apenas metadados, contadores, mapeamento e amostras de erro;
- o conteúdo integral do CSV não é armazenado;
- uma linha inválida não impede o processamento das linhas válidas;
- o limite por execução é de 5.000 linhas e 3.000.000 de caracteres.

## Campos reconhecidos

`name`, `phone`, `email`, `external_id`, `interest`, `campaign`, `message`,
`status`, `priority` e `consent`.

O backend também reconhece aliases comuns, por exemplo `nome`, `telefone`,
`celular`, `e-mail`, `interesse`, `curso`, `produto`, `campanha`, `mensagem`,
`etapa` e `prioridade`.
