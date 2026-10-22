/* ═══════════════════════════════════════════════════════════════════════
   KANBAN.JS — Board de Projetos
   ═══════════════════════════════════════════════════════════════════════ */

let currentUser = null;
let boardData = [];
let allFuncoes = [];
let allFuncionarios = [];
let allFases = [];
let currentViewMode = "vertical"; // "vertical" or "horizontal"

// ─── Init ────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
    await loadUser();
    await loadBoard();
    setupToolbar();
    setupEventListeners();
});

async function loadUser() {
    const res = await fetch("/api/me");
    if (!res.ok) { window.location = "/login"; return; }
    currentUser = await res.json();
    document.getElementById("user-name").textContent = currentUser.nome;
    document.getElementById("user-badge").textContent = currentUser.perfil;
    // Show/hide buttons based on role
    if (isGestao()) {
        document.getElementById("btn-novo-projeto").style.display = "";
        document.getElementById("btn-nova-fase").style.display = "";
        document.getElementById("btn-admin").style.display = "";
        document.getElementById("btn-prioridades").style.display = "";
        // Lista completa de funcionários para o filtro "ver cards de um funcionário"
        const res = await fetch("/api/funcionarios");
        if (res.ok) allFuncionarios = await res.json();
    }
}

function isGestao() {
    return ["admin", "gestor"].includes(currentUser?.perfil);
}

// Admin/Gestor: id do funcionário selecionado no filtro (ou null)
function getFuncionarioEmFoco() {
    if (!isGestao()) return null;
    const value = document.getElementById("kanban-filter-funcionario")?.value;
    return value ? parseInt(value) : null;
}

// ─── Prioridade numérica (fila por funcionário) ──────────────────────────────

// Funcionário cuja fila define a prioridade exibida/ordenada no board:
// o próprio funcionário logado, ou o selecionado no filtro (admin/gestor)
function prioridadeDoContexto(objeto) {
    const prios = objeto.prioridades_fase_atual || [];
    if (currentUser?.perfil === "funcionario") {
        return prios.find(p => p.funcionario_id === currentUser.funcionario_id) || null;
    }
    const funcId = getFuncionarioEmFoco();
    if (funcId) return prios.find(p => p.funcionario_id === funcId) || null;
    return null;
}

// Prioridade usada para ordenar/filtrar: a do contexto, senão a melhor posição da equipe
function prioridadeEfetiva(objeto) {
    const ctx = prioridadeDoContexto(objeto);
    if (ctx) return ctx.prioridade;
    const valores = (objeto.prioridades_fase_atual || [])
        .map(p => p.prioridade)
        .filter(v => v != null);
    return valores.length ? Math.min(...valores) : null;
}

function classePrioridade(valor) {
    if (valor === 1) return "prio-1";
    if (valor <= 3) return "prio-2";
    return "prio-n";
}

function badgesPrioridade(objeto) {
    const ctx = prioridadeDoContexto(objeto);
    if (ctx) {
        if (ctx.prioridade == null) return "";
        return `<span class="prio-badge ${classePrioridade(ctx.prioridade)}" title="Prioridade ${ctx.prioridade} de ${ctx.total} na fila de ${ctx.nome}">🎯 #${ctx.prioridade} <span class="prio-total">de ${ctx.total}</span></span>`;
    }
    return (objeto.prioridades_fase_atual || [])
        .filter(p => p.prioridade != null)
        .map(p => `<span class="prio-badge ${classePrioridade(p.prioridade)}" title="Prioridade ${p.prioridade} de ${p.total} na fila de ${p.nome}">${p.nome.split(" ")[0]} #${p.prioridade}</span>`)
        .join("");
}

async function loadBoard() {
    // Admin/Gestor com funcionário selecionado: o backend devolve só os cards dele,
    // com a relação (atual/concluído/futuro) calculada para ele
    let url = "/api/kanban";
    const funcId = getFuncionarioEmFoco();
    if (funcId) url += `?funcionario_id=${funcId}`;
    const res = await fetch(url);
    if (!res.ok) return;
    boardData = await res.json();
    renderBoard(boardData);
    populateFuncionarioFilter(boardData);
    // Reaplicar filtros ativos após recarregar (ex.: depois de mover/aprovar um card)
    filterBoard();
    renderRelacaoResumo();
}

async function loadSelectData() {
    const [funcRes, funcioRes, fasesRes] = await Promise.all([
        fetch("/api/funcoes"), fetch("/api/funcionarios"), fetch("/api/fases")
    ]);
    if (funcRes.ok) allFuncoes = await funcRes.json();
    if (funcioRes.ok) allFuncionarios = await funcioRes.json();
    if (fasesRes.ok) allFases = await fasesRes.json();
}

// ─── Render Board ────────────────────────────────────────────────────────────

