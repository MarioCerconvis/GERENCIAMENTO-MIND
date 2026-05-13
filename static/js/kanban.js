/* ═══════════════════════════════════════════════════════════════════════
   KANBAN.JS — Board de Projetos
   ═══════════════════════════════════════════════════════════════════════ */

let currentUser = null;
let boardData = [];
let allFuncoes = [];
let allFuncionarios = [];
let allFases = [];

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
    if (["admin", "gestor"].includes(currentUser.perfil)) {
        document.getElementById("btn-novo-projeto").style.display = "";
        document.getElementById("btn-nova-fase").style.display = "";
        document.getElementById("btn-admin").style.display = "";
    }
}

async function loadBoard() {
    const res = await fetch("/api/kanban");
    if (!res.ok) return;
    boardData = await res.json();
    renderBoard(boardData);
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
                <span class="column-count">${col.projetos.length}</span>
            </div>
            <div class="column-body" data-fase-id="${col.id ?? 'sem_fase'}"></div>
        `;

        // Set header top border color
        column.querySelector(".column-header").style.cssText += `border-top: 3px solid ${headerColor};`;

        const body = column.querySelector(".column-body");

        if (col.projetos.length === 0) {
            body.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📋</div>Nenhum projeto</div>`;
        } else {
            col.projetos.forEach(p => {
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
    card.dataset.projetoId = projeto.id;
    card.draggable = ["admin", "gestor"].includes(currentUser?.perfil);

    const sla = projeto.sla || {};
    const slaClass = sla.flag === "Dentro do SLA" ? "sla-dentro" : "sla-fora";
    const slaIcon = sla.flag === "Dentro do SLA" ? "🟢" : "🔴";
    const slaDias = sla.dias_restantes != null
        ? (sla.dias_restantes >= 0 ? `${sla.dias_restantes}d restantes` : `${Math.abs(sla.dias_restantes)}d atraso`)
        : "";
    const diasFase = sla.dias_na_fase != null ? `⏱️ ${sla.dias_na_fase}d na fase` : "";

    card.innerHTML = `
        <div class="card-os">${projeto.os}</div>
        <div class="card-cliente">${projeto.cliente || "—"}</div>
        ${projeto.atividade ? `<div class="card-atividade">${projeto.atividade}</div>` : ""}
        <div class="card-footer">
            <span class="sla-badge ${slaClass}">${slaIcon} ${slaDias}</span>
            <span class="card-days">${diasFase}</span>
        </div>
        ${projeto.responsavel_nome ? `<div class="card-responsavel">👤 ${projeto.responsavel_nome}</div>` : ""}
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

// ─── Drag & Drop ─────────────────────────────────────────────────────────────

let draggedProjectId = null;

function handleDragStart(e) {
    draggedProjectId = e.target.dataset.projetoId;
    e.target.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
}

function handleDragEnd(e) {
    e.target.classList.remove("dragging");
    document.querySelectorAll(".column-body").forEach(b => b.classList.remove("drag-over"));
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    e.currentTarget.classList.add("drag-over");
}

function handleDragLeave(e) {
    e.currentTarget.classList.remove("drag-over");
}

async function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove("drag-over");
    const faseId = e.currentTarget.dataset.faseId;
    if (!draggedProjectId || faseId === "sem_fase") return;

    const res = await fetch(`/api/projetos/${draggedProjectId}/mover-fase`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fase_id: parseInt(faseId) }),
    });

    if (res.ok) {
        showToast("Projeto movido com sucesso!", "success");
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao mover projeto", "error");
    }
    draggedProjectId = null;
}

// ─── Toolbar ─────────────────────────────────────────────────────────────────

function setupToolbar() {
    // Search
    document.getElementById("kanban-search").addEventListener("input", (e) => {
        filterBoard();
    });
    document.getElementById("kanban-filter-sla").addEventListener("change", () => {
        filterBoard();
    });
}

function filterBoard() {
    const query = document.getElementById("kanban-search").value.toLowerCase();
    const slaFilter = document.getElementById("kanban-filter-sla").value;
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

        card.style.display = (matchQuery && matchSla) ? "" : "none";
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
            if (e.target === overlay) overlay.style.display = "none";
        });
    });
}

// ─── New Project Modal ───────────────────────────────────────────────────────

async function openNewProject() {
    await loadSelectData();
    document.getElementById("modal-projeto-titulo").textContent = "Novo Projeto";
    document.getElementById("proj-id").value = "";
    document.getElementById("proj-os").value = "";
    document.getElementById("proj-cliente").value = "";
    document.getElementById("proj-solicitante").value = "";
    document.getElementById("proj-atividade").value = "";
    document.getElementById("proj-data-limite").value = "";
    document.getElementById("proj-descricao").value = "";
    document.getElementById("proj-comentario").value = "";

    // Populate selects
    const respSelect = document.getElementById("proj-responsavel");
    respSelect.innerHTML = '<option value="">Selecionar...</option>';
    allFuncionarios.forEach(f => {
        respSelect.innerHTML += `<option value="${f.id}">${f.nome}</option>`;
    });

    const faseSelect = document.getElementById("proj-fase");
    faseSelect.innerHTML = '<option value="">Sem fase</option>';
    allFases.forEach(f => {
        faseSelect.innerHTML += `<option value="${f.id}">${f.nome}</option>`;
    });

    abrirModal("modal-projeto");
}

async function saveProject() {
    const id = document.getElementById("proj-id").value;
    const data = {
        os: document.getElementById("proj-os").value,
        cliente: document.getElementById("proj-cliente").value,
        solicitante: document.getElementById("proj-solicitante").value,
        atividade: document.getElementById("proj-atividade").value,
        data_limite: document.getElementById("proj-data-limite").value,
        descricao: document.getElementById("proj-descricao").value,
        comentario: document.getElementById("proj-comentario").value,
        responsavel_id: document.getElementById("proj-responsavel").value || null,
        fase_id: document.getElementById("proj-fase").value || null,
    };

    if (data.responsavel_id) data.responsavel_id = parseInt(data.responsavel_id);
    if (data.fase_id) data.fase_id = parseInt(data.fase_id);

    const url = id ? `/api/projetos/${id}` : "/api/projetos";
    const method = id ? "PUT" : "POST";

    const res = await fetch(url, {
        method, headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });

    if (res.ok) {
        fecharModal("modal-projeto");
        showToast(id ? "Projeto atualizado!" : "Projeto criado!", "success");
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao salvar", "error");
    }
}

// ─── New Phase Modal ─────────────────────────────────────────────────────────

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

async function openDetail(projetoId) {
    await loadSelectData();
    const res = await fetch(`/api/projetos/${projetoId}`);
    if (!res.ok) return;
    const p = await res.json();

    document.getElementById("detalhe-titulo").textContent = `Projeto ${p.os}`;

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
            <div class="detail-item"><span class="detail-label">OS</span><span class="detail-value">${p.os}</span></div>
            <div class="detail-item"><span class="detail-label">Cliente</span><span class="detail-value">${p.cliente || "—"}</span></div>
            <div class="detail-item"><span class="detail-label">Solicitante</span><span class="detail-value">${p.solicitante || "—"}</span></div>
            <div class="detail-item"><span class="detail-label">Atividade</span><span class="detail-value">${p.atividade || "—"}</span></div>
            <div class="detail-item"><span class="detail-label">Data Inclusão</span><span class="detail-value">${formatDate(p.data_inclusao)}</span></div>
            <div class="detail-item"><span class="detail-label">Data Limite</span><span class="detail-value">${formatDate(p.data_limite)}</span></div>
            <div class="detail-item"><span class="detail-label">Responsável</span><span class="detail-value">${p.responsavel_nome || "—"}</span></div>
            <div class="detail-item"><span class="detail-label">Fase Atual</span><span class="detail-value">${p.fase_atual_nome || "Sem fase"}</span></div>
        </div>
        ${p.descricao ? `<div class="detail-item" style="margin-bottom:16px;"><span class="detail-label">Descrição</span><span class="detail-value">${p.descricao}</span></div>` : ""}
    `;

    // ── Histórico de fases ──
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
                    ${h.funcionarios.length > 0 ? `
                        <div style="margin-top:8px;">
                            <span class="detail-label">Equipe:</span>
                            <div class="team-chips" style="margin-top:4px;">
                                ${h.funcionarios.map(f => `<span class="team-chip">${f.nome}</span>`).join("")}
                            </div>
                        </div>
                    ` : ""}
                    ${isActive && ["admin", "gestor"].includes(currentUser?.perfil) ? `
                        <div class="card-actions" style="margin-top:8px;">
                            <button class="btn btn-ghost btn-sm" onclick="openAssign(${h.id}, ${p.fase_atual_id})">+ Atribuir Funcionário</button>
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
                <button class="btn btn-ghost" onclick="openEditProject(${p.id})">Editar</button>
                ${currentUser.perfil === "admin" ? `<button class="btn btn-danger btn-sm" onclick="deleteProject(${p.id})">Excluir</button>` : ""}
            </div>
        `;
    }

    document.getElementById("detalhe-body").innerHTML = html;
    abrirModal("modal-detalhe");
}

// ─── Mover fase pelo detalhe ─────────────────────────────────────────────────

async function moverFaseInline(projetoId) {
    const select = document.getElementById("detalhe-mover-fase");
    const faseId = select.value;
    if (!faseId) { showToast("Selecione uma fase", "error"); return; }

    const res = await fetch(`/api/projetos/${projetoId}/mover-fase`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fase_id: parseInt(faseId) }),
    });

    if (res.ok) {
        showToast("Projeto movido para nova fase!", "success");
        fecharModal("modal-detalhe");
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao mover", "error");
    }
}

