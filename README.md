# Nexyra CRM Business

**Gestão comercial multiusuários, com operação centralizada e acesso por navegador.**

O Nexyra CRM Business reúne leads, oportunidades, atividades, comunicação e
relatórios em uma aplicação compartilhada pela equipe. Esta edição utiliza
PostgreSQL e serviços em Docker para centralizar dados e acesso.

Desenvolvido por **Ssamir Martins**, no projeto **Nexyra**.

## Edições do projeto

| Projeto | Objetivo |
| --- | --- |
| **Este repositório: Business** | Operação comercial centralizada e multiusuários |
| [Nexyra CRM + Atlas](https://github.com/ssamirchayen/nexyra-crm-atlas) | CRM com integração ao assistente Atlas e copiloto |
| [Atlas](https://github.com/ssamirchayen/atlas-assistente-inteligente) | Assistente e plataforma de automação |

As edições são mantidas separadamente. O uso comercial básico do Business não
depende de manter o Atlas em execução.

## Funcionalidades

- Usuários, equipes, papéis, permissões e sessões individuais.
- Leads, importação CSV, distribuição, segmentação e acompanhamento comercial.
- Pipeline, oportunidades, atividades, cadências e follow-ups.
- Dashboards, relatórios e auditoria de operações.
- Integrações com Meta Lead Ads e WhatsApp Cloud API mediante configuração.
- Consentimento, opt-out e controles de comunicação em lote.
- Administração de sessões e senhas.
- Backup com verificação de integridade e teste de restauração isolada.

Integrações externas dependem das contas, credenciais, permissões e configurações
do provedor. A existência do módulo não significa que essas contas estejam conectadas.

## Arquitetura

| Camada | Tecnologias |
| --- | --- |
| Interface | React, TypeScript e Vite |
| API | Python e FastAPI |
| Persistência | PostgreSQL, SQLAlchemy e Alembic |
| Limitação de requisições | Redis na configuração Docker Business |
| Execução | Docker Compose e Nginx |
| Qualidade | pytest, Ruff e build TypeScript/Vite |

## Iniciar localmente

Pré-requisitos: Git, Docker Desktop iniciado e Docker Compose disponível.
Os comandos abaixo usam PowerShell e uma instalação nova.

```powershell
git clone https://github.com/ssamirchayen/nexyra-crm-business.git
cd nexyra-crm-business
Copy-Item .env.docker.example .env.docker
notepad .env.docker
```

Configure as senhas e os segredos do arquivo antes de iniciar. Preserve um
`.env.docker` já existente ao atualizar uma instalação.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 start
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 first-access
```

- Interface padrão: <http://localhost:8080>.
- Prontidão da API: <http://localhost:8000/api/v1/health/ready>.
- Portas podem ser alteradas em `.env.docker`.
- O comando `first-access` conduz a configuração inicial de acesso.

O Compose fornecido usa configurações de desenvolvimento. Exposição pública
exige configuração própria de HTTPS, hosts, origens, segredos e infraestrutura.

## Operação e backup

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 status
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 logs
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 backup
```

Guarde o `.dump` e seu `.dump.sha256.json` juntos, também fora da máquina de
operação. O teste de restauração isolada está descrito em
[SPRINT30_ETAPA7_RESTAURACAO_TESTE.md](SPRINT30_ETAPA7_RESTAURACAO_TESTE.md).

## Testes

```powershell
docker compose -f docker-compose.tests.yml build tests
docker compose -f docker-compose.tests.yml run --rm tests pytest -q
docker compose -f docker-compose.tests.yml run --rm tests ruff check app tests tools alembic
```

Para conferir o frontend, com Node.js e npm instalados:

```powershell
cd frontend
npm.cmd ci
npm.cmd run build
```

### Validação registrada em 25/09/2026

| Verificação | Resultado |
| --- | --- |
| Backend | 334 testes passaram |
| Ruff | Aprovado |
| Frontend | TypeScript e Vite compilaram |
| Auditoria npm durante a instalação | 0 vulnerabilidades reportadas naquela execução |

Resultados de execução local informados no processo de publicação do commit
`35a2c8e`; não são um status de CI nem uma garantia de ausência de vulnerabilidades.
Houve avisos de depreciação no backend e de bundle JavaScript acima de 500 kB.

## Organização

| Caminho | Conteúdo |
| --- | --- |
| `app/` | API, regras de negócio, modelos e segurança |
| `frontend/` | Interface web |
| `alembic/` | Migrações do banco |
| `tests/` | Testes automatizados |
| `tools/` | Operação, backup, validação e empacotamento |
| `docs/` | Documentação técnica |

Consulte também [README_BUSINESS.md](README_BUSINESS.md),
[docs/BUSINESS_STAGE1.md](docs/BUSINESS_STAGE1.md) e
[README_RELEASE.md](README_RELEASE.md).

## Dados e credenciais

Versione somente modelos de configuração com valores fictícios. Arquivos `.env`,
bancos, backups, uploads e credenciais reais devem permanecer fora do Git.
Não remova volumes Docker para resolver problemas sem conferir os backups.

## Autoria

[Ssamir Martins](https://github.com/ssamirchayen) · Nexyra
