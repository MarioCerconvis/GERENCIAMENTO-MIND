/* ═══════════════════════════════════════════════════════════════════════
   PRIORIDADES.JS — Fila de trabalhos atuais de cada funcionário
   Admin reordena (arrastar ou setas) e salva por funcionário; gestor só visualiza.
   ═══════════════════════════════════════════════════════════════════════ */

let usuarioPrio = null;
let filas = [];                 // [{funcionario, itens}]
const ordemSalva = new Map();   // funcionario_id -> [objeto_fase_id, ...] (como está no servidor)

document.addEventListener("DOMContentLoaded", async () => {
    const res = await fetch("/api/me");
    if (!res.ok) { window.location = "/login"; return; }
    usuarioPrio = await res.json();
    document.getElementById("user-name").textContent = usuarioPrio.nome;
    document.getElementById("user-badge").textContent = usuarioPrio.perfil;
    if (!podeEditar()) {
        document.getElementById("prio-subtitulo").textContent =
            "Cada coluna é a fila de trabalhos atuais de um funcionário. 1 = mais importante. Somente administradores podem alterar a ordem.";
    }

    document.getElementById("prio-busca").addEventListener("input", aplicarFiltros);
    document.getElementById("prio-mostrar-vazios").addEventListener("change", aplicarFiltros);
    window.addEventListener("beforeunload", (e) => {
        if (document.querySelector(".prio-coluna.alterada")) {
            e.preventDefault();
            e.returnValue = "";
        }
    });

    await carregarFilas();
});

function podeEditar() {
    return usuarioPrio?.perfil === "admin";
}

async function carregarFilas() {
    const res = await fetch("/api/prioridades");
    if (!res.ok) {
        mostrarToast("Erro ao carregar as filas de prioridade", "error");
        return;
    }
    filas = await res.json();
    ordemSalva.clear();
    filas.forEach(f => ordemSalva.set(f.funcionario.id, f.itens.map(i => i.objeto_fase_id)));
    renderBoard();
}

// ─── Render ──────────────────────────────────────────────────────────────────

