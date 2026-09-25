# Sprint 30 — Etapa 6: backup do Business

Pré-requisito: Etapa 5 instalada. Este patch adiciona backup manual e verificação de integridade. Não altera o banco ou o frontend e não oferece restauração automática nesta etapa.

## Instalação e validação

Salve o ZIP em Downloads, abra o Docker Desktop e execute no PowerShell:

```powershell
cd "C:\PROJETOS NEXYRA + ATLAS\Nexyra_CRM_Business (multiusuarios)"
Expand-Archive -LiteralPath "$HOME\Downloads\Nexyra_Business_Sprint30_Etapa6_Backup_PATCH.zip" -DestinationPath . -Force

docker compose -f docker-compose.tests.yml build tests
if ($LASTEXITCODE -ne 0) { throw "Falha no build." }
docker compose -f docker-compose.tests.yml run --rm tests
if ($LASTEXITCODE -ne 0) { throw "Falha no pytest." }
docker compose -f docker-compose.tests.yml run --rm tests ruff check app tests tools alembic
if ($LASTEXITCODE -ne 0) { throw "Falha no Ruff." }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 start
if ($LASTEXITCODE -ne 0) { throw "Falha ao iniciar o Business." }
```

O start é necessário para reconstruir a imagem da API com a ferramenta de backup. Não pule essa reconstrução: a imagem anterior não contém o novo script.

## Criar backup

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 backup
```

Também é possível abrir BACKUP_BUSINESS.bat com duplo clique.
O serviço db deve estar em execução. O procedimento usa o pg_dump do próprio contêiner PostgreSQL e salva arquivos com data e identificador único em backups:

- nexyra_business_DATA_IDENTIFICADOR.dump: banco no formato custom do PostgreSQL.
- nexyra_business_DATA_IDENTIFICADOR.dump.sha256.json: manifesto com nome, tamanho, data UTC e SHA-256.

O comando lê o catálogo usando pg_restore --list, copia o binário com Docker Compose cp, finaliza o arquivo e confere seu SHA-256. O PowerShell não redireciona o conteúdo binário por >.
O dump usa um snapshot consistente do PostgreSQL, sem interromper o CRM. Arquivos temporários no contêiner são removidos ao final; uma interrupção pode deixar um arquivo .partial no computador ou um temporário em /tmp do contêiner. Arquivos .partial não devem ser tratados como backups concluídos.

Backups existentes não são substituídos e não há limpeza automática. Preserve os dois arquivos juntos e copie-os também para outro disco ou local de backup. Manter a única cópia no mesmo computador não protege contra perda desse computador.

## Conferir um backup salvo

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business_backup.ps1 -Action verify -BackupFile "C:\caminho\do\backup.dump"
```

O .dump.sha256.json precisa estar na mesma pasta. Para conferir o mais recente da pasta padrão:

```powershell
$UltimoBackup = Get-ChildItem .\backups\*.dump | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (!$UltimoBackup) { throw "Nenhum backup encontrado." }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business_backup.ps1 -Action verify -BackupFile $UltimoBackup.FullName
```

Essa conferência usa um contêiner temporário da imagem da API, com a pasta montada somente para leitura. O script Python é independente das configurações da aplicação e não se conecta ao banco. O Docker deve estar aberto e a imagem atualizada disponível.

## Conteúdo e limites

O backup contém TODO o banco do Business, incluindo todas as empresas, usuários, hashes de senha, registros comerciais e informações de integração armazenadas no PostgreSQL. Ele não é criptografado pelo procedimento; guarde-o em local de acesso restrito.

O backup não inclui código, arquivos externos ao banco, .env.docker nem configurações globais/roles do servidor PostgreSQL. Guarde separadamente as configurações necessárias à recuperação, especialmente INTEGRATION_SECRET_MASTER_KEY, pois essa chave é necessária para ler os segredos de integração criptografados que estão no banco. Não envie suas configurações ou backups com dados reais ao chat.

SHA-256 detecta alteração em relação ao manifesto. Não é uma assinatura que garanta autenticidade caso alguém possa substituir ambos os arquivos. A leitura do catálogo e a conferência do hash não substituem um teste de restauração em banco separado. Essa restauração não é executada nesta etapa.

## Validação da entrega

Consulte VALIDACAO_ETAPA6.txt. Os testes exercitam os arquivos de integridade e o comando POSIX com pg_dump/pg_restore simulados; não substituem a execução real de PowerShell, Docker Desktop e PostgreSQL no Windows. O frontend não mudou.
