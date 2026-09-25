# Sprint 30 — Etapa 7: teste isolado de restauração

Pré-requisito: Etapa 6 instalada e um backup .dump com seu .dump.sha256.json.
Esta etapa testa a restauração em um PostgreSQL temporário. Não substitui o banco em uso e não publica um ambiente restaurado para os usuários.

## Instalação

Salve o ZIP em Downloads, abra o Docker Desktop e execute:

```powershell
cd "C:\PROJETOS NEXYRA + ATLAS\Nexyra_CRM_Business (multiusuarios)"
Expand-Archive -LiteralPath "$HOME\Downloads\Nexyra_Business_Sprint30_Etapa7_Restauracao_Teste_PATCH.zip" -DestinationPath . -Force

docker compose -f docker-compose.tests.yml build tests
if ($LASTEXITCODE -ne 0) { throw "Falha no build." }
docker compose -f docker-compose.tests.yml run --rm tests
if ($LASTEXITCODE -ne 0) { throw "Falha no pytest." }
docker compose -f docker-compose.tests.yml run --rm tests ruff check app tests tools alembic
if ($LASTEXITCODE -ne 0) { throw "Falha no Ruff." }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 start
if ($LASTEXITCODE -ne 0) { throw "Falha ao iniciar." }
```

O start reconstrói a imagem com o novo gerador de relatório. O frontend não mudou.

## Testar o backup mais recente

Se ainda não houver backup, crie um primeiro:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business.ps1 backup
if ($LASTEXITCODE -ne 0) { throw "Falha no backup." }
```

Selecione o último arquivo concluído e teste:

```powershell
$UltimoBackup = Get-ChildItem .\backups\*.dump | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (!$UltimoBackup) { throw "Nenhum backup encontrado." }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\business_restore_check.ps1 -BackupFile $UltimoBackup.FullName
if ($LASTEXITCODE -ne 0) { throw "O teste de restauracao ou sua limpeza falhou. Confira a mensagem acima." }
```

Para escolher outro arquivo, informe seu caminho completo em -BackupFile.
Use um backup seu, com o manifesto correspondente. O teste precisa de espaço em disco para uma cópia do dump e para o banco restaurado, além do espaço já usado pelo Business.

## Procedimento

1. Verifica SHA-256 e manifesto antes de criar o banco temporário.
2. Cria um contêiner PostgreSQL 16 com nome único, sem portas publicadas, sem rede do Business e sem montagem de volumes da aplicação. O PostgreSQL cria um volume anônimo próprio.
3. Aguarda o servidor final aceitar conexões TCP internas; o servidor temporário de inicialização não é considerado pronto.
4. Copia o dump para o contêiner e compara novamente o hash da cópia.
5. Executa pg_restore com parada em erro, transação única e sem aplicar proprietários ou privilégios do servidor original.
6. Consulta a revisão de migração, as contagens de oito tabelas principais e vínculos de equipe sem usuário/empresa.
7. Gera relatório em backups/restore-checks/IDENTIFICADOR/restore-report.json.
8. Remove pelo ID exato o contêiner criado e seu volume anônimo, tanto em sucesso quanto em falha durante o teste.

Em falha de limpeza, o terminal mostra o ID do contêiner temporário pendente e o comando para removê-lo. Se o terminal ou Docker for encerrado abruptamente, o bloco de limpeza pode não executar; confira contêineres com nome nexyra-restore-check-* antes de repetir muitos testes. Não remova o volume do Business.

## O que o relatório confirma

- Restauração pelo pg_restore terminou sem erro antes de executar as consultas.
- A cópia restaurada corresponde ao SHA-256 registrado.
- O servidor do teste pertence à versão principal 16.
- A revisão é 0018_create_communication_consents, correspondente ao Business desta entrega.
- As tabelas workspaces, users, workspace_memberships, user_credentials, leads, opportunities, activities e audit_events podem ser consultadas.
- Não há vínculos de equipe sem usuário ou empresa nas consultas realizadas.

O relatório contém apenas metadados e contagens, sem listar usuários, senhas ou registros comerciais. As contagens são as do snapshot do backup; não são comparadas ao banco em uso, que pode ter recebido alterações depois do backup.
O status passed descreve a restauração e a conferência do banco; falhas de limpeza são informadas separadamente no terminal. Um arquivo database-check.json pode permanecer se a conferência do relatório falhar; apenas o restore-report.json é o relatório final.

## Limites

Não há troca do banco principal. Não são testados login, telas, integrações externas, proprietários ou permissões globais do servidor. A chave original INTEGRATION_SECRET_MASTER_KEY continua necessária em uma recuperação operacional dos segredos de integração. Esta etapa não autentica assinaturas do backup nem do manifesto.

Um backup de outra revisão de migração é rejeitado como incompatível com esta versão, mesmo que o pg_restore consiga carregá-lo. Não são executadas migrações automáticas no teste.

Os testes automatizados locais validam o gerador do relatório e a suíte existente. PowerShell, Docker Desktop e restauração real em PostgreSQL não estão disponíveis no ambiente de desenvolvimento; execute o procedimento no Windows para validar essa parte. Nenhum teste local é apresentado como uma restauração real concluída.
