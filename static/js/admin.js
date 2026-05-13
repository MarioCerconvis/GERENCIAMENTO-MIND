/* ═══════════════════════════════════════════════════════════════════════
   ADMIN.JS — Painel Administrativo
   ═══════════════════════════════════════════════════════════════════════ */

let currentUser = null;
let tabAtiva = "funcionarios";

document.addEventListener("DOMContentLoaded", async () => {
    await loadUser();
    setupTabs();
    loadTab("funcionarios");
});

async function loadUser() {
    const res = await fetch("/api/me");
    if (!res.ok) { window.location = "/login"; return; }
    currentUser = await res.json();
    document.getElementById("user-name").textContent = currentUser.nome;
    document.getElementById("user-badge").textContent = currentUser.perfil;
    // Hide usuarios tab for non-admin
    if (currentUser.perfil !== "admin") {
        const tabBtn = document.getElementById("tab-usuarios");
        if (tabBtn) tabBtn.style.display = "none";
    }
}

// ─── Tabs ────────────────────────────────────────────────────────────────────

function setupTabs() {
    document.querySelectorAll(".sidebar-link").forEach(btn => {
        btn.addEventListener("click", () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll(".sidebar-link").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            document.querySelectorAll(".admin-tab").forEach(p => p.style.display = "none");
            document.getElementById(`panel-${tab}`).style.display = "";
            tabAtiva = tab;
            loadTab(tab);
        });
    });
}

async function loadTab(tab) {
    switch (tab) {
        case "funcionarios": await loadFuncionarios(); break;
        case "funcoes": await loadFuncoes(); break;
        case "fases": await loadFases(); break;
        case "usuarios": await loadUsuarios(); break;
    }
}

// ─── FUNCIONÁRIOS ────────────────────────────────────────────────────────────

