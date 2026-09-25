# Sprint 3 / Etapa 2 — Frontend autenticado

Objetivo: substituir o antigo estado de "ambiente local" por uma sessão de usuário real no frontend.

Fluxo:

1. Frontend inicia.
2. Se existir token local, chama `/auth/me`.
3. Sessão válida libera o AppShell.
4. Sem sessão, redireciona para `/login`.
5. Login salva o token opaco e o cliente HTTP passa a enviá-lo como Bearer.
6. Resposta 401 invalida o token local e volta ao login.
7. Logout revoga a sessão no backend e remove o token local.

A lista de empresas visível no frontend passa a vir do contexto autenticado, reduzindo o risco de exibir workspaces fora do acesso do usuário.

Nenhuma migration nova.
