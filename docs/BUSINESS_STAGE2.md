# Sprint 30 — Etapa 2: operação e inicialização do Business

Escopo desta entrega: tornar a inicialização do servidor multiusuário verificável e
incorporar as correções encontradas na instalação da Etapa 1. Esta etapa não amplia
as permissões existentes e não modifica o Nexyra standalone ou o Atlas.

## Instalar sobre a Etapa 1

Extraia o conteúdo deste ZIP diretamente na pasta que contém
`docker-compose.business.yml`, substituindo os arquivos correspondentes.
O ZIP é incremental e não inclui `.env`, `.env.docker`, credenciais ou banco.
Mantenha o nome da pasta atual: o Compose usa esse nome para identificar o volume.
Não use `down -v`, pois isso remove dados.

Abra o Docker Desktop e dê dois cliques em `INICIAR_BUSINESS.bat`.
Ou, no PowerShell na raiz do projeto:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 start
```

O script reconstrói as imagens, aguarda o estado saudável da API e reinicia o web
para atualizar o endereço interno da API. O bypass vale apenas para esse processo.
O tempo de espera é 180 segundos; falhas devem ser investigadas com a ação `logs`.
Abra http://localhost:8080 (ou a porta NEXYRA_WEB_PORT do seu .env.docker).

## Comandos

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 status
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 logs
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 stop
```

`stop` preserva os volumes. `start` pode ser repetido sem criar outro administrador.

## Primeiro administrador

Para instalação nova, use `PRIMEIRO_ACESSO_BUSINESS.bat` ou:

```powershell
docker compose --env-file .env.docker -f docker-compose.business.yml exec api python tools/business_first_access.py
```

A rotina só cria o primeiro administrador quando nenhuma credencial existe.
Se você já entrou no Business, não precisa executá-la. Ela não redefine senhas,
não recupera senhas antigas e não altera usuários existentes. A senha gerada é
mostrada apenas no terminal do operador; a cópia temporária é removida ao sair.
Execute apenas uma instância desse comando de cada vez.

## Correções

- Docker fornece os componentes do PostgreSQL separadamente. SQLAlchemy monta a
  URL com codificação da senha; `@`, `%` e outros caracteres não viram hostname.
  Isso não altera a senha existente no PostgreSQL. Se mudar a senha, é necessário
  sincronizar o usuário do banco e a configuração, como na instalação anterior.
  As regras de aspas e interpolação do arquivo Compose continuam aplicáveis.
- Antes das migrations online no PostgreSQL, a tabela `alembic_version` é criada,
  se necessário, e o campo é ampliado para VARCHAR(128). Revisões e dados existentes
  são mantidos. A preparação é idempotente.
- O web aguarda a API ficar saudável, reduzindo o 502 durante a primeira partida.
- A porta direta da API fica vinculada a 127.0.0.1. A interface web mantém sua
  publicação existente. Não foi acrescentada publicação na internet ou TLS.
- O script nativo `start_business_server.ps1` teve as quebras de linha reparadas.

## Validação

10 testes passaram: codificação de senhas reservadas, rejeição de senha vazia,
preservação de DATABASE_URL nativa, primeiro acesso idempotente e testes anteriores
de configuração do banco. O teste de primeiro acesso usa banco SQLite temporário.
Compileall passou nos arquivos Python alterados.
Docker, PowerShell e PostgreSQL não estão disponíveis no ambiente de construção;
a execução real com esses componentes precisa ser confirmada no seu Windows.

Após instalar, confirme a comunicação completa pelo proxy:

Para validar o código dentro do Docker sem usar o banco do Business:

```powershell
docker compose -f docker-compose.tests.yml build tests
docker compose -f docker-compose.tests.yml run --rm tests
```

Ruff no mesmo ambiente:

```powershell
docker compose -f docker-compose.tests.yml run --rm tests ruff check app tests tools alembic
```

Após iniciar o Business, confirme a comunicação completa pelo proxy:

```powershell
Invoke-RestMethod "http://localhost:8080/api/v1/health/ready"
```

Esperado: `ok=True`, `database=postgresql`.
Depois valide dois usuários distintos em navegador normal e janela anônima.
Confira se o perfil vendedor tem apenas as permissões previstas na tela Equipe.
A etapa não declara esse teste manual como concluído.
