# Hotfix Nexyra CRM Desktop — Uvicorn logging

Corrige a falha `Unable to configure formatter 'default'` no executável PyInstaller. O Uvicorn passa a reutilizar o logging já configurado pelo launcher, sem tentar carregar seu formatter padrão dentro do bundle.
