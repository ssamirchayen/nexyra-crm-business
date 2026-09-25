# Hotfix Nexyra CRM Desktop — Cadências

Corrige crash da tela de Cadências no app Desktop.

## Ajustes
- normaliza listas retornadas pela API antes de renderizar;
- tolera cadências antigas/incompletas sem `steps`;
- tolera `leadPage.items` ausente;
- protege datas inválidas;
- protege permissões ausentes;
- adiciona detalhes técnicos na ErrorBoundary para facilitar diagnóstico futuro.

## Validação
- TypeScript: `npx tsc -b` passou.
- Sem migration de banco.
