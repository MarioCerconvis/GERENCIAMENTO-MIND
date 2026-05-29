import re

def update_kanban_js():
    with open('static/js/kanban.js', 'r') as f:
        content = f.read()

    # 1. Update loadBoard to handle objects instead of projects
    content = content.replace("col.projetos.length", "col.objetos.length")
    content = content.replace("Nenhum projeto", "Nenhum card")
    content = content.replace("col.projetos.forEach(p => {", "col.objetos.forEach(p => {")
    content = content.replace("draggedProjectId", "draggedObjetoId")
    content = content.replace("dataset.projetoId", "dataset.objetoId")
    content = content.replace("projeto.projeto_os", "projeto.projeto_os")

    # 2. Add adicionarModuloUI and update openNewProject
    # Find openNewProject
    new_proj_code = """
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
            
            <div class="form-group">
                <label>Descrição do Módulo</label>
                <textarea class="mod-descricao" rows="1">${dadosModulo ? dadosModulo.descricao : ''}</textarea>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', modHtml);
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
            
            data.objetos.push({
                nome: modNome,
                fase_id: modFase ? parseInt(modFase) : null,
                data_limite: modData || null,
                responsavel_id: modResp ? parseInt(modResp) : null,
                descricao: modDesc
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
"""
    
    # Replace the blocks for openNewProject and saveProject
    content = re.sub(r'async function openNewProject\(\) \{.*?(?=async function openNewPhase)', new_proj_code, content, flags=re.DOTALL)
    
    # Update drag handlers
    content = content.replace('const res = await fetch(`/api/projetos/${pendingMove.projetoId}/mover-fase`', 'const res = await fetch(`/api/objetos/${pendingMove.projetoId}/mover-fase`')
    content = content.replace('showToast("Projeto movido com sucesso!", "success");', 'showToast("Card movido com sucesso!", "success");')

    # Update detail modal calls
    content = content.replace('async function openDetail(projetoId) {', 'async function openDetail(objetoId) {\n    const projetoId = objetoId;')
    content = content.replace('const res = await fetch(`/api/projetos/${projetoId}`);', 'const res = await fetch(`/api/objetos/${objetoId}`);')
    content = content.replace('document.getElementById("detalhe-titulo").textContent = `Projeto ${p.os}`;', 'document.getElementById("detalhe-titulo").textContent = `${p.projeto_os} - ${p.nome}`;')
    content = content.replace('moverFaseInline(${p.id})', 'moverFaseInline(${p.id})')
    content = content.replace('enviarComentario(${p.id})', 'enviarComentario(${p.id})')
    content = content.replace('openEditProject(${p.id})', 'openEditProject(${p.projeto_id})') # Edit OS!
    content = content.replace('deleteProject(${p.id})', 'deleteObject(${p.id})')

    content = content.replace('enviarComentario(projetoId)', 'enviarComentario(objetoId)')
    content = content.replace('fetch(`/api/projetos/${projetoId}/comentarios`', 'fetch(`/api/objetos/${objetoId}/comentarios`')

    # Create Object Edit/Delete handlers
    edit_delete_code = """
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
"""
    content = re.sub(r'async function openEditProject\(id\) \{.*?(?=// ─── Assign Employee ───)', edit_delete_code, content, flags=re.DOTALL)

    # In detail view, fix display values
    content = content.replace('<div class="detail-item"><span class="detail-label">OS</span><span class="detail-value">${p.os}</span></div>', 
                              '<div class="detail-item"><span class="detail-label">OS</span><span class="detail-value">${p.projeto_os}</span></div>')
    
    # Also adjust card HTML creation for project_os
    content = content.replace('<div class="card-os">${projeto.os}</div>', '<div class="card-os">${projeto.projeto_os} <span style="font-size:0.8em; color:#64748b; font-weight:normal;">- ${projeto.nome}</span></div>')
    
    # And fix Atividade which is gone
    content = content.replace('${projeto.atividade ? `<div class="card-atividade">${projeto.atividade}</div>` : ""}', '')

    # Assign endpoint
    content = content.replace('/api/projeto-fase/${pfId}/atribuir', '/api/objeto-fase/${pfId}/atribuir')
    
    with open('static/js/kanban.js', 'w') as f:
        f.write(content)
        
    print("kanban.js updated.")

if __name__ == "__main__":
    update_kanban_js()
