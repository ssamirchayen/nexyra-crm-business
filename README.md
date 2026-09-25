# Nexyra CRM

CRM comercial multiempresa e multissegmento da Nexyra.

## Versão

`1.0.0` — release técnica candidata após conclusão das Sprints 1–5.

## Principais módulos

- autenticação, usuários, equipes e permissões;
- leads, pipeline, oportunidades, atividades e auditoria;
- relatórios e dashboards;
- importação e entrada externa de leads;
- Meta Lead Ads;
- WhatsApp Cloud API e coexistência com WhatsApp Business App;
- inbox operacional e templates aprovados;
- distribuição inteligente de leads;
- SLA e fila inteligente;
- cadências e follow-ups;
- consentimento, opt-out e políticas de comunicação;
- triagem e operações em lote;
- mensagens em lote controladas;
- recomendações comerciais;
- dashboard operacional avançado;
- contrato de integração com Atlas.

## Backend

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

## Frontend

```powershell
cd frontend
npm run dev
```

## Validação da release

```powershell
.\tools\validate_release.ps1
```

Esse script executa Alembic, Ruff, pytest, smoke test e build do frontend.

## Configuração

Copie `.env.example` para `.env` e configure os valores necessários. Nunca versione `.env`, banco local ou segredos de integrações.

Mais detalhes em `README_RELEASE.md` e `docs/FINAL_RELEASE_CHECKLIST.md`.
