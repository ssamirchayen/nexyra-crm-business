# Nexyra Business — Etapa 1: núcleo multiusuário

Esta variante é separada do Nexyra Standalone e do Nexyra + Atlas.

## Arquitetura

- PostgreSQL central como banco compartilhado.
- FastAPI central com pool de conexões configurável.
- Frontend web central (Nginx) acessível por navegador.
- Cliente Desktop fino via WebView, apontando para a mesma URL web.
- Mesmos usuários, papéis, sessões e permissões já existentes no CRM.
- Endpoint `/api/v1/health/ready` valida disponibilidade real do banco.

## Portas sugeridas

- 5432: PostgreSQL (não publicar para a internet).
- 8000: API (pode ficar apenas atrás do proxy).
- 8080: Nexyra Business Web.

## Docker — desenvolvimento/LAN

1. Copie `.env.docker.example` para `.env.docker` e troque as senhas.
2. Execute `docker compose --env-file .env.docker -f docker-compose.business.yml up -d --build`.
3. Abra `http://127.0.0.1:8080`.
4. Valide `http://127.0.0.1:8000/api/v1/health/ready`.

## Instalação nativa

1. Crie PostgreSQL e o banco `nexyra_business`.
2. Copie `.env.business.example` para `.env`.
3. Crie `.venv` e instale `requirements.txt`.
4. Rode `tools/start_business_server.ps1`.
5. Sirva o frontend apontando `VITE_API_BASE_URL` para a API.

## Cliente Desktop

O cliente Business não inicia SQLite/API local. Ele abre o Nexyra central. Copie `.env.client.example` para `.env.client`, configure `NEXYRA_BUSINESS_WEB_URL` e execute `business_desktop_client.py`.

## Escala inicial

Os defaults do pool são 10 conexões base + 20 overflow por processo. Antes de aumentar workers, calcule o limite de conexões do PostgreSQL. Para 30 vendedores, comece com 2 workers e monitore uso/latência antes de escalar.

## Validação da construção

- 223 testes do backend passaram em quatro lotes.
- `compileall` de `app`, `tools` e cliente Desktop passou.
- Validador offline da Etapa 1 passou.
- O build do frontend não foi repetido neste ambiente porque a instalação local de `node_modules` ficou incompleta; nenhum `.tsx` existente foi alterado nesta etapa. Valide `npm.cmd install` + `npm.cmd run build` no Windows.
- A execução real das migrations contra PostgreSQL deve ser validada no servidor/Windows com o driver `psycopg` instalado pelo `requirements.txt`.
