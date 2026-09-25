# Sprint 2 / Etapa 2 — Dashboard conectado à API

## Objetivo

Substituir os números fictícios da primeira tela por dados reais do banco do Nexyra CRM.

## Backend

Novo endpoint:

`GET /api/v1/workspaces/{workspace_public_id}/dashboard/summary`

O resumo retorna:

- leads dos últimos 30 dias
- comparação com o período anterior
- pipeline aberto
- oportunidades abertas
- taxa de conversão
- variação de conversão em pontos percentuais
- receita ganha no período
- ticket médio
- oportunidades ganhas/perdidas
- distribuição por origem
- leads recentes
- próximas atividades
- série de receita das últimas quatro semanas

Nenhuma migration nova é necessária.

## CORS

O backend agora permite, por padrão, o frontend local em:

- `http://127.0.0.1:5173`
- `http://localhost:5173`

A lista pode ser alterada por `CORS_ORIGINS` no `.env`.

## Frontend

- seleção real de workspace
- workspace persistido no navegador
- dashboard carregado pela API
- estados de loading, erro e ambiente vazio
- gráfico dinâmico de receita
- leads recentes reais
- atividades pendentes reais
- distribuição real das fontes dos leads
- atualização manual do painel

## Execução

Backend:

```powershell
cd C:\Nexyra_CRM
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend, em outro PowerShell:

```powershell
cd C:\Nexyra_CRM\frontend
npm run build
npm run dev
```

## Validação

```powershell
cd C:\Nexyra_CRM
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests alembic

cd C:\Nexyra_CRM\frontend
npm run build
```
