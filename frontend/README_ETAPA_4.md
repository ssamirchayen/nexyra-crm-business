# Sprint 2 / Etapa 4 — Pipeline e Oportunidades

Depois de extrair o pacote sobre `C:\Nexyra_CRM`:

## Backend

```powershell
cd C:\Nexyra_CRM
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests alembic
```

Não existe migration nova nesta etapa.

Para iniciar:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

## Frontend

Em outro PowerShell:

```powershell
cd C:\Nexyra_CRM\frontend
npm run build
npm run dev
```

Abra:

`http://127.0.0.1:5173`

Use os menus **Pipeline** e **Oportunidades**.

## Como testar rapidamente

1. Tenha uma empresa/workspace ativa.
2. Cadastre pelo menos um lead.
3. Abra `Pipeline`.
4. Clique em `Nova oportunidade`.
5. Selecione o lead e informe um valor.
6. Arraste o card para outra etapa.
7. Abra o card para ver o histórico.
8. Teste `Marcar ganha` ou `Marcar perdida`.
9. Abra `Oportunidades` para conferir a listagem e os filtros.