function renderBoard(data) {
    const board = document.getElementById("kanban-board");
    board.innerHTML = "";

    // Apply view mode class
    board.classList.remove("horizontal");
    if (currentViewMode === "horizontal") {
        board.classList.add("horizontal");
    }

    // Sort by ordem
    data.sort((a, b) => (a.ordem ?? 999) - (b.ordem ?? 999));

    data.forEach(col => {
        const column = document.createElement("div");
        column.className = "kanban-column";
        column.dataset.faseId = col.id ?? "sem_fase";

        const headerColor = col.cor || "#94a3b8";
        column.innerHTML = `
            <div class="column-header" style="--col-color: ${headerColor}">
                <div class="column-title">
                    <span style="color: ${headerColor};">●</span>
                    ${col.nome}
                </div>
                <span class="column-count">${col.objetos.length}</span>
            </div>
            <div class="column-body" data-fase-id="${col.id ?? 'sem_fase'}"></div>
        `;

        // Set header top border color
        column.querySelector(".column-header").style.cssText += `border-top: 3px solid ${headerColor};`;

        const body = column.querySelector(".column-body");

        // Prioridade numérica (1 primeiro; sem prioridade por último), depois ordem manual
        col.objetos.sort((a, b) => {
            const pa = prioridadeEfetiva(a) ?? Infinity;
            const pb = prioridadeEfetiva(b) ?? Infinity;
            if (pa !== pb) return pa - pb;
            return (a.ordem_kanban || 0) - (b.ordem_kanban || 0);
        });

        if (col.objetos.length === 0) {
            body.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📋</div>Nenhum card</div>`;
        } else {
            col.objetos.forEach(p => {
                body.appendChild(createCard(p));
            });
        }

        // Drag & drop listeners
        if (["admin", "gestor"].includes(currentUser?.perfil)) {
            body.addEventListener("dragover", handleDragOver);
            body.addEventListener("dragleave", handleDragLeave);
            body.addEventListener("drop", handleDrop);
        }

        board.appendChild(column);
    });
}

function createCard(projeto) {
    const card = document.createElement("div");
    card.className = "project-card";
    card.dataset.objetoId = projeto.id;
    card.dataset.prioridade = prioridadeEfetiva(projeto) ?? "";
    // Phase-level funcionários for filtering
    const funcsFase = (projeto.funcionarios_fase_atual || []).map(f => f.nome);
    card.dataset.funcionariosFase = funcsFase.join(",");
    // Relationship data for filtering (pendente, concluido, futuro)
    const relacao = projeto.relacao_funcionario || [];
    card.dataset.relacaoFuncionario = relacao.join(",");
    card.draggable = ["admin", "gestor"].includes(currentUser?.perfil);

    const sla = projeto.sla || {};
    const slaClass = sla.flag === "Dentro do SLA" ? "sla-dentro" : "sla-fora";
    const slaIcon = sla.flag === "Dentro do SLA" ? "🟢" : "🔴";
    const slaDias = sla.dias_restantes != null
        ? (sla.dias_restantes >= 0 ? `${sla.dias_restantes}d restantes` : `${Math.abs(sla.dias_restantes)}d atraso`)
        : "";
    
    let diasFase = sla.dias_na_fase != null ? `⏱️ ${sla.dias_na_fase}d na fase` : "";
    if (projeto.sla_fase) {
        const sf = projeto.sla_fase;
        const sfIcon = sf.flag === "Dentro do SLA" ? "🟢" : "🔴";
        const sfDias = sf.dias_restantes >= 0 ? `${sf.dias_restantes}d rest.` : `${Math.abs(sf.dias_restantes)}d atraso`;
        diasFase += ` | ${sfIcon} ${sfDias} (Fase)`;
        
        // SLA de Fase Visual
        if (sf.dias_restantes > 2) {
            card.style.backgroundColor = "rgba(144, 238, 144, 0.2)";
        } else if (sf.dias_restantes === 2) {
            card.style.backgroundColor = "rgba(255, 255, 0, 0.2)";
        } else if (sf.dias_restantes === 1 || sf.dias_restantes === 0) {
            card.style.backgroundColor = "rgba(255, 165, 0, 0.2)";
        } else if (sf.dias_restantes < 0) {
            card.style.backgroundColor = "rgba(255, 0, 0, 0.15)";
        }
    }

    let hasProximaEtapa = projeto.has_proxima_etapa;

    // Datas de início previstas: só alertam, nunca movem o card
    const alertas = projeto.alertas_inicio || {};
    let inicioAlerta = "";
    if (alertas.aguardando) {
        const a = alertas.aguardando;
        inicioAlerta += `<div class="inicio-alerta inicio-aguardando" title="Início previsto do módulo">🕒 Início previsto: ${formatDate(a.data)} (em ${a.dias}d)</div>`;
    }
    if (alertas.proxima_atrasada) {
        const a = alertas.proxima_atrasada;
        inicioAlerta += `<div class="inicio-alerta inicio-atrasado" title="O card só avança quando a fase atual for concluída">⚠️ ${a.fase_nome} deveria ter iniciado em ${formatDate(a.data)} (${a.dias}d)</div>`;
    }

    const priorityBadge = badgesPrioridade(projeto);

    // ── Aprovação (dupla aprovação) ──
    const aprovacao = projeto.aprovacao || { aprovados: 0, total: 0, todos_aprovaram: true };
    const aprovacaoFuncs = projeto.aprovacao_funcionarios || [];
    const isMultiApproval = aprovacao.total > 1;
    const myFuncId = currentUser?.funcionario_id;
    const myApproval = aprovacaoFuncs.find(f => f.id === myFuncId);
    const jaAprovei = myApproval?.aprovado_em != null;
    const isEmployee = currentUser?.perfil === "funcionario";

    let aprovacaoBadge = "";
    if (isMultiApproval) {
        const badgeColor = aprovacao.todos_aprovaram ? "#22c55e" : "#f59e0b";
        aprovacaoBadge = `<div style="margin-top:6px;"><span style="display:inline-flex;align-items:center;gap:4px;font-size:12px;padding:3px 8px;border-radius:12px;background:${badgeColor}15;color:${badgeColor};font-weight:600;border:1px solid ${badgeColor}33;">🔒 ${aprovacao.aprovados}/${aprovacao.total} aprovados</span></div>`;
    }

    // Botão de ação
    let actionButton = "";
    if (hasProximaEtapa) {
        if (isEmployee && isMultiApproval) {
            if (jaAprovei) {
                actionButton = `
                    <div style="margin-top: 8px;">
                        <button class="btn btn-sm" disabled style="width: 100%; background-color: #94a3b8; border-color: #94a3b8; color: white; cursor: not-allowed;">✅ Aprovado (${aprovacao.aprovados}/${aprovacao.total})</button>
                    </div>`;
            } else {
                actionButton = `
                    <div style="margin-top: 8px;">
                        <button class="btn btn-primary btn-sm" onclick="aprovarFase(event, ${projeto.fase_ativa_id})" style="width: 100%; background-color: #f59e0b; border-color: #f59e0b; color: white;">✔ Aprovar Fase</button>
                    </div>`;
            }
        } else {
            actionButton = `
                <div style="margin-top: 8px;">
                    <button class="btn btn-primary btn-sm" onclick="concluirFasePreDefinida(event, ${projeto.id})" style="width: 100%; background-color: #22c55e; border-color: #22c55e; color: white;">✔ Concluído</button>
                </div>`;
        }
    }

    card.innerHTML = `
        <div class="card-os">${projeto.projeto_os} <span style="font-size:0.8em; color:#64748b; font-weight:normal;">- ${projeto.nome}</span></div>
        <div class="card-cliente" style="font-size:0.85em; font-weight:bold; margin-bottom: 2px;">${projeto.projeto_nome || ""}</div>
        <div class="card-cliente">${projeto.cliente || "—"}</div>
        
        ${priorityBadge ? `<div class="prio-badges">${priorityBadge}</div>` : ""}
        
        <div class="card-footer">
            <span class="sla-badge ${slaClass}">${slaIcon} ${slaDias}</span>
            <span class="card-days">${diasFase}</span>
        </div>
        ${funcsFase.length > 0
            ? `<div class="card-responsavel">👤 ${funcsFase.join(", ")}</div>`
            : (projeto.responsavel_nome ? `<div class="card-responsavel">👤 ${projeto.responsavel_nome}</div>` : "")}
        ${inicioAlerta}
        ${aprovacaoBadge}
        ${relacao.length > 0 ? `<div style="margin-top:4px;">${relacao.map(r => {
            if (r === "pendente") return '<span class="relacao-badge relacao-pendente">⏳ Atual</span>';
            if (r === "concluido") return '<span class="relacao-badge relacao-concluido">✅ Concluído</span>';
            if (r === "futuro") return '<span class="relacao-badge relacao-futuro">🔮 Futuro</span>';
            return '';
        }).join('')}</div>` : ''}
        ${actionButton}
    `;

    // Click to open detail
    card.addEventListener("click", (e) => {
        if (e.target.closest(".btn")) return;
        openDetail(projeto.id);
    });

    // Drag events
    card.addEventListener("dragstart", handleDragStart);
    card.addEventListener("dragend", handleDragEnd);

    return card;
}

// ─── Concluir Fase Pré-Definida ──────────────────────────────────────────────
async function concluirFasePreDefinida(event, projetoId) {
    event.stopPropagation();
    if (!confirm("Confirmar a conclusão desta etapa e mover para a próxima do fluxo pré-definido?")) return;
    
    const res = await fetch(`/api/objetos/${projetoId}/concluir-fase`, {
        method: "POST"
    });

    if (res.ok) {
        const data = await res.json();
        if (data.movido) {
            showToast("Fase concluída e movida com sucesso!", "success");
        } else if (data.aprovado) {
            showToast(`Aprovação registrada! (${data.total_aprovacoes || 'Completa'})`, "success");
        } else {
            showToast("Fase concluída!", "success");
        }
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao concluir fase", "error");
    }
}

// ─── Aprovar Fase (dupla aprovação) ──────────────────────────────────────────
async function aprovarFase(event, faseAtivaId) {
    event.stopPropagation();
    if (!confirm("Confirmar sua aprovação desta fase?")) return;
    
    const res = await fetch(`/api/objeto-fase/${faseAtivaId}/aprovar`, {
        method: "POST"
    });

    if (res.ok) {
        const data = await res.json();
        if (data.movido) {
            showToast("Todos aprovaram! Card movido para a próxima fase.", "success");
        } else {
            showToast(`Aprovação registrada! (${data.total_aprovacoes || 'Completa'})`, "success");
        }
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao aprovar", "error");
    }
}

// ─── Drag & Drop ─────────────────────────────────────────────────────────────

let draggedObjetoId = null;

function handleDragStart(e) {
    draggedObjetoId = e.target.dataset.objetoId;
    e.target.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
}

function handleDragEnd(e) {
    e.target.classList.remove("dragging");
    document.querySelectorAll(".column-body").forEach(b => b.classList.remove("drag-over"));
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.project-card:not(.dragging)')];
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    e.currentTarget.classList.add("drag-over");
    
    const afterElement = getDragAfterElement(e.currentTarget, e.clientY);
    const draggable = document.querySelector('.dragging');
    if (draggable) {
        if (afterElement == null) {
            e.currentTarget.appendChild(draggable);
        } else {
            e.currentTarget.insertBefore(draggable, afterElement);
        }
    }
}

function handleDragLeave(e) {
    e.currentTarget.classList.remove("drag-over");
}

let pendingMove = null;

async function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove("drag-over");
    const newFaseId = e.currentTarget.dataset.faseId;
    if (!draggedObjetoId || newFaseId === "sem_fase") return;

    let oldFaseId = null;
    boardData.forEach(col => {
        if (col.objetos.find(o => o.id == draggedObjetoId)) {
            oldFaseId = col.id ? col.id.toString() : "sem_fase";
        }
    });

    if (newFaseId !== oldFaseId) {
        // Phase changed
        pendingMove = { projetoId: draggedObjetoId, faseId: parseInt(newFaseId), isInline: false };
        document.getElementById("mover-data-limite").value = "";
        abrirModal("modal-mover-fase");
    } else {
        // Reordering in the same phase
        if (currentUser?.perfil !== "admin") {
            showToast("Apenas administradores podem reordenar cards na mesma fase.", "error");
            await loadBoard();
        } else {
            const cards = [...e.currentTarget.querySelectorAll('.project-card')];
            const ordemIds = cards.map(c => parseInt(c.dataset.objetoId));
            
            const res = await fetch('/api/fases/reordenar-objetos', {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ordem: ordemIds }),
            });
            
            if (res.ok) {
                await loadBoard();
            } else {
                showToast("Erro ao reordenar", "error");
                await loadBoard();
            }
        }
    }
    draggedObjetoId = null;
}

function cancelarMoverFase() {
    pendingMove = null;
    fecharModal("modal-mover-fase");
}

document.getElementById("btn-confirmar-mover")?.addEventListener("click", async () => {
    if (!pendingMove) return;
    const dataLimite = document.getElementById("mover-data-limite").value;
    
    const payload = { fase_id: pendingMove.faseId };
    if (dataLimite) {
        payload.data_limite_fase = dataLimite;
    }
    
    const res = await fetch(`/api/objetos/${pendingMove.projetoId}/mover-fase`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    if (res.ok) {
        showToast("Card movido com sucesso!", "success");
        fecharModal("modal-mover-fase");
        if (pendingMove.isInline) fecharModal("modal-detalhe");
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao mover projeto", "error");
    }
    pendingMove = null;
});

// ─── Toolbar ─────────────────────────────────────────────────────────────────

function setupToolbar() {
    // Search
    document.getElementById("kanban-search").addEventListener("input", (e) => {
        filterBoard();
    });
    document.getElementById("kanban-filter-sla").addEventListener("change", () => {
        filterBoard();
    });
    document.getElementById("kanban-filter-funcionario").addEventListener("change", async () => {
        // Admin/Gestor: recarrega o board com os cards do funcionário selecionado
        if (isGestao()) {
            await loadBoard();
        } else {
            renderBoard(boardData);  // reordena pela fila do funcionário selecionado
        }
        filterBoard();
    });
    document.getElementById("kanban-filter-prioridade").addEventListener("change", () => {
        filterBoard();
    });
    document.getElementById("kanban-filter-relacao")?.addEventListener("change", () => {
        filterBoard();
        renderRelacaoResumo();
    });

    // View toggle
    document.querySelectorAll(".view-toggle-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const newMode = btn.dataset.view;
            if (newMode === currentViewMode) return;
            currentViewMode = newMode;
            document.querySelectorAll(".view-toggle-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            renderBoard(boardData);
            filterBoard();
        });
    });
}

function filterBoard() {
    const query = document.getElementById("kanban-search").value.toLowerCase();
    const slaFilter = document.getElementById("kanban-filter-sla").value;
    const funcFilter = document.getElementById("kanban-filter-funcionario").value;
    const prioFilter = document.getElementById("kanban-filter-prioridade").value;
    const relacaoFilter = document.getElementById("kanban-filter-relacao")?.value || "";
    const cards = document.querySelectorAll(".project-card");

    cards.forEach(card => {
        const text = card.textContent.toLowerCase();
        const matchQuery = !query || text.includes(query);

        let matchSla = true;
        if (slaFilter) {
            const badge = card.querySelector(".sla-badge");
            if (slaFilter === "dentro") matchSla = badge?.classList.contains("sla-dentro");
            if (slaFilter === "fora") matchSla = badge?.classList.contains("sla-fora");
        }

        // Admin/Gestor: o backend já filtrou os cards do funcionário selecionado.
        // Funcionário: filtra pelos colegas na fase atual (por nome).
        let matchFunc = true;
        if (funcFilter && !isGestao()) {
            const funcionariosFase = card.dataset.funcionariosFase || "";
            matchFunc = funcionariosFase.split(",").includes(funcFilter);
        }

        let matchPrio = true;
        if (prioFilter !== "") {
            const prio = card.dataset.prioridade ? parseInt(card.dataset.prioridade) : null;
            if (prioFilter === "1") matchPrio = prio === 1;
            else if (prioFilter === "top3") matchPrio = prio !== null && prio <= 3;
            else if (prioFilter === "sem") matchPrio = prio === null;
        }

        // Relationship filter
        let matchRelacao = true;
        if (relacaoFilter) {
            const relacaoData = card.dataset.relacaoFuncionario || "";
            const relacoes = relacaoData ? relacaoData.split(",").filter(r => r) : [];
            
            if (relacoes.length === 0) {
                // Sem dados de relação: filtros de situação não se aplicam
                matchRelacao = false;
            } else {
                switch (relacaoFilter) {
                    case "pendentes":
                        matchRelacao = relacoes.includes("pendente");
                        break;
                    case "concluidos":
                        matchRelacao = relacoes.includes("concluido");
                        break;
                    case "futuros":
                        matchRelacao = relacoes.includes("futuro");
                        break;
                    case "pendentes_futuros":
                        matchRelacao = relacoes.includes("pendente") || relacoes.includes("futuro");
                        break;
                }
            }
        }

        card.style.display = (matchQuery && matchSla && matchFunc && matchPrio && matchRelacao) ? "" : "none";
    });

    updateColumnCounts();
}

function populateFuncionarioFilter(data) {
    const select = document.getElementById("kanban-filter-funcionario");
    const currentValue = select.value;

    if (isGestao()) {
        // Admin/Gestor: todos os funcionários (por id), inclusive os que só têm
        // cards concluídos ou futuros
        select.innerHTML = '<option value="">Todos os Funcionários</option>';
        [...allFuncionarios]
            .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
            .forEach(f => {
                select.innerHTML += `<option value="${f.id}">${f.nome}</option>`;
            });
        if (currentValue && allFuncionarios.some(f => String(f.id) === currentValue)) {
            select.value = currentValue;
        }
        atualizarFiltroRelacao();
        return;
    }

    const names = new Set();
    data.forEach(col => {
        (col.objetos || []).forEach(obj => {
            (obj.funcionarios_fase_atual || []).forEach(f => {
                if (f.nome) names.add(f.nome);
            });
        });
    });
    select.innerHTML = '<option value="">Todos os Funcionários</option>';
    [...names].sort((a, b) => a.localeCompare(b, 'pt-BR')).forEach(name => {
        select.innerHTML += `<option value="${name}">${name}</option>`;
    });
    // Restore previous selection if still available
    if (currentValue && names.has(currentValue)) {
        select.value = currentValue;
    }
}

// Filtro de situação (atual/concluído/futuro): só faz sentido com um funcionário em foco
function atualizarFiltroRelacao() {
    const select = document.getElementById("kanban-filter-relacao");
    const optTodos = document.getElementById("kanban-filter-relacao-todos");
    if (!select || !optTodos) return;

    if (!isGestao()) {
        optTodos.textContent = "Meus Cards";
        return;
    }
    const funcId = getFuncionarioEmFoco();
    if (funcId) {
        const func = allFuncionarios.find(f => f.id === funcId);
        optTodos.textContent = `Todos os cards de ${func ? func.nome : "funcionário"}`;
        select.disabled = false;
        select.title = "";
    } else {
        optTodos.textContent = "Situação: escolha um funcionário";
        select.value = "";
        select.disabled = true;
        select.title = "Selecione um funcionário para filtrar os cards atuais, concluídos e futuros dele";
    }
}

// Resumo clicável com a contagem de cards atuais, concluídos e futuros do funcionário em foco
function renderRelacaoResumo() {
    const container = document.getElementById("relacao-resumo");
    if (!container) return;

    const funcId = getFuncionarioEmFoco();
    const emFoco = isGestao() ? funcId !== null : currentUser?.funcionario_id != null;
    if (!emFoco) {
        container.style.display = "none";
        container.innerHTML = "";
        return;
    }

    const contagem = { pendente: 0, concluido: 0, futuro: 0 };
    boardData.forEach(col => {
        (col.objetos || []).forEach(o => {
            (o.relacao_funcionario || []).forEach(r => {
                if (r in contagem) contagem[r]++;
            });
        });
    });

    let titulo = "Meus cards";
    if (isGestao()) {
        const func = allFuncionarios.find(f => f.id === funcId);
        titulo = `Cards de ${func ? func.nome : "funcionário"}`;
    }

    const filtroAtual = document.getElementById("kanban-filter-relacao")?.value || "";
    const chips = [
        { valor: "", rotulo: "Todos", classe: "relacao-chip-todos", qtd: null },
        { valor: "pendentes", rotulo: "⏳ Atuais", classe: "relacao-pendente", qtd: contagem.pendente },
        { valor: "concluidos", rotulo: "✅ Concluídos", classe: "relacao-concluido", qtd: contagem.concluido },
        { valor: "futuros", rotulo: "🔮 Futuros", classe: "relacao-futuro", qtd: contagem.futuro },
    ];

    container.innerHTML = `
        <span class="relacao-resumo-titulo">${titulo}</span>
        ${chips.map(c => `
            <button type="button" class="relacao-chip ${c.classe} ${filtroAtual === c.valor ? "ativo" : ""}"
                    data-valor="${c.valor}" aria-pressed="${filtroAtual === c.valor}">
                ${c.rotulo}${c.qtd !== null ? ` <strong>${c.qtd}</strong>` : ""}
            </button>
        `).join("")}
    `;
    container.querySelectorAll(".relacao-chip").forEach(btn => {
        btn.addEventListener("click", () => {
            document.getElementById("kanban-filter-relacao").value = btn.dataset.valor;
            filterBoard();
            renderRelacaoResumo();
        });
    });
    container.style.display = "flex";
}

function updateColumnCounts() {
    document.querySelectorAll(".kanban-column").forEach(col => {
        const body = col.querySelector(".column-body");
        const countBadge = col.querySelector(".column-count");
        if (!body || !countBadge) return;
        const visibleCards = body.querySelectorAll(".project-card:not([style*='display: none'])").length;
        countBadge.textContent = visibleCards;
    });
}

// ─── Event Listeners ─────────────────────────────────────────────────────────

function setupEventListeners() {
    // New project
    document.getElementById("btn-novo-projeto")?.addEventListener("click", openNewProject);
    document.getElementById("btn-salvar-projeto")?.addEventListener("click", saveProject);

    // New phase
    document.getElementById("btn-nova-fase")?.addEventListener("click", openNewPhase);
    document.getElementById("btn-salvar-fase")?.addEventListener("click", savePhase);

    // Assign employee
    document.getElementById("btn-confirmar-atribuir")?.addEventListener("click", confirmAssign);

    // Close modals on overlay click
    document.querySelectorAll(".modal-overlay").forEach(overlay => {
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) fecharModal(overlay.id);
        });
    });
}

// ─── New Project Modal ───────────────────────────────────────────────────────


let moduloCount = 0;

function adicionarModuloUI(dadosModulo = null) {
    if (moduloCount >= 6) {
        showToast("Limite de 6 módulos atingido.", "error");
        return;
    }
    
    moduloCount++;
    const container = document.getElementById("modulos-list");
    
    const responsavelOptions = allFuncionarios.map(f => `<option value="${f.id}" ${dadosModulo && dadosModulo.responsavel_id === f.id ? 'selected' : ''}>${f.nome}</option>`).join("");
    const faseOptions = allFases.map(f => `<option value="${f.id}" ${dadosModulo && dadosModulo.fase_atual_id === f.id ? 'selected' : ''}>${f.nome}</option>`).join("");
    
    // Preparar UI do fluxo de fases se estiver editando
    let fluxoHtml = "";
    if (dadosModulo && dadosModulo.etapas_pre_definidas && Array.isArray(dadosModulo.etapas_pre_definidas)) {
        dadosModulo.etapas_pre_definidas.forEach(etapa => {
            const faseId = etapa.fase_id || etapa;
            const dataLim = etapa.data_limite || "";
            const dataIni = etapa.data_inicio || "";
            const funcId = etapa.funcionario_id || "";
            if (!faseId) return;
            const selOpts = allFases.map(f => `<option value="${f.id}" ${f.id == faseId ? 'selected' : ''}>${f.nome}</option>`).join("");
            const funcOpts = allFuncionarios.map(f => `<option value="${f.id}" ${f.id == funcId ? 'selected' : ''}>${f.nome}</option>`).join("");
            fluxoHtml += `
                <div class="fluxo-step-item" style="display:flex; gap:6px; align-items:center; margin-bottom:6px; padding:8px; background:#fff; border:1px solid #e2e8f0; border-radius:6px; flex-wrap:wrap;">
                    <select class="input-select mod-etapa-step-fase" style="flex:2; min-width:120px;" onchange="onFluxoFaseChange(this)"><option value="">-- Fase --</option>${selOpts}</select>
                    <input type="date" class="mod-etapa-step-inicio" style="flex:1; min-width:120px; padding:6px 8px; border:1px solid #cbd5e1; border-radius:4px; font-size:13px;" value="${dataIni}" title="Início previsto" aria-label="Início previsto">
                    <input type="date" class="mod-etapa-step-data" style="flex:1; min-width:120px; padding:6px 8px; border:1px solid #cbd5e1; border-radius:4px; font-size:13px;" value="${dataLim}" title="Prazo previsto" aria-label="Prazo previsto">
                    <select class="input-select mod-etapa-step-func" style="flex:2; min-width:120px;"><option value="">-- Funcionário (opcional) --</option>${funcOpts}</select>
                    <button type="button" class="btn btn-ghost btn-sm" onclick="removeFluxoStep(this)" style="color:#ef4444; padding:4px 8px; min-width:auto;">✕</button>
                </div>`;
        });
    }

    const modHtml = `
        <div class="modulo-item" id="modulo-${moduloCount}" style="border: 1px solid #e2e8f0; padding: 12px; margin-bottom: 12px; border-radius: 6px; background: #f8fafc;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <strong>Módulo ${moduloCount}</strong>
                ${moduloCount > 1 ? `<button type="button" class="btn btn-ghost btn-sm" onclick="removerModuloUI('modulo-${moduloCount}')" style="color: red;">Remover</button>` : ''}
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>Nome do Módulo *</label>
                    <input type="text" class="mod-nome" required value="${dadosModulo ? dadosModulo.nome : 'Módulo ' + moduloCount}">
                </div>
                <div class="form-group">
                    <label>Fase Inicial</label>
                    <select class="mod-fase">
                        <option value="">Sem fase</option>
                        ${faseOptions}
                    </select>
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>Início Previsto do Módulo</label>
                    <input type="date" class="mod-data-inicio" value="${dadosModulo && dadosModulo.data_inicio ? dadosModulo.data_inicio : ''}">
                </div>
                <div class="form-group">
                    <label>Data Limite do Módulo</label>
                    <input type="date" class="mod-data" value="${dadosModulo && dadosModulo.data_limite ? dadosModulo.data_limite.split('T')[0] : ''}">
                </div>
            </div>
            <p class="rm-ajuda" style="margin-top:-4px;">O início previsto é só uma referência: o card só avança de fase quando a fase atual é concluída.</p>

            <div class="form-row">
                <div class="form-group">
                    <label>Responsável</label>
                    <select class="mod-responsavel">
                        <option value="">(Mesmo da OS se vazio)</option>
                        ${responsavelOptions}
                    </select>
                </div>
            </div>
            
            <div class="form-group" style="grid-column: 1 / -1;">
                <label>Fluxo de Fases Pré-Definidas <span style="font-weight:normal; color:#94a3b8;">(Opcional, em ordem: fase · início previsto · prazo previsto · funcionário)</span></label>
                <div class="mod-fluxo-container" style="margin-bottom:8px;">
                    ${fluxoHtml}
                </div>
                <button type="button" class="btn btn-ghost btn-sm" onclick="addFluxoStep(this)">+ Adicionar Passo do Fluxo</button>
            </div>
            
            <div class="form-group">
                <label>Descrição do Módulo</label>
                <textarea class="mod-descricao" rows="1">${dadosModulo ? dadosModulo.descricao : ''}</textarea>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', modHtml);
}

window.addFluxoStep = function(btn) {
    const container = btn.previousElementSibling;
    const faseOptions = allFases.map(f => `<option value="${f.id}">${f.nome}</option>`).join("");
    const funcOptions = allFuncionarios.map(f => `<option value="${f.id}">${f.nome}</option>`).join("");
    const stepHtml = `
        <div class="fluxo-step-item" style="display:flex; gap:6px; align-items:center; margin-bottom:6px; padding:8px; background:#fff; border:1px solid #e2e8f0; border-radius:6px; flex-wrap:wrap;">
            <select class="input-select mod-etapa-step-fase" style="flex:2; min-width:120px;" onchange="onFluxoFaseChange(this)"><option value="">-- Fase --</option>${faseOptions}</select>
            <input type="date" class="mod-etapa-step-inicio" style="flex:1; min-width:120px; padding:6px 8px; border:1px solid #cbd5e1; border-radius:4px; font-size:13px;" title="Início previsto" aria-label="Início previsto">
            <input type="date" class="mod-etapa-step-data" style="flex:1; min-width:120px; padding:6px 8px; border:1px solid #cbd5e1; border-radius:4px; font-size:13px;" title="Prazo previsto" aria-label="Prazo previsto">
            <select class="input-select mod-etapa-step-func" style="flex:2; min-width:120px;"><option value="">-- Funcionário (opcional) --</option>${funcOptions}</select>
            <button type="button" class="btn btn-ghost btn-sm" onclick="removeFluxoStep(this)" style="color:#ef4444; padding:4px 8px; min-width:auto;">✕</button>
        </div>`;
    container.insertAdjacentHTML('beforeend', stepHtml);
}

window.removeFluxoStep = function(btn) {
    btn.closest(".fluxo-step-item").remove();
}

window.onFluxoFaseChange = async function(selectEl) {
    const faseId = selectEl.value;
    const stepItem = selectEl.closest(".fluxo-step-item");
    const funcSelect = stepItem.querySelector(".mod-etapa-step-func");
    
    if (!faseId) {
        // Reset func select with all employees
        const allOpts = allFuncionarios.map(f => `<option value="${f.id}">${f.nome}</option>`).join("");
        funcSelect.innerHTML = `<option value="">-- Funcionário (opcional) --</option>${allOpts}`;
        return;
    }
    
    // Fetch eligible employees for this phase
    try {
        const res = await fetch(`/api/fases/${faseId}/funcionarios-elegiveis`);
        if (res.ok) {
            const elegíveis = await res.json();
            const opts = elegíveis.map(f => `<option value="${f.id}">${f.nome}</option>`).join("");
            funcSelect.innerHTML = `<option value="">-- Funcionário (opcional) --</option>${opts}`;
        }
    } catch (e) {
        console.error("Erro ao buscar funcionários elegíveis:", e);
    }
}

function removerModuloUI(id) {
    document.getElementById(id).remove();
    moduloCount--;
}

async function openNewProject() {
    await loadSelectData();
    document.getElementById("modal-projeto-titulo").textContent = "Novo Projeto (OS)";
    document.getElementById("proj-id").value = "";
    document.getElementById("proj-os").value = "";
    document.getElementById("proj-nome").value = "";
    document.getElementById("proj-cliente").value = "";
    document.getElementById("proj-solicitante").value = "";
    document.getElementById("proj-data-limite").value = "";
    document.getElementById("proj-descricao").value = "";
    document.getElementById("proj-comentario").value = "";

    // Populate selects
    const respSelect = document.getElementById("proj-responsavel");
    respSelect.innerHTML = '<option value="">Selecionar...</option>';
    allFuncionarios.forEach(f => {
        respSelect.innerHTML += `<option value="${f.id}">${f.nome}</option>`;
    });

    // Reset modules
    document.getElementById("modulos-list").innerHTML = "";
    moduloCount = 0;
    adicionarModuloUI(); // Adiciona 1 módulo por padrão
    document.getElementById("modulos-container").style.display = "block";

    abrirModal("modal-projeto");
}

async function saveProject() {
    const id = document.getElementById("proj-id").value;
    
    // Obter dados da OS
    const data = {
        os: document.getElementById("proj-os").value,
        nome: document.getElementById("proj-nome").value,
        cliente: document.getElementById("proj-cliente").value,
        solicitante: document.getElementById("proj-solicitante").value,
        data_limite: document.getElementById("proj-data-limite").value,
        descricao: document.getElementById("proj-descricao").value,
        comentario: document.getElementById("proj-comentario").value,
        responsavel_id: document.getElementById("proj-responsavel").value ? parseInt(document.getElementById("proj-responsavel").value) : null,
        objetos: []
    };

    if (!id) {
        // Obter dados dos módulos (apenas na criação)
        const moduloElements = document.querySelectorAll(".modulo-item");
        moduloElements.forEach(mod => {
            const modNome = mod.querySelector(".mod-nome").value;
            const modFase = mod.querySelector(".mod-fase").value;
            const modData = mod.querySelector(".mod-data").value;
            const modDataInicio = mod.querySelector(".mod-data-inicio").value;
            const modResp = mod.querySelector(".mod-responsavel").value;
            const modDesc = mod.querySelector(".mod-descricao").value;
            const modEtapas = Array.from(mod.querySelectorAll(".fluxo-step-item")).map(step => {
                const faseId = step.querySelector(".mod-etapa-step-fase")?.value;
                if (!faseId) return null;
                return {
                    fase_id: parseInt(faseId),
                    data_inicio: step.querySelector(".mod-etapa-step-inicio")?.value || null,
                    data_limite: step.querySelector(".mod-etapa-step-data")?.value || null,
                    funcionario_id: step.querySelector(".mod-etapa-step-func")?.value ? parseInt(step.querySelector(".mod-etapa-step-func").value) : null
                };
            }).filter(v => v !== null);
            
            data.objetos.push({
                nome: modNome,
                fase_id: modFase ? parseInt(modFase) : null,
                data_inicio: modDataInicio || null,
                data_limite: modData || null,
                responsavel_id: modResp ? parseInt(modResp) : null,
                descricao: modDesc,
                etapas_pre_definidas: modEtapas.length > 0 ? modEtapas : null
            });
        });
        
        if (data.objetos.length === 0) {
            showToast("Adicione pelo menos 1 módulo.", "error");
            return;
        }
    }

    const url = id ? `/api/projetos/${id}` : "/api/projetos";
    const method = id ? "PUT" : "POST";

    const res = await fetch(url, {
        method, headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });

    if (res.ok) {
        fecharModal("modal-projeto", true);
        showToast(id ? "OS atualizada!" : "OS criada com sucesso!", "success");
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao salvar", "error");
    }
}
async function openNewPhase() {
    await loadSelectData();
    document.getElementById("fase-nome").value = "";
    document.getElementById("fase-cor").value = "#6366f1";
    document.getElementById("fase-descricao").value = "";

    const list = document.getElementById("fase-funcoes-list");
    list.innerHTML = "";
    allFuncoes.forEach(f => {
        list.innerHTML += `<label><input type="checkbox" value="${f.id}"> ${f.nome}</label>`;
    });

    abrirModal("modal-fase");
}

async function savePhase() {
    const funcaoIds = [...document.querySelectorAll("#fase-funcoes-list input:checked")].map(cb => parseInt(cb.value));

    const data = {
        nome: document.getElementById("fase-nome").value,
        cor: document.getElementById("fase-cor").value,
        descricao: document.getElementById("fase-descricao").value,
        funcao_ids: funcaoIds,
    };

    const res = await fetch("/api/fases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });

    if (res.ok) {
        fecharModal("modal-fase");
        showToast("Fase criada!", "success");
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao criar fase", "error");
    }
}

async function openDetail(objetoId) {
    const projetoId = objetoId;
    await loadSelectData();
    const res = await fetch(`/api/objetos/${objetoId}`);
    if (!res.ok) return;
    const p = await res.json();

    document.getElementById("detalhe-titulo").textContent = `${p.projeto_os} - ${p.projeto_nome || ""}`;
    document.getElementById("detalhe-subtitulo").textContent = `Módulo: ${p.nome}`;

    const sla = p.sla || {};
    const slaClass = sla.flag === "Dentro do SLA" ? "dentro" : "fora";
    const slaIcon = sla.flag === "Dentro do SLA" ? "🟢" : "🔴";
    const slaDias = sla.dias_restantes != null
        ? (sla.dias_restantes >= 0 ? `${sla.dias_restantes} dia(s) restante(s)` : `${Math.abs(sla.dias_restantes)} dia(s) de atraso`)
        : "";

    let html = `
        <div class="sla-indicator ${slaClass}">
            <span class="sla-icon">${slaIcon}</span>
            <div>
                <div class="sla-text">${sla.flag || "—"}</div>
                <div class="sla-sub">${slaDias} · ⏱️ ${sla.dias_na_fase || 0} dia(s) na fase atual</div>
            </div>
        </div>
    `;

    // ── Prioridade na fila de cada funcionário da fase atual ──
    const prios = p.prioridades_fase_atual || [];
    if (prios.length > 0) {
        const isAdmin = currentUser?.perfil === "admin";
        html += `
            <div class="prio-detalhe">
                <div class="prio-detalhe-header">
                    <span class="detail-label" style="margin:0;">Prioridade na fila de cada funcionário</span>
                    ${["admin", "gestor"].includes(currentUser?.perfil) ? `<a href="/prioridades" class="btn btn-ghost btn-sm">Ver todas as filas</a>` : ""}
                </div>
                ${prios.map(pr => {
                    let controle;
                    if (pr.aprovado) {
                        controle = `<span class="prio-detalhe-info">✅ Já aprovou — fora da fila</span>`;
                    } else if (isAdmin && pr.prioridade != null) {
                        const opts = Array.from({ length: pr.total }, (_, i) => i + 1)
                            .map(n => `<option value="${n}" ${n === pr.prioridade ? "selected" : ""}>${n}${n === 1 ? " (mais importante)" : ""}</option>`)
                            .join("");
                        controle = `
                            <select class="input-select prio-detalhe-select" aria-label="Prioridade na fila de ${pr.nome}"
                                    onchange="mudarPrioridadeFuncionario(${pr.funcionario_id}, ${p.fase_ativa_id}, this.value, ${p.id})">${opts}</select>
                            <span class="prio-detalhe-info">de ${pr.total}</span>`;
                    } else {
                        controle = pr.prioridade != null
                            ? `<span class="prio-badge ${classePrioridade(pr.prioridade)}">#${pr.prioridade}</span><span class="prio-detalhe-info">de ${pr.total}</span>`
                            : `<span class="prio-detalhe-info">—</span>`;
                    }
                    return `<div class="prio-detalhe-linha"><span class="prio-detalhe-nome">👤 ${pr.nome}</span>${controle}</div>`;
                }).join("")}
            </div>
        `;
    }

    // ── Mover fase inline (para admin/gestor) ──
    if (["admin", "gestor"].includes(currentUser?.perfil)) {
        const faseOptions = allFases.map(f => {
            const sel = f.id === p.fase_atual_id ? "selected" : "";
            return `<option value="${f.id}" ${sel}>${f.nome}</option>`;
        }).join("");
        html += `
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:20px;padding:12px 16px;background:var(--bg-primary);border:1px solid var(--border);border-radius:var(--radius);">
                <span class="detail-label" style="margin:0;white-space:nowrap;">Fase Atual:</span>
                <select id="detalhe-mover-fase" class="input-select" style="flex:1;">
                    <option value="">Sem fase</option>
                    ${faseOptions}
                </select>
                <button class="btn btn-primary btn-sm" id="btn-detalhe-mover" onclick="moverFaseInline(${p.id})">Mover</button>
            </div>
        `;
    }

    html += `
        <div class="detail-grid">
            <div class="detail-item"><span class="detail-label">OS</span><span class="detail-value">${p.projeto_os}</span></div>
            <div class="detail-item"><span class="detail-label">Cliente</span><span class="detail-value">${p.cliente || "—"}</span></div>
            <div class="detail-item"><span class="detail-label">Solicitante</span><span class="detail-value">${p.solicitante || "—"}</span></div>
            <div class="detail-item"><span class="detail-label">Atividade</span><span class="detail-value">${p.atividade || "—"}</span></div>
            <div class="detail-item"><span class="detail-label">Data Inclusão</span><span class="detail-value">${formatDate(p.data_inclusao)}</span></div>
            <div class="detail-item"><span class="detail-label">Início Previsto</span><span class="detail-value">${formatDate(p.data_inicio)}</span></div>
            <div class="detail-item"><span class="detail-label">Data Limite</span><span class="detail-value">${formatDate(p.data_limite)}</span></div>
            <div class="detail-item"><span class="detail-label">Responsável</span><span class="detail-value">${p.responsavel_nome || "—"}</span></div>
            <div class="detail-item"><span class="detail-label">Fase Atual</span><span class="detail-value">${p.fase_atual_nome || "Sem fase"}</span></div>
        </div>
        ${p.projeto_descricao ? `<div class="detail-item" style="margin-bottom:16px;"><span class="detail-label">Descrição (OS)</span><span class="detail-value" style="white-space: pre-wrap;">${p.projeto_descricao}</span></div>` : ""}
        ${p.descricao ? `<div class="detail-item" style="margin-bottom:16px;"><span class="detail-label">Descrição (Módulo)</span><span class="detail-value" style="white-space: pre-wrap;">${p.descricao}</span></div>` : ""}
        ${p.projeto_comentario ? `<div class="detail-item" style="margin-bottom:16px;"><span class="detail-label">Comentário MACRO</span><span class="detail-value" style="white-space: pre-wrap;">${p.projeto_comentario}</span></div>` : ""}
    `;

    // ── Roadmap Pré-Definido (somente leitura; edição no editor de roadmap e módulos) ──
    const etapas = p.etapas_pre_definidas || [];
    const canEditRoadmap = ["admin", "gestor"].includes(currentUser?.perfil);
    if (etapas.length > 0 || canEditRoadmap) {
        html += `
            <div class="detail-section-header">
                <div class="detail-section-title" style="margin:0;">Roadmap Pré-Definido</div>
                ${canEditRoadmap ? `<button class="btn btn-ghost btn-sm" onclick="abrirEditorRoadmap(${p.id})">🗺️ Editar roadmap e módulos da OS</button>` : ""}
            </div>
        `;
    }
    if (etapas.length > 0) {
        // Índice calculado no backend (considera o histórico quando a fase se repete)
        const currentIdx = p.indice_fase_atual ?? -1;
        html += `<div style="display:flex; flex-direction:column; gap:6px; margin-bottom:20px;">`;
        etapas.forEach((etapa, idx) => {
            const faseObj = allFases.find(f => f.id === etapa.fase_id);
            const faseNome = faseObj ? faseObj.nome : `Fase #${etapa.fase_id}`;
            const faseCor = faseObj ? faseObj.cor : "#94a3b8";
            const isCurrent = (idx === currentIdx);
            const isDone = currentIdx !== -1 && idx < currentIdx;
            const funcNome = etapa.funcionario_id
                ? (allFuncionarios.find(f => f.id === etapa.funcionario_id)?.nome || "—")
                : "—";
            const dataLim = etapa.data_limite ? formatDate(etapa.data_limite) : "—";
            const dataIni = etapa.data_inicio ? formatDate(etapa.data_inicio) : "—";
            html += `
                <div style="display:flex; align-items:center; gap:10px; padding:10px 14px; background:${isCurrent ? 'rgba(99,102,241,0.08)' : 'var(--bg-primary)'}; border:1px ${isCurrent || isDone ? 'solid' : 'dashed'} ${isCurrent ? faseCor : 'var(--border)'}; border-radius:var(--radius); ${isCurrent ? 'box-shadow: 0 0 0 2px ' + faseCor + '33;' : ''} ${isDone ? 'opacity:0.7;' : ''}">
                    <span style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:${faseCor};color:#fff;font-size:12px;font-weight:700;flex-shrink:0;">${isDone ? '✓' : idx + 1}</span>
                    <div style="flex:1;min-width:0;">
                        <div style="font-weight:600;font-size:14px;color:${faseCor};">${faseNome} ${isCurrent ? '<span style="font-size:11px;background:' + faseCor + ';color:#fff;padding:1px 6px;border-radius:10px;margin-left:6px;">ATUAL</span>' : ''}</div>
                    </div>
                    <div style="display:flex;gap:16px;font-size:13px;color:var(--text-secondary);flex-shrink:0;flex-wrap:wrap;">
                        <span title="Início previsto">▶ ${dataIni}</span>
                        <span title="Prazo previsto">📅 ${dataLim}</span>
                        <span title="Funcionário pré-definido">👤 ${funcNome}</span>
                    </div>
                </div>
            `;
        });
        html += `</div>`;
    } else if (canEditRoadmap) {
        html += `<p class="rm-ajuda" style="margin-bottom:20px;">Este módulo ainda não tem roadmap.</p>`;
    }


    if (p.historico && p.historico.length > 0) {
        html += `<div class="detail-section-title">Histórico de Fases</div><div class="timeline">`;
        p.historico.forEach(h => {
            const isActive = !h.data_saida;
            html += `
                <div class="timeline-item ${isActive ? 'active' : ''}">
                    <div class="timeline-fase" style="color: ${h.fase_cor};">${h.fase_nome}</div>
                    <div class="timeline-meta">
                        Entrada: ${formatDateTime(h.data_entrada)}
                        ${h.data_saida ? ` · Saída: ${formatDateTime(h.data_saida)}` : " · <strong>Ativa</strong>"}
                        · ${h.dias_na_fase} dia(s)
                    </div>
                    ${h.responsavel_fase_nome ? `
                        <div style="margin-top:6px;font-size:13px;color:var(--text-secondary);">
                            <span class="detail-label" style="font-size:12px;">Responsável:</span> ${h.responsavel_fase_nome}
                        </div>
                    ` : ""}
                    ${h.funcionarios.length > 0 ? `
                        <div style="margin-top:8px;">
                            <span class="detail-label">Equipe:</span>
                            ${isActive && h.aprovacao && h.aprovacao.total > 1 ? `<span style="font-size:12px;margin-left:8px;padding:2px 8px;border-radius:10px;background:${h.aprovacao.todos_aprovaram ? '#22c55e' : '#f59e0b'}15;color:${h.aprovacao.todos_aprovaram ? '#22c55e' : '#f59e0b'};font-weight:600;">🔒 ${h.aprovacao.aprovados}/${h.aprovacao.total} aprovados</span>` : ""}
                            <div class="team-chips" style="margin-top:4px;">
                                ${h.funcionarios.map(f => {
                                    const aprovIcon = f.aprovado_em ? '✅' : '⏳';
                                    const aprovTitle = f.aprovado_em ? `Aprovado em ${formatDateTime(f.aprovado_em)}` : 'Aprovação pendente';
                                    if (isActive && ["admin", "gestor"].includes(currentUser?.perfil)) {
                                        return `<span class="team-chip" style="display:inline-flex;align-items:center;gap:4px;" title="${aprovTitle}">${aprovIcon} ${f.nome} <button onclick="removerFuncionarioFaseAtiva(event, ${h.id}, ${f.id})" style="background:none;border:none;color:#ef4444;cursor:pointer;font-size:14px;padding:0 2px;line-height:1;" title="Remover">✕</button></span>`;
                                    }
                                    return `<span class="team-chip" title="${aprovTitle}">${aprovIcon} ${f.nome}</span>`;
                                }).join("")}
                            </div>
                        </div>
                    ` : ""}
                    ${isActive && ["admin", "gestor"].includes(currentUser?.perfil) ? `
                        <div class="card-actions" style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">
                            <button class="btn btn-ghost btn-sm" onclick="openAssign(${h.id}, ${p.fase_atual_id})">+ Atribuir Funcionário</button>
                            <button class="btn btn-ghost btn-sm" onclick="openReatribuir(${p.id}, ${p.fase_atual_id})" style="color:#6366f1;">🔄 Reatribuir Responsável</button>
                        </div>
                    ` : ""}
                </div>
            `;
        });
        html += `</div>`;
    }

    // ── Comentários ──
    html += `
        <div class="detail-section-title">Comentários</div>
        <div style="display:flex;gap:10px;margin-bottom:16px;">
            <textarea id="novo-comentario" rows="2" placeholder="Escreva um comentário..." style="flex:1;"></textarea>
            <button class="btn btn-primary" onclick="enviarComentario(${p.id})" style="align-self:flex-end;">Enviar</button>
        </div>
        <div id="lista-comentarios">
    `;

    const comentarios = p.comentarios || [];
    if (comentarios.length === 0) {
        html += `<div class="empty-state" style="padding:16px;"><div class="empty-state-icon">💬</div>Nenhum comentário ainda</div>`;
    } else {
        comentarios.forEach(c => {
            html += `
                <div class="comment-item">
                    <div class="comment-header">
                        <span class="comment-author">${c.autor_nome}</span>
                        <span class="comment-date">${formatDateTime(c.criado_em)}</span>
                    </div>
                    <div class="comment-text">${c.texto}</div>
                </div>
            `;
        });
    }
    html += `</div>`;

    // ── Botões de ação ──
    if (["admin", "gestor"].includes(currentUser?.perfil)) {
        html += `
            <div style="display:flex;gap:10px;margin-top:24px;">
                <button class="btn btn-ghost" onclick="openEditProject(${p.projeto_id})">Editar</button>
                ${currentUser.perfil === "admin" ? `<button class="btn btn-danger btn-sm" onclick="deleteObject(${p.id})">Excluir</button>` : ""}
            </div>
        `;
    }

    document.getElementById("detalhe-body").innerHTML = html;
    abrirModal("modal-detalhe");
}