function esc(valor) {
    return String(valor ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

function renderBoard() {
    const board = document.getElementById("prio-board");
    board.innerHTML = "";
    // Mais carregados primeiro: é onde a priorização mais importa
    [...filas]
        .sort((a, b) => b.itens.length - a.itens.length || a.funcionario.nome.localeCompare(b.funcionario.nome, "pt-BR"))
        .forEach(fila => board.appendChild(criarColuna(fila)));
    aplicarFiltros();
}

function criarColuna(fila) {
    const { funcionario, itens } = fila;
    const coluna = document.createElement("section");
    coluna.className = "prio-coluna";
    coluna.dataset.funcId = funcionario.id;
    coluna.dataset.busca = [funcionario.nome, ...itens.map(i => `${i.os} ${i.projeto_nome} ${i.modulo} ${i.cliente}`)]
        .join(" ").toLowerCase();
    coluna.setAttribute("aria-label", `Fila de ${funcionario.nome}`);

    coluna.innerHTML = `
        <header class="prio-coluna-header">
            <div class="prio-coluna-titulo">
                <span>${esc(funcionario.nome)}</span>
                <span class="prio-contador">${itens.length} ${itens.length === 1 ? "trabalho" : "trabalhos"}</span>
            </div>
            <div class="prio-coluna-funcoes">${esc(funcionario.funcoes.join(", ") || "Sem função")}</div>
        </header>
        <ol class="prio-lista"></ol>
        <footer class="prio-coluna-rodape">
            <button type="button" class="btn btn-ghost btn-sm" data-acao="descartar">Descartar</button>
            <button type="button" class="btn btn-primary btn-sm" data-acao="salvar">Salvar ordem</button>
        </footer>
    `;

    const lista = coluna.querySelector(".prio-lista");
    if (itens.length === 0) {
        lista.innerHTML = `<li class="prio-vazio">Nenhum trabalho atual</li>`;
    } else {
        itens.forEach(item => lista.appendChild(criarItem(item)));
        atualizarPosicoes(coluna);
    }

    if (podeEditar()) {
        lista.addEventListener("dragover", (e) => arrastarSobre(e, lista));
        coluna.querySelector('[data-acao="salvar"]').addEventListener("click", () => salvarColuna(coluna));
        coluna.querySelector('[data-acao="descartar"]').addEventListener("click", () => descartarColuna(coluna));
    }
    return coluna;
}

function textoPrazo(dias) {
    if (dias == null) return { texto: "Sem prazo de fase", classe: "" };
    if (dias < 0) return { texto: `${Math.abs(dias)}d de atraso`, classe: "prio-prazo-atraso" };
    if (dias <= 2) return { texto: dias === 0 ? "Vence hoje" : `${dias}d restantes`, classe: "prio-prazo-alerta" };
    return { texto: `${dias}d restantes`, classe: "prio-prazo-ok" };
}

function criarItem(item) {
    const li = document.createElement("li");
    li.className = "prio-item" + (podeEditar() ? "" : " somente-leitura");
    li.dataset.ofId = item.objeto_fase_id;
    li.style.setProperty("--fase-cor", item.fase_cor);
    const prazo = textoPrazo(item.dias_restantes_fase);

    li.innerHTML = `
        <span class="prio-posicao" aria-hidden="true"></span>
        <div class="prio-item-corpo">
            <div class="prio-item-os" title="${esc(item.os)} — ${esc(item.projeto_nome)}">${esc(item.os)} <span style="font-weight:500;color:var(--text-muted);">${esc(item.projeto_nome)}</span></div>
            <div class="prio-item-modulo">${esc(item.modulo)}${item.cliente ? ` · ${esc(item.cliente)}` : ""}</div>
            <div class="prio-item-meta">
                <span class="prio-fase">● ${esc(item.fase_nome)}</span>
                <span class="${prazo.classe}">📅 ${prazo.texto}</span>
                <span>⏱️ ${item.dias_na_fase}d na fase</span>
            </div>
        </div>
        ${podeEditar() ? `
            <div class="prio-item-setas">
                <button type="button" class="prio-seta" data-dir="-1" aria-label="Subir prioridade">▲</button>
                <button type="button" class="prio-seta" data-dir="1" aria-label="Descer prioridade">▼</button>
            </div>` : ""}
    `;

    if (podeEditar()) {
        li.draggable = true;
        li.addEventListener("dragstart", () => li.classList.add("arrastando"));
        li.addEventListener("dragend", () => {
            li.classList.remove("arrastando");
            atualizarPosicoes(li.closest(".prio-coluna"));
        });
        li.querySelectorAll(".prio-seta").forEach(btn => {
            btn.addEventListener("click", () => moverComSeta(li, parseInt(btn.dataset.dir), btn.dataset.dir));
        });
    }
    return li;
}

// Renumera 1..n conforme a ordem na tela e marca a coluna se difere do salvo
function atualizarPosicoes(coluna) {
    const itens = [...coluna.querySelectorAll(".prio-item")];
    itens.forEach((li, idx) => {
        const pos = idx + 1;
        const badge = li.querySelector(".prio-posicao");
        badge.textContent = pos;
        badge.className = "prio-posicao " + (pos === 1 ? "prio-1" : pos <= 3 ? "prio-2" : "prio-n");
        li.setAttribute("aria-label", `Prioridade ${pos} de ${itens.length}`);
        const [subir, descer] = li.querySelectorAll(".prio-seta");
        if (subir) subir.disabled = idx === 0;
        if (descer) descer.disabled = idx === itens.length - 1;
    });
    const atual = itens.map(li => parseInt(li.dataset.ofId));
    const salvo = ordemSalva.get(parseInt(coluna.dataset.funcId)) || [];
    coluna.classList.toggle("alterada", atual.join(",") !== salvo.join(","));
}

// ─── Reordenação ─────────────────────────────────────────────────────────────

function arrastarSobre(e, lista) {
    const arrastando = document.querySelector(".prio-item.arrastando");
    // Só reordena dentro da própria fila (mudar de funcionário é reatribuição, feita no card)
    if (!arrastando || arrastando.parentElement !== lista) return;
    e.preventDefault();
    const depois = [...lista.querySelectorAll(".prio-item:not(.arrastando)")].reduce((maisPerto, el) => {
        const box = el.getBoundingClientRect();
        const offset = e.clientY - box.top - box.height / 2;
        return offset < 0 && offset > maisPerto.offset ? { offset, el } : maisPerto;
    }, { offset: Number.NEGATIVE_INFINITY }).el;
    if (depois) lista.insertBefore(arrastando, depois);
    else lista.appendChild(arrastando);
}

function moverComSeta(li, direcao, dir) {
    const alvo = direcao < 0 ? li.previousElementSibling : li.nextElementSibling;
    if (!alvo) return;
    if (direcao < 0) li.parentElement.insertBefore(li, alvo);
    else li.parentElement.insertBefore(alvo, li);
    atualizarPosicoes(li.closest(".prio-coluna"));
    // Mantém o foco no mesmo botão para mover várias posições pelo teclado
    const btn = li.querySelector(`.prio-seta[data-dir="${dir}"]`);
    if (btn && !btn.disabled) btn.focus();
}

async function salvarColuna(coluna) {
    const funcId = parseInt(coluna.dataset.funcId);
    const ordem = [...coluna.querySelectorAll(".prio-item")].map(li => parseInt(li.dataset.ofId));
    const btn = coluna.querySelector('[data-acao="salvar"]');
    btn.disabled = true;
    try {
        const res = await fetch(`/api/prioridades/${funcId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ordem }),
        });
        const data = await res.json();
        if (res.ok) {
            substituirFila(data);
            mostrarToast(`Prioridades de ${data.funcionario.nome} salvas!`, "success");
        } else if (res.status === 409 && data.fila) {
            // A fila mudou (trabalho novo, aprovação...): mostra a versão atual
            substituirFila(data.fila);
            mostrarToast(data.erro, "error");
        } else {
            mostrarToast(data.erro || "Erro ao salvar prioridades", "error");
        }
    } finally {
        btn.disabled = false;
    }
}

function descartarColuna(coluna) {
    const funcId = parseInt(coluna.dataset.funcId);
    const fila = filas.find(f => f.funcionario.id === funcId);
    if (fila) coluna.replaceWith(criarColuna(fila));
    aplicarFiltros();
}

function substituirFila(fila) {
    const idx = filas.findIndex(f => f.funcionario.id === fila.funcionario.id);
    if (idx >= 0) filas[idx] = fila;
    ordemSalva.set(fila.funcionario.id, fila.itens.map(i => i.objeto_fase_id));
    const coluna = document.querySelector(`.prio-coluna[data-func-id="${fila.funcionario.id}"]`);
    if (coluna) coluna.replaceWith(criarColuna(fila));
    aplicarFiltros();
}

// ─── Filtros ─────────────────────────────────────────────────────────────────

function aplicarFiltros() {
    const busca = document.getElementById("prio-busca").value.trim().toLowerCase();
    const mostrarVazios = document.getElementById("prio-mostrar-vazios").checked;
    let visiveis = 0;
    document.querySelectorAll(".prio-coluna").forEach(coluna => {
        const vazia = coluna.querySelectorAll(".prio-item").length === 0;
        const visivel = (!busca || coluna.dataset.busca.includes(busca))
            && (mostrarVazios || !vazia || coluna.classList.contains("alterada"));
        coluna.style.display = visivel ? "" : "none";
        if (visivel) visiveis++;
    });

    let vazio = document.getElementById("prio-sem-resultado");
    if (visiveis === 0) {
        if (!vazio) {
            vazio = document.createElement("div");
            vazio.id = "prio-sem-resultado";
            vazio.className = "empty-state";
            document.getElementById("prio-board").appendChild(vazio);
        }
        vazio.innerHTML = busca
            ? `<div class="empty-state-icon">🔍</div>Nenhum funcionário ou OS encontrado para "${esc(busca)}".`
            : `<div class="empty-state-icon">🎉</div>Nenhum funcionário com trabalhos atuais.`;
    } else if (vazio) {
        vazio.remove();
    }
}

// ─── Toast ───────────────────────────────────────────────────────────────────

function mostrarToast(mensagem, tipo = "success") {
    let container = document.querySelector(".toast-container");
    if (!container) {
        container = document.createElement("div");
        container.className = "toast-container";
        document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.className = `toast toast-${tipo}`;
    toast.textContent = mensagem;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}
