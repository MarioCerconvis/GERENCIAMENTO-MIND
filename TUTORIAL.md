# 📘 Tutorial — Gerenciamento MIND

> **Sistema de Gerenciamento de Projetos com Kanban**
> Versão de Deploy — Julho 2026

---

## Sumário

1. [Visão Geral](#visão-geral)
2. [Perfis de Acesso](#perfis-de-acesso)
3. [Funcionalidades Gerais (Todos os Perfis)](#funcionalidades-gerais)
4. [Funcionalidades do Administrador (Admin)](#funcionalidades-do-administrador)
5. [Funcionalidades do Gestor](#funcionalidades-do-gestor)
6. [Funcionalidades do Funcionário](#funcionalidades-do-funcionário)
7. [Sistema de SLA e Notificações](#sistema-de-sla-e-notificações)
8. [Credenciais Padrão](#credenciais-padrão)

---

## Visão Geral

O **Gerenciamento MIND** é um SaaS web de gerenciamento de projetos baseado em **Kanban**. Ele permite acompanhar Ordens de Serviço (OS), seus módulos (cards), fases de produção, equipe atribuída e prazos (SLA) — tudo em um board visual e interativo.

**Conceitos-chave:**
| Conceito | Descrição |
|---|---|
| **OS (Ordem de Serviço)** | Um projeto. Contém 1 a 6 módulos. |
| **Módulo (Objeto/Card)** | Uma unidade de trabalho dentro da OS. Cada card aparece no Kanban. |
| **Fase (Coluna)** | Uma etapa do processo (ex: Revisão, Diagramação, Envio ao Cliente). |
| **Função** | Especialidade profissional (ex: Redator, Revisor, Web Designer). |
| **Funcionário** | Membro da equipe, vinculado a uma ou mais Funções. |
| **Usuário** | Conta de login. Pode ser vinculada a um Funcionário. |
| **SLA** | Prazo de entrega. Monitorado em 3 níveis: Projeto, Módulo e Fase. |

---

## Perfis de Acesso

| Perfil | Abas Disponíveis | Resumo de Permissões |
|---|---|---|
| **Admin** | Kanban, Projetos, Funcionários, Funções, Fases, Usuários | Acesso total. Gerencia tudo. |
| **Gestor** | Kanban, Projetos, Funcionários, Funções, Fases | Gerencia projetos, equipe e fases. Não gerencia usuários. |
| **Funcionário** | Kanban (apenas cards atribuídos) | Visualiza seus cards, adiciona comentários, conclui etapas. |

---

## Funcionalidades Gerais

> Disponíveis para **todos os perfis** (Admin, Gestor e Funcionário).

### 1. Login

1. Acesse a URL do sistema.
2. Na tela de login, preencha o campo **E-mail** e **Senha**.
3. Clique em **Entrar**.
4. Se for o primeiro acesso, o sistema redirecionará para a tela de **Troca de Senha Obrigatória**.

### 2. Trocar Senha (Primeiro Acesso)

1. Ao fazer login pela primeira vez, a tela "Trocar Senha" aparece automaticamente.
2. Preencha **Nova Senha** (mínimo 6 caracteres) e **Confirmar Senha**.
3. Clique em **Salvar Nova Senha**.
4. Após trocar, você será redirecionado ao Kanban.

### 3. Visualizar o Kanban

1. Após o login, a página principal é o **Board de Projetos (Kanban)**.
2. Cada **coluna** representa uma **Fase** do fluxo de trabalho.
3. Cada **card** dentro da coluna representa um **Módulo** de uma OS.
4. Os cards exibem: código da OS, nome do módulo, cliente, status SLA (🟢/🔴), dias na fase, prioridade e equipe atribuída.

> **Funcionários** veem apenas os cards onde estão atribuídos.
> **Admin/Gestor** veem todos os cards.

### 4. Filtrar Cards no Kanban

Na barra de ferramentas no topo do Kanban, utilize os filtros:

| Filtro | Como Usar |
|---|---|
| **Busca por texto** | Digite no campo "Buscar por OS, cliente..." para buscar por qualquer texto no card. |
| **Filtro de SLA** | Selecione "Dentro do SLA" ou "Fora do SLA" no dropdown. |
| **Filtro de Funcionário** | Selecione um funcionário para ver apenas os cards onde ele está atribuído na fase atual. |
| **Filtro de Prioridade** | Selecione "Sem flag", "🟡 Importante", "🟠 Prioridade" ou "🔴 Urgente". |

### 5. Visualizar Detalhes de um Card

1. **Clique em qualquer card** no Kanban.
2. O modal de detalhes mostra:
   - Status SLA do módulo (dias restantes ou atraso).
   - Dias na fase atual.
   - SLA da fase (se definido).
   - Informações da OS: código, cliente, solicitante, data de inclusão, data limite.
   - Responsável.
   - Fase atual.
   - Descrição do módulo.
   - **Histórico de Fases** — timeline de todas as fases pelas quais o módulo passou, com datas de entrada/saída, tempo de permanência e equipe.
   - **Comentários** — lista de comentários do módulo.

### 6. Adicionar Comentários

1. Abra o detalhe de um card (clique no card).
2. Role até a seção **Comentários**.
3. Escreva o texto no campo e clique em **Enviar**.
4. O comentário fica registrado com autor e data/hora.

### 7. Concluir Etapa (Fluxo Pré-Definido)

Se um módulo possui um **fluxo de fases pré-definido**, o botão **✔ Concluído** aparece no card:

1. Clique em **✔ Concluído** no card.
2. Confirme a ação no popup.
3. O módulo avança automaticamente para a próxima fase do fluxo.
4. A equipe da nova fase é notificada por e-mail.

### 8. Ver Histórico de Atividade

1. Clique no botão **Ver Histórico** na barra de ferramentas do Kanban.
2. No modal, digite o **código da OS** e clique em **Pesquisar**.
3. O sistema mostra uma **timeline completa** para cada módulo da OS:
   - Fases percorridas (com data, responsável e TMO).
   - Comentários adicionados.
   - Fases futuras esperadas (se o módulo tem fluxo pré-definido).
4. Use o checkbox **"Exibir fases futuras esperadas"** para mostrar/ocultar as fases pendentes.

### 9. Logout

1. Clique no botão **Sair** no canto superior direito da página.

---

## Funcionalidades do Administrador

> Exclusivas do perfil **Admin**. Acesso total ao sistema.

### 10. Criar Nova OS (Projeto)

1. No Kanban, clique no botão **+ Novo Projeto**.
2. Preencha as informações da OS:
   - **OS** (código da Ordem de Serviço) — obrigatório, único.
   - **Nome do Projeto** — obrigatório.
   - **Cliente** e **Solicitante** — opcional.
   - **Data Limite da OS** — obrigatório (define o SLA macro).
   - **Responsável pela OS** — selecione um funcionário.
   - **Descrição** e **Comentário Macro** — opcional.
3. Na seção **Módulos**, adicione de 1 a 6 módulos:
   - **Nome do Módulo** — obrigatório (padrão: "Módulo 1", "Módulo 2"...).
   - **Fase Inicial** — a coluna onde o card vai aparecer.
   - **Data Limite do Módulo** — se vazio, herda a data da OS.
   - **Responsável** — se vazio, herda o responsável da OS.
   - **Fluxo de Fases Pré-Definidas** — clique em "+ Adicionar Passo do Fluxo" para definir a sequência de fases automática. O módulo poderá avançar entre elas com o botão "✔ Concluído".
   - **Descrição do Módulo** — opcional.
4. Clique em **Salvar OS**.

### 11. Editar OS

1. Clique em um card para abrir os detalhes.
2. Clique em **Editar**.
3. Modifique os campos desejados (OS, nome, cliente, solicitante, data limite, responsável, descrição, comentário).
4. Clique em **Salvar OS**.

> **Nota:** Módulos não são editados pelo formulário da OS. Edite-os individualmente.

### 12. Excluir OS

1. Abra o detalhe de um card.
2. Clique em **Excluir** (botão vermelho). Apenas Admin pode excluir.
3. Confirme a exclusão.

> Se a OS tiver apenas 1 módulo, exclua a OS inteira. Se tiver mais de 1, você pode excluir módulos individuais.

### 13. Mover Card entre Fases (Drag & Drop)

1. **Arraste um card** de uma coluna e **solte em outra coluna**.
2. Um modal aparece pedindo opcionalmente a **Data Limite da Fase**.
3. Preencha (ou deixe vazio) e clique em **Confirmar**.
4. O card move para a nova fase. A equipe atribuída é notificada.

**Alternativa (via detalhe):**
1. Abra o detalhe do card.
2. Use o dropdown **Fase Atual** para selecionar a nova fase.
3. Clique em **Mover**.

### 14. Reordenar Cards na Mesma Fase

1. **Arraste um card** e **solte na mesma coluna** em uma posição diferente.
2. A ordem é salva automaticamente.

> **Apenas Admin** pode reordenar cards na mesma fase.

### 15. Alterar Prioridade de um Card

1. Abra o detalhe do card.
2. Na seção **Prioridade**, selecione:
   - Sem flag
   - 🟡 Importante
   - 🟠 Prioridade
   - 🔴 Urgente
3. Clique em **Salvar**.
4. O badge de prioridade aparece no card do Kanban.

> **Apenas Admin** pode alterar prioridades.

### 16. Atribuir Funcionário a uma Fase

1. Abra o detalhe do card.
2. No **Histórico de Fases**, na fase ativa, clique em **+ Atribuir Funcionário**.
3. O sistema lista apenas os **funcionários elegíveis** (que possuem as funções exigidas pela fase).
4. Selecione o funcionário e clique em **Atribuir**.
5. O funcionário é notificado por e-mail.

### 17. Criar Nova Fase (via Kanban)

1. No Kanban, clique em **+ Nova Fase**.
2. Preencha:
   - **Nome da Fase** — obrigatório.
   - **Cor** — escolha uma cor para a coluna.
   - **Descrição** — opcional.
   - **Funções exigidas** — marque as funções que um funcionário deve ter para ser atribuído a esta fase.
3. Clique em **Salvar**.
4. A nova coluna aparece no Kanban.

---

### Painel Administrativo (Admin)

Acessível pelo botão **Admin** na barra do Kanban. Contém 4 abas:

### 18. Gerenciar Funcionários

**Aba: Funcionários** (no Painel Admin)

| Ação | Como Fazer |
|---|---|
| **Listar** | Ao abrir a aba, a tabela mostra todos os funcionários com nome, e-mail e funções. |
| **Criar** | Clique em **+ Novo**. Preencha nome, e-mail e marque as funções. Clique em **Salvar**. |
| **Editar** | Clique em **Editar** na linha do funcionário. Modifique os dados e clique em **Salvar**. |
| **Excluir** | Clique em **Excluir** na linha do funcionário. Confirme. |

### 19. Gerenciar Funções

**Aba: Funções** (no Painel Admin)

| Ação | Como Fazer |
|---|---|
| **Listar** | A tabela mostra todas as funções cadastradas. |
| **Criar** | Clique em **+ Nova**. Preencha o nome da função. Clique em **Salvar**. |
| **Editar** | Clique em **Editar** na linha. Modifique o nome. Clique em **Salvar**. |
| **Excluir** | Clique em **Excluir**. Confirme. |

### 20. Gerenciar Fases

**Aba: Fases** (no Painel Admin)

| Ação | Como Fazer |
|---|---|
| **Listar** | A tabela mostra todas as fases (incluindo desativadas), com ordem, nome, cor e funções exigidas. Fases desativadas aparecem com opacidade reduzida e tag vermelha. |
| **Criar** | Clique em **+ Nova**. Preencha nome, cor, ordem, descrição e funções exigidas. Clique em **Salvar**. |
| **Editar** | Clique em **Editar** na linha. Modifique os campos. Clique em **Salvar**. |
| **Excluir** | Clique em **Excluir**. Se a fase possui cards atualmente, a exclusão é **bloqueada** (mova os cards primeiro). Se a fase possui histórico, ela é **desativada** (soft delete). Se não possui histórico, ela é **excluída permanentemente**. |
| **Reativar** | Para fases desativadas, clique em **Reativar**. A fase volta a aparecer no Kanban. |

### 21. Gerenciar Usuários

**Aba: Usuários** (no Painel Admin — **Apenas Admin**)

| Ação | Como Fazer |
|---|---|
| **Listar** | A tabela mostra todos os usuários com nome, e-mail, perfil e status ativo. |
| **Criar** | Clique em **+ Novo**. Preencha nome, e-mail, perfil (Funcionário/Gestor/Admin) e senha (padrão: `Trocar@123`). Clique em **Salvar**. O usuário terá que trocar a senha no primeiro login. |
| **Editar** | Clique em **Editar**. Modifique nome e perfil. Clique em **Salvar**. |
| **Reset de Senha** | Clique em **Reset Senha**. Um prompt pede a nova senha (deixe em branco para usar `Trocar@123`). O usuário terá que trocar a senha no próximo login. |
| **Excluir** | Clique em **Excluir**. Confirme. Não é possível excluir a si mesmo. |

### 22. Excluir Comentários

- Apenas **Admin** pode excluir comentários de qualquer usuário.

---

## Funcionalidades do Gestor

> O perfil **Gestor** tem as mesmas capacidades do Admin, **exceto**:

| Funcionalidade | Gestor pode? |
|---|---|
| Criar/Editar/Excluir OS | ✅ Sim |
| Mover cards entre fases (drag & drop) | ✅ Sim |
| Atribuir funcionários a fases | ✅ Sim |
| Criar/Editar/Excluir Funcionários | ✅ Sim |
| Criar/Editar/Excluir Funções | ✅ Sim |
| Criar/Editar/Excluir Fases | ✅ Sim |
| Gerenciar Usuários | ❌ Não |
| Alterar Prioridade de cards | ❌ Não |
| Reordenar cards na mesma fase | ❌ Não |
| Excluir Comentários | ❌ Não |
| Excluir OS (projeto inteiro) | ❌ Não (apenas Admin) |

---

## Funcionalidades do Funcionário

> O perfil **Funcionário** tem acesso limitado ao Kanban.

| Funcionalidade | Descrição |
|---|---|
| Ver Kanban | Visualiza **apenas os cards onde está atribuído**. |
| Ver detalhes de cards | Abre o modal com informações do módulo, histórico e comentários. |
| Adicionar comentários | Pode escrever comentários nos cards atribuídos. |
| Concluir etapa | Se o card possui fluxo pré-definido, pode clicar em **✔ Concluído** para avançar. |
| Ver Histórico | Pesquisa o histórico de qualquer OS pelo código. |
| Filtrar cards | Usa os filtros de busca, SLA, funcionário e prioridade. |

> **O funcionário NÃO pode:** criar/editar/excluir OS, mover cards, atribuir equipe, gerenciar cadastros, acessar o painel Admin.

---

## Sistema de SLA e Notificações

### Indicadores Visuais de SLA

Os cards exibem cores de fundo de acordo com o SLA da fase:

| Dias Restantes (Fase) | Cor do Card |
|---|---|
| Mais de 2 dias | 🟢 Verde claro |
| 2 dias | 🟡 Amarelo |
| 0 a 1 dia | 🟠 Laranja |
| Atrasado (negativo) | 🔴 Vermelho |

### Verificação Automática de SLA

O sistema executa uma verificação diária automática (configurável via `.env`):

1. **SLA do Projeto** — Se a data limite macro da OS foi ultrapassada, o responsável recebe e-mail.
2. **SLA do Módulo** — Se a data limite do módulo foi ultrapassada, o responsável recebe e-mail.
3. **SLA da Fase** — Se a data limite da fase ativa foi ultrapassada, o responsável recebe e-mail.

### Notificações por E-mail

| Evento | Quem Recebe |
|---|---|
| Funcionário atribuído a uma fase | O funcionário atribuído |
| Módulo movido para nova fase | Equipe da nova fase |
| SLA do Projeto ultrapassado | Responsável do projeto |
| SLA do Módulo ultrapassado | Responsável do módulo |
| SLA da Fase ultrapassado | Responsável do módulo |

> **Nota:** Se o envio de e-mail não estiver ativo (`.env` → `EMAIL_ATIVO=false`), as notificações são simuladas no console do servidor.

---

## Credenciais Padrão

### Admin Padrão (criado automaticamente)
- **E-mail:** `admin@mind.com.br`
- **Senha:** `admin123`

### Demais Usuários (criados pelo seed)
- **Senha padrão:** `Trocar@123`
- **Troca obrigatória** no primeiro login.

### Perfis dos usuários seed:
| Nome | E-mail | Perfil |
|---|---|---|
| Eduardo | eduardo@mind.com.br | Admin |
| John | john@mind.com.br | Gestor |
| Carol | carol@mind.com.br | Funcionário |
| Renato | renato@mind.com.br | Funcionário |
| Lucas | lucas@mind.com.br | Funcionário |
| Luiza | luiza@mind.com.br | Funcionário |
| Marina | marina@mind.com.br | Funcionário |
| Juliana | juliana@mind.com.br | Funcionário |
| Beatriz | beatriz@mind.com.br | Funcionário |
| Gustavo | gustavo@mind.com.br | Funcionário |
| Leandro | leandro@mind.com.br | Funcionário |
| Petter | petter@mind.com.br | Funcionário |

---

> **Gerenciamento MIND** — Sistema de Gerenciamento de Projetos © 2026
