# Nexyra CRM — Sprint 2 / Etapa 6

## Equipe, Vendedores e Permissões

Esta etapa transforma a rota **Equipe** em uma área operacional conectada ao backend.

### Entregas

- tela profissional de equipe;
- cadastro de membro por workspace;
- papéis `admin`, `manager`, `seller` e `operator`;
- edição de função;
- ativação e desativação do vínculo;
- visualização das permissões efetivas por papel;
- resumo comercial por membro;
- leads atribuídos;
- oportunidades abertas, ganhas e perdidas;
- conversão individual;
- receita ganha;
- atividades pendentes e atrasadas;
- filtros por nome, e-mail, função e status;
- endpoint `GET /api/v1/workspaces/{workspace}/team/summary`;
- isolamento por workspace preservado;
- auditoria das alterações de membership preservada.

### Segurança

A etapa administra papéis e permissões, mas não adiciona autenticação de login/senha. A autenticação real e identidade de sessão continuam sendo requisito antes de produção.

### Banco de dados

Nenhuma migration nova.