// ─── Comentários ─────────────────────────────────────────────────────────────

async function enviarComentario(projetoId) {
    const textarea = document.getElementById("novo-comentario");
    const texto = textarea.value.trim();
    if (!texto) { showToast("Escreva um comentário", "error"); return; }

    const res = await fetch(`/api/projetos/${projetoId}/comentarios`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
    });

    if (res.ok) {
        showToast("Comentário adicionado!", "success");
        // Reabrir o detalhe para mostrar o novo comentário
        openDetail(projetoId);
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao comentar", "error");
    }
}

async function openEditProject(id) {
    fecharModal("modal-detalhe");
    await loadSelectData();
    const res = await fetch(`/api/projetos/${id}`);
    const p = await res.json();

    document.getElementById("modal-projeto-titulo").textContent = "Editar Projeto";
    document.getElementById("proj-id").value = p.id;
    document.getElementById("proj-os").value = p.os;
    document.getElementById("proj-cliente").value = p.cliente;
    document.getElementById("proj-solicitante").value = p.solicitante;
    document.getElementById("proj-atividade").value = p.atividade;
    document.getElementById("proj-data-limite").value = p.data_limite;
    document.getElementById("proj-descricao").value = p.descricao;
    document.getElementById("proj-comentario").value = p.comentario;

    const respSelect = document.getElementById("proj-responsavel");
    respSelect.innerHTML = '<option value="">Selecionar...</option>';
    allFuncionarios.forEach(f => {
        const sel = f.id === p.responsavel_id ? "selected" : "";
        respSelect.innerHTML += `<option value="${f.id}" ${sel}>${f.nome}</option>`;
    });

    const faseSelect = document.getElementById("proj-fase");
    faseSelect.innerHTML = '<option value="">Sem fase</option>';
    allFases.forEach(f => {
        const sel = f.id === p.fase_atual_id ? "selected" : "";
        faseSelect.innerHTML += `<option value="${f.id}" ${sel}>${f.nome}</option>`;
    });

    abrirModal("modal-projeto");
}

async function deleteProject(id) {
    if (!confirm("Tem certeza que deseja excluir este projeto?")) return;
    const res = await fetch(`/api/projetos/${id}`, { method: "DELETE" });
    if (res.ok) {
        fecharModal("modal-detalhe");
        showToast("Projeto excluído!", "success");
        await loadBoard();
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

    const res = await fetch(`/api/projeto-fase/${pfId}/atribuir`, {
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

// ─── Helpers ─────────────────────────────────────────────────────────────────

function abrirModal(id) { document.getElementById(id).style.display = "flex"; }
function fecharModal(id) { document.getElementById(id).style.display = "none"; }

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