async function loadFuncionarios() {
    const res = await fetch("/api/funcionarios");
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.querySelector("#table-funcionarios tbody");
    tbody.innerHTML = "";
    data.forEach(f => {
        const funcoes = (f.funcoes || []).map(fn => `<span class="tag">${fn.nome}</span>`).join("");
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${f.nome}</td>
            <td>${f.email}</td>
            <td>${funcoes || "—"}</td>
            <td>
                <button class="btn btn-ghost btn-sm" onclick="editFuncionario(${f.id})">Editar</button>
                <button class="btn btn-danger btn-sm" onclick="deleteFuncionario(${f.id})">Excluir</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

document.getElementById("btn-novo-funcionario")?.addEventListener("click", () => openFuncionarioModal());

async function openFuncionarioModal(funcData = null) {
    const funcoesRes = await fetch("/api/funcoes");
    const funcoes = funcoesRes.ok ? await funcoesRes.json() : [];

    const isEdit = !!funcData;
    document.getElementById("modal-admin-titulo").textContent = isEdit ? "Editar Funcionário" : "Novo Funcionário";

    const selectedFuncoes = isEdit ? (funcData.funcoes || []).map(f => f.id) : [];

    document.getElementById("modal-admin-body").innerHTML = `
        <input type="hidden" id="admin-edit-id" value="${isEdit ? funcData.id : ''}">
        <div class="form-group">
            <label>Nome *</label>
            <input type="text" id="admin-nome" value="${isEdit ? funcData.nome : ''}">
        </div>
        <div class="form-group">
            <label>E-mail *</label>
            <input type="email" id="admin-email" value="${isEdit ? funcData.email : ''}">
        </div>
        <div class="form-group">
            <label>Funções</label>
            <div class="checkbox-list">
                ${funcoes.map(f => `<label><input type="checkbox" value="${f.id}" ${selectedFuncoes.includes(f.id) ? 'checked' : ''}> ${f.nome}</label>`).join("")}
            </div>
        </div>
    `;

    document.getElementById("btn-salvar-admin").onclick = async () => {
        const id = document.getElementById("admin-edit-id").value;
        const funcaoIds = [...document.querySelectorAll("#modal-admin-body input[type=checkbox]:checked")].map(cb => parseInt(cb.value));
        const body = {
            nome: document.getElementById("admin-nome").value,
            email: document.getElementById("admin-email").value,
            funcao_ids: funcaoIds,
        };
        const url = id ? `/api/funcionarios/${id}` : "/api/funcionarios";
        const method = id ? "PUT" : "POST";
        const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (res.ok) {
            fecharModal("modal-admin");
            showToast(id ? "Funcionário atualizado!" : "Funcionário criado!", "success");
            loadFuncionarios();
        } else {
            const err = await res.json();
            showToast(err.erro || "Erro", "error");
        }
    };

    abrirModal("modal-admin");
}

async function editFuncionario(id) {
    const res = await fetch("/api/funcionarios");
    const all = await res.json();
    const f = all.find(x => x.id === id);
    if (f) openFuncionarioModal(f);
}

async function deleteFuncionario(id) {
    if (!confirm("Excluir este funcionário?")) return;
    await fetch(`/api/funcionarios/${id}`, { method: "DELETE" });
    showToast("Funcionário excluído!", "success");
    loadFuncionarios();
}

// ─── FUNÇÕES ─────────────────────────────────────────────────────────────────

async function loadFuncoes() {
    const res = await fetch("/api/funcoes");
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.querySelector("#table-funcoes tbody");
    tbody.innerHTML = "";
    data.forEach(f => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${f.nome}</td>
            <td>
                <button class="btn btn-ghost btn-sm" onclick="editFuncao(${f.id}, '${f.nome}')">Editar</button>
                <button class="btn btn-danger btn-sm" onclick="deleteFuncao(${f.id})">Excluir</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

document.getElementById("btn-nova-funcao")?.addEventListener("click", () => openFuncaoModal());

function openFuncaoModal(id = null, nome = "") {
    document.getElementById("modal-admin-titulo").textContent = id ? "Editar Função" : "Nova Função";
    document.getElementById("modal-admin-body").innerHTML = `
        <input type="hidden" id="admin-edit-id" value="${id || ''}">
        <div class="form-group">
            <label>Nome da Função *</label>
            <input type="text" id="admin-nome" value="${nome}">
        </div>
    `;
    document.getElementById("btn-salvar-admin").onclick = async () => {
        const editId = document.getElementById("admin-edit-id").value;
        const body = { nome: document.getElementById("admin-nome").value };
        const url = editId ? `/api/funcoes/${editId}` : "/api/funcoes";
        const method = editId ? "PUT" : "POST";
        const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (res.ok) {
            fecharModal("modal-admin");
            showToast(editId ? "Função atualizada!" : "Função criada!", "success");
            loadFuncoes();
        } else {
            const err = await res.json();
            showToast(err.erro || "Erro", "error");
        }
    };
    abrirModal("modal-admin");
}

function editFuncao(id, nome) { openFuncaoModal(id, nome); }

async function deleteFuncao(id) {
    if (!confirm("Excluir esta função?")) return;
    await fetch(`/api/funcoes/${id}`, { method: "DELETE" });
    showToast("Função excluída!", "success");
    loadFuncoes();
}

// ─── FASES ───────────────────────────────────────────────────────────────────

async function loadFases() {
    const res = await fetch("/api/fases");
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.querySelector("#table-fases tbody");
    tbody.innerHTML = "";
    data.forEach(f => {
        const funcoes = (f.funcoes_exigidas || []).map(fn => `<span class="tag">${fn.nome}</span>`).join("");
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${f.ordem}</td>
            <td>${f.nome}</td>
            <td><span style="display:inline-block;width:24px;height:24px;background:${f.cor};border-radius:4px;vertical-align:middle;"></span></td>
            <td>${funcoes || "—"}</td>
            <td>
                <button class="btn btn-ghost btn-sm" onclick="editFase(${f.id})">Editar</button>
                <button class="btn btn-danger btn-sm" onclick="deleteFase(${f.id})">Excluir</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

document.getElementById("btn-nova-fase-admin")?.addEventListener("click", () => openFaseModal());

async function openFaseModal(faseData = null) {
    const funcoesRes = await fetch("/api/funcoes");
    const funcoes = funcoesRes.ok ? await funcoesRes.json() : [];

    const isEdit = !!faseData;
    document.getElementById("modal-admin-titulo").textContent = isEdit ? "Editar Fase" : "Nova Fase";
    const selectedFuncoes = isEdit ? (faseData.funcoes_exigidas || []).map(f => f.id) : [];

    document.getElementById("modal-admin-body").innerHTML = `
        <input type="hidden" id="admin-edit-id" value="${isEdit ? faseData.id : ''}">
        <div class="form-group">
            <label>Nome *</label>
            <input type="text" id="admin-nome" value="${isEdit ? faseData.nome : ''}">
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>Cor</label>
                <input type="color" id="admin-cor" value="${isEdit ? faseData.cor : '#6366f1'}">
            </div>
            <div class="form-group">
                <label>Ordem</label>
                <input type="number" id="admin-ordem" value="${isEdit ? faseData.ordem : 0}">
            </div>
        </div>
        <div class="form-group">
            <label>Descrição</label>
            <input type="text" id="admin-descricao" value="${isEdit ? faseData.descricao : ''}">
        </div>
        <div class="form-group">
            <label>Funções Exigidas</label>
            <div class="checkbox-list">
                ${funcoes.map(f => `<label><input type="checkbox" value="${f.id}" ${selectedFuncoes.includes(f.id) ? 'checked' : ''}> ${f.nome}</label>`).join("")}
            </div>
        </div>
    `;

    document.getElementById("btn-salvar-admin").onclick = async () => {
        const editId = document.getElementById("admin-edit-id").value;
        const funcaoIds = [...document.querySelectorAll("#modal-admin-body input[type=checkbox]:checked")].map(cb => parseInt(cb.value));
        const body = {
            nome: document.getElementById("admin-nome").value,
            cor: document.getElementById("admin-cor").value,
            ordem: parseInt(document.getElementById("admin-ordem").value) || 0,
            descricao: document.getElementById("admin-descricao").value,
            funcao_ids: funcaoIds,
        };
        const url = editId ? `/api/fases/${editId}` : "/api/fases";
        const method = editId ? "PUT" : "POST";
        const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (res.ok) {
            fecharModal("modal-admin");
            showToast(editId ? "Fase atualizada!" : "Fase criada!", "success");
            loadFases();
        } else {
            const err = await res.json();
            showToast(err.erro || "Erro", "error");
        }
    };
    abrirModal("modal-admin");
}

async function editFase(id) {
    const res = await fetch("/api/fases");
    const all = await res.json();
    const f = all.find(x => x.id === id);
    if (f) openFaseModal(f);
}

async function deleteFase(id) {
    if (!confirm("Excluir esta fase?")) return;
    await fetch(`/api/fases/${id}`, { method: "DELETE" });
    showToast("Fase excluída!", "success");
    loadFases();
}

// ─── USUÁRIOS ────────────────────────────────────────────────────────────────

async function loadUsuarios() {
    const res = await fetch("/api/usuarios");
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.querySelector("#table-usuarios tbody");
    tbody.innerHTML = "";
    data.forEach(u => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${u.nome}</td>
            <td>${u.email}</td>
            <td><span class="tag">${u.perfil}</span></td>
            <td>${u.ativo ? "✅" : "❌"}</td>
            <td>
                <button class="btn btn-ghost btn-sm" onclick="editUsuario(${u.id})">Editar</button>
                <button class="btn btn-ghost btn-sm" onclick="resetSenha(${u.id})">Reset Senha</button>
                <button class="btn btn-danger btn-sm" onclick="deleteUsuario(${u.id})">Excluir</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

document.getElementById("btn-novo-usuario")?.addEventListener("click", () => openUsuarioModal());

function openUsuarioModal(userData = null) {
    const isEdit = !!userData;
    document.getElementById("modal-admin-titulo").textContent = isEdit ? "Editar Usuário" : "Novo Usuário";
    document.getElementById("modal-admin-body").innerHTML = `
        <input type="hidden" id="admin-edit-id" value="${isEdit ? userData.id : ''}">
        <div class="form-group">
            <label>Nome *</label>
            <input type="text" id="admin-nome" value="${isEdit ? userData.nome : ''}">
        </div>
        <div class="form-group">
            <label>E-mail *</label>
            <input type="email" id="admin-email" value="${isEdit ? userData.email : ''}" ${isEdit ? 'readonly' : ''}>
        </div>
        <div class="form-group">
            <label>Perfil *</label>
            <select id="admin-perfil">
                <option value="funcionario" ${isEdit && userData.perfil === 'funcionario' ? 'selected' : ''}>Funcionário</option>
                <option value="gestor" ${isEdit && userData.perfil === 'gestor' ? 'selected' : ''}>Gestor</option>
                <option value="admin" ${isEdit && userData.perfil === 'admin' ? 'selected' : ''}>Admin</option>
            </select>
        </div>
        ${!isEdit ? `<div class="form-group"><label>Senha</label><input type="password" id="admin-senha" placeholder="Padrão: Trocar@123"></div>` : ''}
    `;

    document.getElementById("btn-salvar-admin").onclick = async () => {
        const editId = document.getElementById("admin-edit-id").value;
        const body = {
            nome: document.getElementById("admin-nome").value,
            perfil: document.getElementById("admin-perfil").value,
        };
        if (!editId) {
            body.email = document.getElementById("admin-email").value;
            const senha = document.getElementById("admin-senha")?.value;
            if (senha) body.senha = senha;
        }
        const url = editId ? `/api/usuarios/${editId}` : "/api/usuarios";
        const method = editId ? "PUT" : "POST";
        const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (res.ok) {
            fecharModal("modal-admin");
            showToast(editId ? "Usuário atualizado!" : "Usuário criado!", "success");
            loadUsuarios();
        } else {
            const err = await res.json();
            showToast(err.erro || "Erro", "error");
        }
    };
    abrirModal("modal-admin");
}

async function editUsuario(id) {
    const res = await fetch("/api/usuarios");
    const all = await res.json();
    const u = all.find(x => x.id === id);
    if (u) openUsuarioModal(u);
}

async function resetSenha(id) {
    const nova = prompt("Nova senha (deixe em branco para Trocar@123):");
    const body = nova ? { senha: nova } : {};
    await fetch(`/api/usuarios/${id}/reset-senha`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    showToast("Senha resetada!", "success");
}

async function deleteUsuario(id) {
    if (!confirm("Excluir este usuário?")) return;
    const res = await fetch(`/api/usuarios/${id}`, { method: "DELETE" });
    if (res.ok) {
        showToast("Usuário excluído!", "success");
        loadUsuarios();
    } else {
        const err = await res.json();
        showToast(err.erro || "Erro", "error");
    }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function abrirModal(id) { document.getElementById(id).style.display = "flex"; }
function fecharModal(id) { document.getElementById(id).style.display = "none"; }

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
    setTimeout(() => toast.remove(), 4000);
}

// Close modals on overlay click
document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) overlay.style.display = "none";
    });
});