// ─── Alterar Prioridade (posição do card na fila de um funcionário) ──────────

async function mudarPrioridadeFuncionario(funcionarioId, objetoFaseId, posicao, objetoId) {
    const res = await fetch(`/api/prioridades/${funcionarioId}/mover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ objeto_fase_id: objetoFaseId, posicao: parseInt(posicao) })
    });
    if (res.ok) {
        showToast("Prioridade atualizada!", "success");
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao atualizar prioridade", "error");
    }
    await loadBoard();
    openDetail(objetoId);
}

// ─── Mover fase pelo detalhe ─────────────────────────────────────────────────

async function moverFaseInline(projetoId) {
    const select = document.getElementById("detalhe-mover-fase");
    const faseId = select.value;
    if (!faseId) { showToast("Selecione uma fase", "error"); return; }

    pendingMove = { projetoId: projetoId, faseId: parseInt(faseId), isInline: true };
    document.getElementById("mover-data-limite").value = "";
    abrirModal("modal-mover-fase");
}

// ─── Comentários ─────────────────────────────────────────────────────────────

async function enviarComentario(objetoId) {
    const textarea = document.getElementById("novo-comentario");
    const texto = textarea.value.trim();
    if (!texto) { showToast("Escreva um comentário", "error"); return; }

    const res = await fetch(`/api/objetos/${objetoId}/comentarios`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
    });

    if (res.ok) {
        showToast("Comentário adicionado!", "success");
        // Reabrir o detalhe para mostrar o novo comentário
        openDetail(objetoId);
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao comentar", "error");
    }
}


async function openEditProject(osId) {
    fecharModal("modal-detalhe");
    await loadSelectData();
    const res = await fetch(`/api/projetos/${osId}`);
    if (!res.ok) return;
    const p = await res.json();

    document.getElementById("modal-projeto-titulo").textContent = "Editar OS";
    document.getElementById("proj-id").value = p.id;
    document.getElementById("proj-os").value = p.os;
    document.getElementById("proj-nome").value = p.nome || "";
    document.getElementById("proj-cliente").value = p.cliente;
    document.getElementById("proj-solicitante").value = p.solicitante;
    document.getElementById("proj-data-limite").value = p.data_limite;
    document.getElementById("proj-descricao").value = p.descricao;
    document.getElementById("proj-comentario").value = p.comentario;

    const respSelect = document.getElementById("proj-responsavel");
    respSelect.innerHTML = '<option value="">Selecionar...</option>';
    allFuncionarios.forEach(f => {
        const sel = f.id === p.responsavel_id ? "selected" : "";
        respSelect.innerHTML += `<option value="${f.id}" ${sel}>${f.nome}</option>`;
    });

    // Ocultar criação de módulos no edit
    document.getElementById("modulos-container").style.display = "none";

    abrirModal("modal-projeto");
}

async function deleteObject(id) {
    if (!confirm("Tem certeza que deseja excluir este módulo?")) return;
    const res = await fetch(`/api/objetos/${id}`, { method: "DELETE" });
    if (res.ok) {
        fecharModal("modal-detalhe");
        showToast("Módulo excluído!", "success");
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao excluir", "error");
    }
}
// ─── Assign Employee ─────────────────────────────────────────────────────────

async function openAssign(projetoFaseId, faseId) {
    document.getElementById("atribuir-pf-id").value = projetoFaseId;
    const res = await fetch(`/api/fases/${faseId}/funcionarios-elegiveis`);
    if (!res.ok) return;
    const funcionarios = await res.json();

    const select = document.getElementById("atribuir-funcionario");
    select.innerHTML = '<option value="">Selecionar...</option>';
    funcionarios.forEach(f => {
        const funcoes = f.funcoes ? f.funcoes.map(fn => fn.nome).join(", ") : "";
        select.innerHTML += `<option value="${f.id}">${f.nome} (${funcoes})</option>`;
    });

    abrirModal("modal-atribuir");
}

async function confirmAssign() {
    const pfId = document.getElementById("atribuir-pf-id").value;
    const funcId = document.getElementById("atribuir-funcionario").value;
    if (!funcId) { showToast("Selecione um funcionário", "error"); return; }

    const res = await fetch(`/api/objeto-fase/${pfId}/atribuir`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ funcionario_id: parseInt(funcId) }),
    });

    if (res.ok) {
        fecharModal("modal-atribuir");
        fecharModal("modal-detalhe");
        showToast("Funcionário atribuído!", "success");
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao atribuir", "error");
    }
}

// ─── Reatribuir Responsável da Fase Ativa ────────────────────────────────────

async function openReatribuir(objetoId, faseId) {
    document.getElementById("reatribuir-objeto-id").value = objetoId;
    const res = await fetch(`/api/fases/${faseId}/funcionarios-elegiveis`);
    if (!res.ok) return;
    const funcionarios = await res.json();

    const select = document.getElementById("reatribuir-funcionario");
    select.innerHTML = '<option value="">Selecionar...</option>';
    funcionarios.forEach(f => {
        const funcoes = f.funcoes ? f.funcoes.map(fn => fn.nome).join(", ") : "";
        select.innerHTML += `<option value="${f.id}">${f.nome} (${funcoes})</option>`;
    });

    abrirModal("modal-reatribuir");
}

document.getElementById("btn-confirmar-reatribuir")?.addEventListener("click", async () => {
    const objetoId = document.getElementById("reatribuir-objeto-id").value;
    const funcId = document.getElementById("reatribuir-funcionario").value;
    if (!funcId) { showToast("Selecione um funcionário", "error"); return; }

    const res = await fetch(`/api/objetos/${objetoId}/reatribuir-fase`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ novo_responsavel_id: parseInt(funcId) }),
    });

    if (res.ok) {
        fecharModal("modal-reatribuir");
        fecharModal("modal-detalhe");
        showToast("Responsável reatribuído com sucesso!", "success");
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao reatribuir", "error");
    }
});

// ─── Remover Funcionário da Fase Ativa ───────────────────────────────────────

async function removerFuncionarioFaseAtiva(event, objetoFaseId, funcionarioId) {
    event.stopPropagation();
    if (!confirm("Remover este funcionário da equipe da fase ativa?")) return;

    const res = await fetch(`/api/objeto-fase/${objetoFaseId}/remover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ funcionario_id: funcionarioId }),
    });

    if (res.ok) {
        showToast("Funcionário removido da fase!", "success");
        // Re-fetch object detail to get the parent objeto_id
        fecharModal("modal-detalhe");
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao remover funcionário", "error");
    }
}

