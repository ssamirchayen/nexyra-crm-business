# Nexyra CRM 1.0.0 — Release técnica

Esta pasta consolida o Nexyra CRM após as Sprints 1–5, incluindo os hotfixes validados durante o desenvolvimento.

## Estado desta release

- Backend FastAPI + SQLAlchemy + Alembic.
- Frontend React + TypeScript + Vite.
- Banco com cadeia de migrations linear até `0018_create_communication_consents`.
- Leads, pipeline, atividades, equipe, autenticação, auditoria e relatórios.
- Meta Lead Ads e WhatsApp Cloud API/coexistência.
- Inbox operacional e templates aprovados.
- Distribuição inteligente, SLA, cadências, consentimento/opt-out.
- Triagem e mensagens em lote controladas.
- Motor de recomendações comerciais.
- Dashboard operacional avançado.
- Contrato de integração com Atlas preservado para a próxima fase.

## Validação rápida no Windows

Na raiz do projeto:

```powershell
.\tools\validate_release.ps1
```

O script executa migration, Ruff, pytest, smoke test e build do frontend.

## Executar em desenvolvimento

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm run dev
```

## Segurança

- `.env`, banco local, logs, caches e segredos não fazem parte do pacote limpo.
- Copie `.env.example` para `.env` e troque os segredos antes de produção.
- Tokens, App Secret e chaves da Meta devem permanecer somente no backend.

## Próxima fase

Após a validação desta release no Windows, o próximo passo é empacotamento executável/instalador e, em seguida, integração profunda Nexyra CRM + Atlas.
