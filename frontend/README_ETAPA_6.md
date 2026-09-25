# Sprint 2 / Etapa 6 — Equipe

A tela `/team` agora está conectada à API real do Nexyra CRM.

## Validar

```powershell
cd C:\Nexyra_CRM
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests alembic

cd C:\Nexyra_CRM\frontend
npm run build
```

Não há migration nova nesta etapa.