// ─── Editor de Roadmap e Módulos da OS ───────────────────────────────────────
//
// Abre por cima do detalhe do card. Lista os módulos da OS à esquerda e, à
// direita, o roadmap do módulo selecionado: etapas cumpridas e a atual ficam
// travadas (o backend também valida); as futuras podem ser editadas,
// reordenadas, removidas e acrescentadas. Também permite criar e remover módulos.

const MAX_MODULOS_OS = 6;
const rm = {
    projeto: null,        // OS com objetos (GET /api/projetos/:id)
    selecionado: null,    // id do módulo ou "novo"
    etapas: [],           // cópia editável do roadmap do módulo selecionado
    novo: {},             // campos do formulário de novo módulo (sobrevivem ao re-render)
    dirty: false,
    objetoOrigem: null,   // card a partir do qual o editor foi aberto
};
const elegiveisCache = {};

function escHtml(valor) {
    return String(valor ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

async function funcionariosElegiveis(faseId) {
    if (!faseId) return allFuncionarios;
    if (!elegiveisCache[faseId]) {
        const res = await fetch(`/api/fases/${faseId}/funcionarios-elegiveis`);
        elegiveisCache[faseId] = res.ok ? await res.json() : allFuncionarios;
    }
    return elegiveisCache[faseId];
}

async function abrirEditorRoadmap(objetoId) {
    await loadSelectData();
    const res = await fetch(`/api/objetos/${objetoId}`);
    if (!res.ok) { showToast("Erro ao carregar o módulo", "error"); return; }
    const objeto = await res.json();
    rm.objetoOrigem = objetoId;
    rm.dirty = false;
    if (!(await carregarProjetoRoadmap(objeto.projeto_id))) return;
    abrirModal("modal-roadmap");
    await selecionarModuloRoadmap(objetoId, true);
}

async function carregarProjetoRoadmap(projetoId) {
    const res = await fetch(`/api/projetos/${projetoId}`);
    if (!res.ok) { showToast("Erro ao carregar a OS", "error"); return false; }
    rm.projeto = await res.json();
    document.getElementById("rm-titulo").textContent = `Roadmap e módulos — OS ${rm.projeto.os}`;
    document.getElementById("rm-subtitulo").textContent = rm.projeto.nome || "";
    return true;
}

function moduloSelecionado() {
    return (rm.projeto?.objetos || []).find(o => o.id === rm.selecionado) || null;
}

function renderModulosRoadmap() {
    const nav = document.getElementById("rm-modulos");
    const objetos = rm.projeto?.objetos || [];
    const limite = objetos.length >= MAX_MODULOS_OS;
    nav.innerHTML = `
        ${objetos.map(o => `
            <button type="button" class="rm-modulo-btn ${o.id === rm.selecionado ? "ativo" : ""}"
                    onclick="selecionarModuloRoadmap(${o.id})" aria-current="${o.id === rm.selecionado}">
                <span class="rm-modulo-nome">${escHtml(o.nome)}</span>
                <span class="rm-modulo-fase">
                    <span style="color:${o.fase_atual_cor};">●</span> ${escHtml(o.fase_atual_nome || "Sem fase")}
                    · ${(o.etapas_pre_definidas || []).length} etapa(s)
                </span>
            </button>
        `).join("")}
        <button type="button" class="rm-modulo-btn rm-modulo-novo ${rm.selecionado === "novo" ? "ativo" : ""}"
                onclick="selecionarModuloRoadmap('novo')" ${limite ? "disabled" : ""}
                title="${limite ? `Limite de ${MAX_MODULOS_OS} módulos por OS atingido` : "Adicionar um módulo a esta OS"}">
            + Novo módulo ${limite ? `<span class="rm-modulo-fase">Limite de ${MAX_MODULOS_OS} atingido</span>` : ""}
        </button>
    `;
}

async function selecionarModuloRoadmap(id, ignorarAlteracoes = false) {
    if (!ignorarAlteracoes && rm.dirty && id !== rm.selecionado) {
        if (!confirm("Há alterações não salvas neste roadmap. Descartar e trocar de módulo?")) return;
    }
    rm.selecionado = id;
    rm.dirty = false;
    if (id === "novo") {
        rm.etapas = [{ fase_id: null, data_inicio: null, data_limite: null, funcionario_id: null }];
        rm.novo = { nome: "", data_inicio: "", data_limite: "", responsavel_id: "", descricao: "" };
    } else {
        const mod = moduloSelecionado();
        rm.etapas = JSON.parse(JSON.stringify(mod?.etapas_pre_definidas || []));
        rm.datasModulo = { data_inicio: mod?.data_inicio || "", data_limite: mod?.data_limite || "" };
    }
    renderModulosRoadmap();
    await renderPainelRoadmap();
}

function marcarRoadmapAlterado() {
    rm.dirty = true;
    const status = document.getElementById("rm-status");
    if (status) status.style.visibility = "visible";
}

// Índice da última etapa travada (cumprida ou atual). -1 = tudo editável
function indiceTravado() {
    if (rm.selecionado === "novo") return -1;
    return moduloSelecionado()?.indice_fase_atual ?? -1;
}

async function linhaEtapaEditavel(etapa, idx, total, travado) {
    const elegiveis = await funcionariosElegiveis(etapa.fase_id);
    const faseOpts = allFases.map(f =>
        `<option value="${f.id}" ${f.id === etapa.fase_id ? "selected" : ""}>${escHtml(f.nome)}</option>`
    ).join("");
    const funcOpts = elegiveis.map(f =>
        `<option value="${f.id}" ${f.id === etapa.funcionario_id ? "selected" : ""}>${escHtml(f.nome)}</option>`
    ).join("");
    const primeiraEditavel = idx === travado + 1;
    const ehFaseInicial = rm.selecionado === "novo" && idx === 0;
    return `
        <li class="rm-etapa" data-idx="${idx}">
            <span class="rm-etapa-num">${idx + 1}</span>
            <div class="rm-etapa-campos">
                <label class="rm-campo">
                    <span>${ehFaseInicial ? "Fase inicial *" : "Fase *"}</span>
                    <select class="input-select" onchange="alterarEtapaRoadmap(${idx}, 'fase_id', this.value)">
                        <option value="">-- Fase --</option>${faseOpts}
                    </select>
                </label>
                <label class="rm-campo">
                    <span>Funcionário</span>
                    <select class="input-select" onchange="alterarEtapaRoadmap(${idx}, 'funcionario_id', this.value)">
                        <option value="">-- A definir --</option>${funcOpts}
                    </select>
                </label>
                <label class="rm-campo">
                    <span>Início previsto</span>
                    <input type="date" value="${etapa.data_inicio || ""}" onchange="alterarEtapaRoadmap(${idx}, 'data_inicio', this.value)">
                </label>
                <label class="rm-campo">
                    <span>Prazo previsto</span>
                    <input type="date" value="${etapa.data_limite || ""}" onchange="alterarEtapaRoadmap(${idx}, 'data_limite', this.value)">
                </label>
            </div>
            <div class="rm-etapa-acoes">
                <button type="button" class="rm-seta" onclick="moverEtapaRoadmap(${idx}, -1)" ${primeiraEditavel ? "disabled" : ""} aria-label="Mover etapa ${idx + 1} para cima">▲</button>
                <button type="button" class="rm-seta" onclick="moverEtapaRoadmap(${idx}, 1)" ${idx === total - 1 ? "disabled" : ""} aria-label="Mover etapa ${idx + 1} para baixo">▼</button>
                <button type="button" class="rm-seta rm-remover" onclick="removerEtapaRoadmap(${idx})" aria-label="Remover etapa ${idx + 1}">✕</button>
            </div>
        </li>
    `;
}

function linhaEtapaTravada(etapa, idx, atual) {
    const fase = allFases.find(f => f.id === etapa.fase_id);
    const cor = fase?.cor || "#94a3b8";
    const func = allFuncionarios.find(f => f.id === etapa.funcionario_id);
    return `
        <li class="rm-etapa travada ${atual ? "atual" : ""}" style="--fase-cor:${cor};">
            <span class="rm-etapa-num" style="background:${cor};color:#fff;">${atual ? idx + 1 : "✓"}</span>
            <div class="rm-etapa-campos">
                <span class="rm-etapa-fase" style="color:${cor};">${escHtml(fase?.nome || `Fase #${etapa.fase_id}`)}</span>
                <span class="rm-etapa-info" title="Início previsto → prazo previsto">▶ ${etapa.data_inicio ? formatDate(etapa.data_inicio) : "—"} · 📅 ${etapa.data_limite ? formatDate(etapa.data_limite) : "—"}</span>
                <span class="rm-etapa-info">👤 ${escHtml(func?.nome || "—")}</span>
            </div>
            <span class="rm-etapa-tag">${atual ? "Atual" : "Cumprida"} 🔒</span>
        </li>
    `;
}

async function renderPainelRoadmap() {
    const painel = document.getElementById("rm-painel");
    const novo = rm.selecionado === "novo";
    const mod = moduloSelecionado();
    const travado = indiceTravado();
    const isAdmin = currentUser?.perfil === "admin";
    const unico = (rm.projeto?.objetos || []).length <= 1;

    const linhas = [];
    for (let idx = 0; idx < rm.etapas.length; idx++) {
        linhas.push(idx <= travado
            ? linhaEtapaTravada(rm.etapas[idx], idx, idx === travado)
            : await linhaEtapaEditavel(rm.etapas[idx], idx, rm.etapas.length, travado));
    }

    let cabecalho;
    if (novo) {
        const respOpts = allFuncionarios.map(f =>
            `<option value="${f.id}" ${String(f.id) === rm.novo.responsavel_id ? "selected" : ""}>${escHtml(f.nome)}</option>`
        ).join("");
        cabecalho = `
            <div class="rm-painel-header"><h3>Novo módulo</h3></div>
            <div class="form-row">
                <div class="form-group">
                    <label for="rm-novo-nome">Nome do módulo *</label>
                    <input type="text" id="rm-novo-nome" value="${escHtml(rm.novo.nome)}" oninput="rm.novo.nome = this.value; marcarRoadmapAlterado()">
                </div>
                <div class="form-group">
                    <label for="rm-novo-inicio">Início previsto do módulo</label>
                    <input type="date" id="rm-novo-inicio" value="${rm.novo.data_inicio}" onchange="rm.novo.data_inicio = this.value; marcarRoadmapAlterado()">
                </div>
                <div class="form-group">
                    <label for="rm-novo-data">Data limite do módulo</label>
                    <input type="date" id="rm-novo-data" value="${rm.novo.data_limite}" onchange="rm.novo.data_limite = this.value; marcarRoadmapAlterado()">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label for="rm-novo-resp">Responsável</label>
                    <select id="rm-novo-resp" onchange="rm.novo.responsavel_id = this.value"><option value="">(Mesmo da OS se vazio)</option>${respOpts}</select>
                </div>
                <div class="form-group">
                    <label for="rm-novo-desc">Descrição</label>
                    <input type="text" id="rm-novo-desc" value="${escHtml(rm.novo.descricao)}" oninput="rm.novo.descricao = this.value">
                </div>
            </div>
            <p class="rm-ajuda">A primeira etapa é a fase em que o módulo começa.</p>
        `;
    } else {
        const foraDoRoadmap = mod?.fase_atual_id && travado === -1 && rm.etapas.length > 0;
        cabecalho = `
            <div class="rm-painel-header">
                <div>
                    <h3>${escHtml(mod?.nome)}</h3>
                    <div class="rm-sub">
                        Fase atual: <span style="color:${mod?.fase_atual_cor};">●</span> ${escHtml(mod?.fase_atual_nome || "Sem fase")}
                    </div>
                </div>
                ${isAdmin ? `
                    <button type="button" class="btn btn-danger btn-sm" onclick="removerModuloRoadmap(${mod?.id})"
                            ${unico ? "disabled title='Uma OS precisa de ao menos um módulo. Para remover, exclua a OS.'" : ""}>
                        Remover módulo
                    </button>` : ""}
            </div>
            <div class="rm-datas-modulo">
                <label class="rm-campo">
                    <span>Início previsto do módulo</span>
                    <input type="date" value="${rm.datasModulo.data_inicio || ""}" onchange="rm.datasModulo.data_inicio = this.value; marcarRoadmapAlterado()">
                </label>
                <label class="rm-campo">
                    <span>Data limite do módulo *</span>
                    <input type="date" value="${rm.datasModulo.data_limite || ""}" required onchange="rm.datasModulo.data_limite = this.value; marcarRoadmapAlterado()">
                </label>
            </div>
            <p class="rm-ajuda">Etapas cumpridas e a etapa atual ficam travadas 🔒. As próximas podem ser editadas, reordenadas ou removidas.
            Datas de início são previsões: o card só avança quando a fase atual é concluída.</p>
            ${foraDoRoadmap ? `<p class="rm-aviso">A fase atual (${escHtml(mod.fase_atual_nome)}) não faz parte do roadmap: ao concluir, o card irá para a etapa 1.</p>` : ""}
        `;
    }

    painel.innerHTML = `
        ${cabecalho}
        <ol class="rm-etapas">
            ${linhas.join("") || `<li class="rm-vazio">Nenhuma etapa. Adicione a primeira abaixo.</li>`}
        </ol>
        <button type="button" class="btn btn-ghost rm-adicionar" onclick="adicionarEtapaRoadmap()">+ Adicionar etapa</button>
        <div class="rm-painel-rodape">
            <span id="rm-status" class="rm-status" style="visibility:${rm.dirty ? "visible" : "hidden"};">Alterações não salvas</span>
            ${novo ? "" : `<button type="button" class="btn btn-ghost" onclick="descartarRoadmap()">Descartar</button>`}
            <button type="button" class="btn btn-primary" id="rm-salvar" onclick="${novo ? "criarModuloRoadmap()" : "salvarRoadmap()"}">
                ${novo ? "Criar módulo" : "Salvar roadmap"}
            </button>
        </div>
    `;
}

async function alterarEtapaRoadmap(idx, campo, valor) {
    const etapa = rm.etapas[idx];
    if (!etapa) return;
    if (campo === "data_limite" || campo === "data_inicio") {
        etapa[campo] = valor || null;
    } else {
        etapa[campo] = valor ? parseInt(valor) : null;
    }
    marcarRoadmapAlterado();
    if (campo === "fase_id") {
        // Funcionário escolhido pode não ter as funções exigidas pela nova fase
        const elegiveis = await funcionariosElegiveis(etapa.fase_id);
        if (etapa.funcionario_id && !elegiveis.some(f => f.id === etapa.funcionario_id)) {
            const nome = allFuncionarios.find(f => f.id === etapa.funcionario_id)?.nome || "O funcionário";
            etapa.funcionario_id = null;
            showToast(`${nome} não tem as funções exigidas por essa fase e foi removido da etapa ${idx + 1}.`, "error");
        }
        await renderPainelRoadmap();
    }
}

async function moverEtapaRoadmap(idx, direcao) {
    const destino = idx + direcao;
    if (destino <= indiceTravado() || destino >= rm.etapas.length) return;
    [rm.etapas[idx], rm.etapas[destino]] = [rm.etapas[destino], rm.etapas[idx]];
    marcarRoadmapAlterado();
    await renderPainelRoadmap();
}

async function removerEtapaRoadmap(idx) {
    if (idx <= indiceTravado()) return;
    rm.etapas.splice(idx, 1);
    marcarRoadmapAlterado();
    await renderPainelRoadmap();
}

async function adicionarEtapaRoadmap() {
    rm.etapas.push({ fase_id: null, data_inicio: null, data_limite: null, funcionario_id: null });
    marcarRoadmapAlterado();
    await renderPainelRoadmap();
    document.querySelector("#rm-painel .rm-etapa:last-child select")?.focus();
}

async function descartarRoadmap() {
    await selecionarModuloRoadmap(rm.selecionado, true);
}

function validarEtapasRoadmap() {
    const semFase = rm.etapas.findIndex(e => !e.fase_id);
    if (semFase !== -1) {
        showToast(`Selecione a fase da etapa ${semFase + 1}.`, "error");
        return false;
    }
    // Datas ISO (yyyy-mm-dd) podem ser comparadas como texto
    const invertida = rm.etapas.findIndex(e => e.data_inicio && e.data_limite && e.data_inicio > e.data_limite);
    if (invertida !== -1) {
        showToast(`Etapa ${invertida + 1}: o início previsto é depois do prazo previsto.`, "error");
        return false;
    }
    const datas = rm.selecionado === "novo" ? rm.novo : rm.datasModulo;
    if (datas.data_inicio && datas.data_limite && datas.data_inicio > datas.data_limite) {
        showToast("O início previsto do módulo não pode ser depois da data limite.", "error");
        return false;
    }
    return true;
}

async function aposAlterarProjetoRoadmap(selecionar) {
    await carregarProjetoRoadmap(rm.projeto.id);
    await selecionarModuloRoadmap(selecionar, true);
    await loadBoard();
}

async function salvarRoadmap() {
    if (!validarEtapasRoadmap()) return;
    if (!rm.datasModulo.data_limite) { showToast("Informe a data limite do módulo.", "error"); return; }
    const btn = document.getElementById("rm-salvar");
    btn.disabled = true;
    try {
        const res = await fetch(`/api/objetos/${rm.selecionado}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                etapas_pre_definidas: rm.etapas,
                data_inicio: rm.datasModulo.data_inicio || null,
                data_limite: rm.datasModulo.data_limite,
            }),
        });
        if (res.ok) {
            showToast("Roadmap atualizado com sucesso!", "success");
            await aposAlterarProjetoRoadmap(rm.selecionado);
        } else {
            const err = await res.json();
            showToast(err.erro || "Erro ao salvar roadmap", "error");
        }
    } finally {
        btn.disabled = false;
    }
}

