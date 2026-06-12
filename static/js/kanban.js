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
                <span class="column-count">${col.objetos.length}</span>
            </div>
            <div class="column-body" data-fase-id="${col.id ?? 'sem_fase'}"></div>
        `;

        // Set header top border color
        column.querySelector(".column-header").style.cssText += `border-top: 3px solid ${headerColor};`;

        const body = column.querySelector(".column-body");

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
            card.style.backgroundColor = "rgba(144, 238, 144, 0.2)"; // verde claro mais transparente
        } else if (sf.dias_restantes === 2) {
            card.style.backgroundColor = "rgba(255, 255, 0, 0.2)"; // amarelo mais transparente
        } else if (sf.dias_restantes === 1 || sf.dias_restantes === 0) {
            card.style.backgroundColor = "rgba(255, 165, 0, 0.2)"; // laranja mais transparente
        } else if (sf.dias_restantes < 0) {
            card.style.backgroundColor = "rgba(255, 0, 0, 0.15)"; // vermelho mais transparente
        }
    }

    let hasProximaEtapa = false;
    if (projeto.etapas_pre_definidas) {
        const etapasStr = String(projeto.etapas_pre_definidas).split(",").filter(e => e);
        const currentIndex = etapasStr.indexOf(String(projeto.fase_atual_id));
        if (currentIndex !== -1 && currentIndex + 1 < etapasStr.length) {
            hasProximaEtapa = true;
        } else if (currentIndex === -1 && etapasStr.length > 0) {
            hasProximaEtapa = true;
        }
    }

    card.innerHTML = `
        <div class="card-os">${projeto.projeto_os} <span style="font-size:0.8em; color:#64748b; font-weight:normal;">- ${projeto.nome}</span></div>
        <div class="card-cliente">${projeto.cliente || "—"}</div>
        
        <div class="card-footer">
            <span class="sla-badge ${slaClass}">${slaIcon} ${slaDias}</span>
            <span class="card-days">${diasFase}</span>
        </div>
        ${projeto.responsavel_nome ? `<div class="card-responsavel">👤 ${projeto.responsavel_nome}</div>` : ""}
        ${hasProximaEtapa ? `
            <div style="margin-top: 8px;">
                <button class="btn btn-primary btn-sm" onclick="concluirFasePreDefinida(event, ${projeto.id})" style="width: 100%; background-color: #22c55e; border-color: #22c55e; color: white;">✔ Concluído</button>
            </div>
        ` : ""}
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
        showToast("Fase concluída e movida com sucesso!", "success");
        await loadBoard();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro ao concluir fase", "error");
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

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    e.currentTarget.classList.add("drag-over");
}

function handleDragLeave(e) {
    e.currentTarget.classList.remove("drag-over");
}

let pendingMove = null;

async function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove("drag-over");
    const faseId = e.currentTarget.dataset.faseId;
    if (!draggedObjetoId || faseId === "sem_fase") return;

    pendingMove = { projetoId: draggedObjetoId, faseId: parseInt(faseId), isInline: false };
    document.getElementById("mover-data-limite").value = "";
    abrirModal("modal-mover-fase");
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
    if (dadosModulo && dadosModulo.etapas_pre_definidas) {
        const etapas = String(dadosModulo.etapas_pre_definidas).split(",");
        etapas.forEach(val => {
            if (!val.trim()) return;
            const selOpts = allFases.map(f => `<option value="${f.id}" ${f.id == val ? 'selected' : ''}>${f.nome}</option>`).join("");
            fluxoHtml += `<select class="input-select mod-etapa-step" style="width:auto; margin-bottom:4px;"><option value="">--</option>${selOpts}</select>`;
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
                    <label>Data Limite do Módulo</label>
                    <input type="date" class="mod-data" value="${dadosModulo && dadosModulo.data_limite ? dadosModulo.data_limite.split('T')[0] : ''}">
                </div>
                <div class="form-group">
                    <label>Responsável</label>
                    <select class="mod-responsavel">
                        <option value="">(Mesmo da OS se vazio)</option>
                        ${responsavelOptions}
                    </select>
                </div>
            </div>
            
            <div class="form-group" style="grid-column: 1 / -1;">
                <label>Fluxo de Fases Pré-Definidas (Opcional, em ordem)</label>
                <div class="mod-fluxo-container" style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:8px;">
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
    const sel = document.createElement("select");
    sel.className = "input-select mod-etapa-step";
    sel.style.width = "auto";
    sel.style.marginBottom = "4px";
    sel.innerHTML = `<option value="">--</option>${faseOptions}`;
    container.appendChild(sel);
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
            const modResp = mod.querySelector(".mod-responsavel").value;
            const modDesc = mod.querySelector(".mod-descricao").value;
            const modEtapas = Array.from(mod.querySelectorAll(".mod-etapa-step")).map(s => s.value).filter(v => v);
            
            data.objetos.push({
                nome: modNome,
                fase_id: modFase ? parseInt(modFase) : null,
                data_limite: modData || null,
                responsavel_id: modResp ? parseInt(modResp) : null,
                descricao: modDesc,
                etapas_pre_definidas: modEtapas.length > 0 ? modEtapas.map(Number) : null
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
        fecharModal("modal-projeto");
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

    document.getElementById("detalhe-titulo").textContent = `${p.projeto_os} - ${p.nome}`;

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
            <div class="detail-item"><span class="detail-label">OS</span><span class="detail-value">${p.projeto_os}</span></div>
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
                <button class="btn btn-ghost" onclick="openEditProject(${p.projeto_id})">Editar</button>
                ${currentUser.perfil === "admin" ? `<button class="btn btn-danger btn-sm" onclick="deleteObject(${p.id})">Excluir</button>` : ""}
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
        openDetail(projetoId);
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