async function criarModuloRoadmap() {
    const nome = rm.novo.nome.trim();
    if (!nome) { showToast("Informe o nome do módulo.", "error"); return; }
    if (rm.etapas.length === 0) { showToast("Adicione ao menos a fase inicial.", "error"); return; }
    if (!validarEtapasRoadmap()) return;

    const body = {
        nome,
        descricao: rm.novo.descricao.trim(),
        data_inicio: rm.novo.data_inicio || null,
        data_limite: rm.novo.data_limite || null,
        responsavel_id: rm.novo.responsavel_id ? parseInt(rm.novo.responsavel_id) : null,
        fase_id: rm.etapas[0].fase_id,
        etapas_pre_definidas: rm.etapas,
    };
    const btn = document.getElementById("rm-salvar");
    btn.disabled = true;
    try {
        const res = await fetch(`/api/projetos/${rm.projeto.id}/objetos`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`Módulo "${nome}" criado!`, "success");
            await aposAlterarProjetoRoadmap(data.id);
        } else {
            showToast(data.erro || "Erro ao criar módulo", "error");
        }
    } finally {
        btn.disabled = false;
    }
}

async function removerModuloRoadmap(objetoId) {
    const mod = (rm.projeto?.objetos || []).find(o => o.id === objetoId);
    if (!mod) return;
    if (!confirm(`Remover o módulo "${mod.nome}" da OS ${rm.projeto.os}?\n\nO histórico de fases dele será apagado. Os comentários continuam na OS.`)) return;

    const res = await fetch(`/api/objetos/${objetoId}`, { method: "DELETE" });
    if (!res.ok) {
        const err = await res.json();
        showToast(err.erro || "Erro ao remover módulo", "error");
        return;
    }
    showToast(`Módulo "${mod.nome}" removido.`, "success");
    if (objetoId === rm.objetoOrigem) {
        // O card que abriu o editor não existe mais
        fecharModal("modal-detalhe", true);
        rm.objetoOrigem = null;
    }
    rm.dirty = false;
    await carregarProjetoRoadmap(rm.projeto.id);
    await selecionarModuloRoadmap(rm.projeto.objetos[0]?.id ?? "novo", true);
    await loadBoard();
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function abrirModal(id) { document.getElementById(id).style.display = "flex"; }
function fecharModal(id, force = false) {
    if (id === "modal-projeto" && !force) {
        // Verifica se há algo digitado para evitar prompts desnecessários se estiver vazio
        const os = document.getElementById("proj-os")?.value.trim();
        const nome = document.getElementById("proj-nome")?.value.trim();
        
        if (os || nome) {
            if (!confirm("Quer sair mesmo? Você perderá o escrito até então.")) {
                return;
            }
        }
    }
    
    if (id === "modal-roadmap" && !force) {
        if (rm.dirty && !confirm("Há alterações não salvas no roadmap. Quer sair mesmo?")) return;
        rm.dirty = false;
        fecharModal(id, true);
        // Atualiza o detalhe do card que abriu o editor (se ele ainda existir)
        if (document.getElementById("modal-detalhe").style.display !== "none" && rm.objetoOrigem) {
            openDetail(rm.objetoOrigem);
        }
        return;
    }

    if (id === "modal-detalhe" && !force) {
        const commentBox = document.getElementById("novo-comentario");
        if (commentBox && commentBox.value.trim() !== "") {
            if (!confirm("Você tem um comentário não salvo. Quer sair mesmo?")) {
                return;
            }
        }
    }

    const modal = document.getElementById(id);
    if (modal) {
        modal.style.display = "none";
    }
}

function formatDate(iso) {
    if (!iso) return "—";
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
}

function formatDateTime(iso) {
    if (!iso) return "—";
    const dt = new Date(iso);
    return dt.toLocaleDateString("pt-BR") + " " + dt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function showToast(message, type = "success") {
    let container = document.querySelector(".toast-container");
    if (!container) {
        container = document.createElement("div");
        container.className = "toast-container";
        document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 4000);
}

// ─── Histórico de Atividade ──────────────────────────────────────────────────

document.getElementById("btn-historico")?.addEventListener("click", () => {
    document.getElementById("historico-os-input").value = "";
    document.getElementById("historico-content").style.display = "none";
    document.getElementById("historico-empty").style.display = "flex";
    document.getElementById("historico-not-found").style.display = "none";
    abrirModal("modal-historico");
});

document.getElementById("btn-buscar-historico")?.addEventListener("click", buscarHistorico);
document.getElementById("historico-os-input")?.addEventListener("keypress", (e) => {
    if (e.key === "Enter") buscarHistorico();
});

document.getElementById("toggle-fases-futuras")?.addEventListener("change", (e) => {
    const container = document.getElementById("hist-modulos-container");
    if (e.target.checked) {
        container.classList.remove("hide-futures");
    } else {
        container.classList.add("hide-futures");
    }
});

// Injetar CSS para as fases futuras
const style = document.createElement("style");
style.textContent = `
    .hide-futures .timeline-item-future { display: none !important; }
    .timeline-item-future {
        opacity: 0.6;
        border: 2px dashed var(--item-color);
        background: transparent !important;
    }
    .timeline-item-future .timeline-meta span {
        color: var(--text-muted);
    }
`;
document.head.appendChild(style);

async function buscarHistorico() {
    const osCode = document.getElementById("historico-os-input").value.trim();
    if (!osCode) return;

    const btn = document.getElementById("btn-buscar-historico");
    btn.disabled = true;
    btn.textContent = "Buscando...";

    try {
        const res = await fetch(`/api/historico/${osCode}`);
        if (!res.ok) {
            document.getElementById("historico-content").style.display = "none";
            document.getElementById("historico-empty").style.display = "none";
            document.getElementById("historico-not-found").style.display = "flex";
            return;
        }

        const data = await res.json();
        
        // Header da OS
        document.getElementById("hist-os-titulo").textContent = `OS: ${data.os}`;
        document.getElementById("hist-os-cliente").textContent = data.cliente ? `Cliente: ${data.cliente}` : "";
        
        const container = document.getElementById("hist-modulos-container");
        container.innerHTML = "";

        if (!data.modulos || data.modulos.length === 0) {
            container.innerHTML = `<p style="color: var(--text-muted); text-align: center; padding: 20px;">Nenhum módulo encontrado para esta OS.</p>`;
        } else {
            data.modulos.forEach(mod => {
                let html = `
                    <div style="margin-bottom: 32px;">
                        <h4 style="font-size: 16px; font-weight: 700; margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
                            <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--accent);"></span>
                            Módulo: ${mod.nome}
                        </h4>
                        <div class="timeline">
                `;

                if (mod.eventos.length === 0) {
                    html += `<div class="empty-state" style="padding:16px;"><div class="empty-state-icon">📭</div>Nenhum histórico para este módulo.</div>`;
                } else {
                    mod.eventos.forEach(ev => {
                        if (ev.tipo === "fase") {
                            html += `
                                <div class="timeline-item" style="--item-color: ${ev.fase_cor};">
                                    <div class="timeline-fase"><i class="fa-solid fa-flag"></i> ${ev.fase_nome}</div>
                                    <div class="timeline-meta">
                                        <span><i class="fa-regular fa-clock"></i> Entrada: ${ev.data_str}</span>
                                        <span><i class="fa-solid fa-user-tag"></i> Responsável: ${ev.responsavel}</span>
                                        <span><i class="fa-solid fa-hourglass-half"></i> TMO: ${ev.tmo_dias} dia(s)</span>
                                    </div>
                                </div>
                            `;
                        } else if (ev.tipo === "fase_futura") {
                            const dataLabel = (ev.inicio_str ? `Início previsto: ${ev.inicio_str} · ` : "")
                                + (ev.data_str === "Pendente" ? "Prazo a definir" : `Prazo: ${ev.data_str}`);
                            const respLabel = ev.responsavel === "—" ? "A definir" : ev.responsavel;
                            html += `
                                <div class="timeline-item timeline-item-future" style="--item-color: ${ev.fase_cor};">
                                    <div class="timeline-fase"><i class="fa-solid fa-hourglass-start"></i> ${ev.fase_nome} (Pendente)</div>
                                    <div class="timeline-meta">
                                        <span><i class="fa-regular fa-clock"></i> ${dataLabel}</span>
                                        <span><i class="fa-solid fa-user-tag"></i> ${respLabel}</span>
                                    </div>
                                </div>
                            `;
                        } else if (ev.tipo === "comentario") {
                            html += `
                                <div class="timeline-item" style="--item-color: var(--text-muted);">
                                    <div class="timeline-fase" style="color: var(--text-primary);"><i class="fa-solid fa-comment-dots"></i> Comentário adicionado</div>
                                    <div class="timeline-meta">
                                        <span><i class="fa-regular fa-clock"></i> ${ev.data_str}</span>
                                        <span><i class="fa-solid fa-user"></i> Autor: ${ev.autor}</span>
                                        <div class="timeline-comment-text">${ev.texto}</div>
                                    </div>
                                </div>
                            `;
                        }
                    });
                }

                html += `</div></div>`;
                container.innerHTML += html;
            });
        }

        document.getElementById("historico-empty").style.display = "none";
        document.getElementById("historico-not-found").style.display = "none";
        document.getElementById("historico-content").style.display = "block";

    } catch (e) {
        console.error("Erro ao buscar histórico:", e);
        showToast("Erro ao buscar histórico", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Pesquisar";
    }
}

