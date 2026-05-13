from datetime import datetime, date

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_bcrypt import Bcrypt
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from models import (
    db, configure_db, Usuario, Funcionario, Funcao, Fase,
    Projeto, ProjetoFase, Comentario, funcionario_funcao, fase_funcao,
    projeto_fase_funcionario,
)
from auth import get_usuario_logado, requer_login, requer_perfil, requer_perfil_api, get_abas_usuario
from notifications import notificar_atribuicao, notificar_mudanca_fase
from sla_checker import verificar_sla_projetos

# ─── App ──────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config.from_object(Config)
configure_db(app)
bcrypt = Bcrypt(app)

with app.app_context():
    db.create_all()

# ─── SLA Scheduler ────────────────────────────────────────────────────────────

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=lambda: app.app_context().push() or verificar_sla_projetos(),
    trigger="cron",
    hour=Config.SLA_CHECK_HOUR,
    minute=Config.SLA_CHECK_MINUTE,
)
scheduler.start()


# ═══════════════════════════════════════════════════════════════════════════════
#  PÁGINAS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    u = get_usuario_logado()
    if u:
        return redirect(url_for("kanban_page"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and usuario.ativo and bcrypt.check_password_hash(usuario.hash_senha, senha):
            session["usuario_id"] = usuario.id
            if usuario.trocar_senha:
                return redirect(url_for("trocar_senha"))
            return redirect(url_for("kanban_page"))
        else:
            erro = "E-mail ou senha incorretos."
    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/trocar-senha", methods=["GET", "POST"])
@requer_login
def trocar_senha():
    u = get_usuario_logado()
    erro = None
    if request.method == "POST":
        nova = request.form.get("nova", "").strip()
        confirma = request.form.get("confirma", "").strip()
        if len(nova) < 6:
            erro = "A senha deve ter ao menos 6 caracteres."
        elif nova != confirma:
            erro = "As senhas não coincidem."
        else:
            u.hash_senha = bcrypt.generate_password_hash(nova).decode("utf-8")
            u.trocar_senha = False
            db.session.commit()
            return redirect(url_for("kanban_page"))
    return render_template("trocar_senha.html", usuario=u, erro=erro)


@app.route("/kanban")
@requer_login
def kanban_page():
    return render_template("kanban.html")


@app.route("/admin")
@requer_perfil("admin", "gestor")
def admin_page():
    return render_template("admin.html")


# ═══════════════════════════════════════════════════════════════════════════════
#  API: SESSÃO
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/me")
def api_me():
    u = get_usuario_logado()
    if not u:
        return jsonify({"logado": False}), 401
    return jsonify({
        "logado": True,
        **u.to_dict(),
        "abas": get_abas_usuario(u),
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  API: USUÁRIOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/usuarios", methods=["GET"])
@requer_perfil_api("admin")
def api_listar_usuarios():
    usuarios = Usuario.query.all()
    return jsonify([u.to_dict() for u in usuarios])


@app.route("/api/usuarios", methods=["POST"])
@requer_perfil_api("admin")
def api_criar_usuario():
    body = request.get_json()
    nome = body.get("nome", "").strip()
    email = body.get("email", "").strip().lower()
    perfil = body.get("perfil", "funcionario").strip()
    senha = body.get("senha", "Trocar@123").strip()
    if not nome or not email:
        return jsonify({"erro": "Nome e e-mail são obrigatórios"}), 400
    if perfil not in ("admin", "gestor", "funcionario"):
        return jsonify({"erro": "Perfil inválido"}), 400
    if Usuario.query.filter_by(email=email).first():
        return jsonify({"erro": "Usuário já existe"}), 409
    novo = Usuario(
        nome=nome, email=email, perfil=perfil,
        hash_senha=bcrypt.generate_password_hash(senha).decode("utf-8"),
        trocar_senha=True,
    )
    db.session.add(novo)
    db.session.commit()
    return jsonify(novo.to_dict()), 201


@app.route("/api/usuarios/<int:uid>", methods=["PUT"])
@requer_perfil_api("admin")
def api_editar_usuario(uid):
    u = Usuario.query.get_or_404(uid)
    body = request.get_json()
    if "nome" in body:
        u.nome = body["nome"].strip()
    if "perfil" in body and body["perfil"] in ("admin", "gestor", "funcionario"):
        u.perfil = body["perfil"]
    if "ativo" in body:
        u.ativo = body["ativo"]
    db.session.commit()
    return jsonify(u.to_dict())


@app.route("/api/usuarios/<int:uid>", methods=["DELETE"])
@requer_perfil_api("admin")
def api_deletar_usuario(uid):
    me = get_usuario_logado()
    if me.id == uid:
        return jsonify({"erro": "Não pode remover a si mesmo"}), 400
    u = Usuario.query.get_or_404(uid)
    db.session.delete(u)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/usuarios/<int:uid>/reset-senha", methods=["POST"])
@requer_perfil_api("admin")
def api_reset_senha(uid):
    u = Usuario.query.get_or_404(uid)
    nova = request.get_json().get("senha", "Trocar@123")
    u.hash_senha = bcrypt.generate_password_hash(nova).decode("utf-8")
    u.trocar_senha = True
    db.session.commit()
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  API: FUNCIONÁRIOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/funcionarios", methods=["GET"])
@requer_perfil_api("admin", "gestor")
def api_listar_funcionarios():
    funcs = Funcionario.query.all()
    return jsonify([f.to_dict() for f in funcs])


@app.route("/api/funcionarios", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_criar_funcionario():
    body = request.get_json()
    nome = body.get("nome", "").strip()
    email = body.get("email", "").strip().lower()
    if not nome or not email:
        return jsonify({"erro": "Nome e e-mail são obrigatórios"}), 400
    if Funcionario.query.filter_by(email=email).first():
        return jsonify({"erro": "Funcionário já existe"}), 409
    novo = Funcionario(nome=nome, email=email)
    # Vincular funções se fornecidas
    funcao_ids = body.get("funcao_ids", [])
    if funcao_ids:
        funcoes = Funcao.query.filter(Funcao.id_funcao.in_(funcao_ids)).all()
        novo.funcoes = funcoes
    # Vincular a um usuário se fornecido
    usuario_id = body.get("usuario_id")
    if usuario_id:
        novo.usuario_id = usuario_id
    db.session.add(novo)
    db.session.commit()
    return jsonify(novo.to_dict()), 201


@app.route("/api/funcionarios/<int:fid>", methods=["PUT"])
@requer_perfil_api("admin", "gestor")
def api_editar_funcionario(fid):
    f = Funcionario.query.get_or_404(fid)
    body = request.get_json()
    if "nome" in body:
        f.nome = body["nome"].strip()
    if "email" in body:
        f.email = body["email"].strip().lower()
    if "funcao_ids" in body:
        funcoes = Funcao.query.filter(Funcao.id_funcao.in_(body["funcao_ids"])).all()
        f.funcoes = funcoes
    if "usuario_id" in body:
        f.usuario_id = body["usuario_id"]
    db.session.commit()
    return jsonify(f.to_dict())


@app.route("/api/funcionarios/<int:fid>", methods=["DELETE"])
@requer_perfil_api("admin", "gestor")
def api_deletar_funcionario(fid):
    f = Funcionario.query.get_or_404(fid)
    db.session.delete(f)
    db.session.commit()
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  API: FUNÇÕES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/funcoes", methods=["GET"])
@requer_perfil_api("admin", "gestor")
def api_listar_funcoes():
    funcoes = Funcao.query.all()
    return jsonify([f.to_dict() for f in funcoes])


@app.route("/api/funcoes", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_criar_funcao():
    body = request.get_json()
    nome = body.get("nome", "").strip()
    if not nome:
        return jsonify({"erro": "Nome é obrigatório"}), 400
    if Funcao.query.filter_by(nome_funcao=nome).first():
        return jsonify({"erro": "Função já existe"}), 409
    nova = Funcao(nome_funcao=nome)
    db.session.add(nova)
    db.session.commit()
    return jsonify(nova.to_dict()), 201


@app.route("/api/funcoes/<int:fid>", methods=["PUT"])
@requer_perfil_api("admin", "gestor")
def api_editar_funcao(fid):
    f = Funcao.query.get_or_404(fid)
    body = request.get_json()
    if "nome" in body:
        f.nome_funcao = body["nome"].strip()
    db.session.commit()
    return jsonify(f.to_dict())


@app.route("/api/funcoes/<int:fid>", methods=["DELETE"])
@requer_perfil_api("admin", "gestor")
def api_deletar_funcao(fid):
    f = Funcao.query.get_or_404(fid)
    db.session.delete(f)
    db.session.commit()
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  API: FASES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/fases", methods=["GET"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_listar_fases():
    fases = Fase.query.order_by(Fase.ordem).all()
    return jsonify([f.to_dict() for f in fases])


@app.route("/api/fases", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_criar_fase():
    body = request.get_json()
    nome = body.get("nome", "").strip()
    if not nome:
        return jsonify({"erro": "Nome é obrigatório"}), 400
    max_ordem = db.session.query(db.func.max(Fase.ordem)).scalar() or 0
    nova = Fase(
        nome_fase=nome,
        descricao=body.get("descricao", ""),
        cor=body.get("cor", "#6366f1"),
        ordem=max_ordem + 1,
    )
    # Funções exigidas
    funcao_ids = body.get("funcao_ids", [])
    if funcao_ids:
        funcoes = Funcao.query.filter(Funcao.id_funcao.in_(funcao_ids)).all()
        nova.funcoes_exigidas = funcoes
    db.session.add(nova)
    db.session.commit()
    return jsonify(nova.to_dict()), 201


@app.route("/api/fases/<int:fid>", methods=["PUT"])
@requer_perfil_api("admin", "gestor")
def api_editar_fase(fid):
    f = Fase.query.get_or_404(fid)
    body = request.get_json()
    if "nome" in body:
        f.nome_fase = body["nome"].strip()
    if "descricao" in body:
        f.descricao = body["descricao"]
    if "cor" in body:
        f.cor = body["cor"]
    if "ordem" in body:
        f.ordem = body["ordem"]
    if "funcao_ids" in body:
        funcoes = Funcao.query.filter(Funcao.id_funcao.in_(body["funcao_ids"])).all()
        f.funcoes_exigidas = funcoes
    db.session.commit()
    return jsonify(f.to_dict())


@app.route("/api/fases/<int:fid>", methods=["DELETE"])
@requer_perfil_api("admin", "gestor")
def api_deletar_fase(fid):
    f = Fase.query.get_or_404(fid)
    db.session.delete(f)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/fases/reordenar", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_reordenar_fases():
    body = request.get_json()
    ordem = body.get("ordem", [])  # [fase_id, fase_id, ...]
    for i, fase_id in enumerate(ordem):
        fase = db.session.get(Fase, fase_id)
        if fase:
            fase.ordem = i
    db.session.commit()
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  API: PROJETOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/projetos", methods=["GET"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_listar_projetos():
    u = get_usuario_logado()
    query = Projeto.query
    # Funcionário só vê projetos onde está atribuído
    if u.perfil == "funcionario" and u.funcionario:
        func_id = u.funcionario.id_func
        query = query.join(ProjetoFase).join(
            projeto_fase_funcionario,
            projeto_fase_funcionario.c.id_projeto_fase == ProjetoFase.id,
        ).filter(
            projeto_fase_funcionario.c.id_funcionario == func_id
        ).distinct()
    projetos = query.all()
    return jsonify([p.to_dict() for p in projetos])


@app.route("/api/projetos/<int:pid>", methods=["GET"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_detalhe_projeto(pid):
    p = Projeto.query.get_or_404(pid)
    return jsonify(p.to_dict(include_historico=True))


@app.route("/api/projetos", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_criar_projeto():
    body = request.get_json()
    os_code = body.get("os", "").strip()
    if not os_code:
        return jsonify({"erro": "OS é obrigatório"}), 400
    if Projeto.query.filter_by(os=os_code).first():
        return jsonify({"erro": "OS já existe"}), 409
    data_limite = body.get("data_limite")
    if not data_limite:
        return jsonify({"erro": "Data limite é obrigatória"}), 400
    novo = Projeto(
        os=os_code,
        atividade=body.get("atividade", ""),
        cliente=body.get("cliente", ""),
        solicitante=body.get("solicitante", ""),
        descricao=body.get("descricao", ""),
        comentario=body.get("comentario", ""),
        data_limite=date.fromisoformat(data_limite),
        responsavel_id=body.get("responsavel_id"),
    )
    # Se uma fase inicial foi selecionada
    fase_id = body.get("fase_id")
    if fase_id:
        fase = db.session.get(Fase, fase_id)
        if fase:
            novo.fase_atual_id = fase_id
            db.session.add(novo)
            db.session.flush()  # Para obter o ID
            pf = ProjetoFase(
                projeto_id=novo.projeto_id,
                id_fase=fase_id,
                responsavel_fase_id=body.get("responsavel_id"),
            )
            db.session.add(pf)
    else:
        db.session.add(novo)
    db.session.commit()
    return jsonify(novo.to_dict()), 201


@app.route("/api/projetos/<int:pid>", methods=["PUT"])
@requer_perfil_api("admin", "gestor")
def api_editar_projeto(pid):
    p = Projeto.query.get_or_404(pid)
    body = request.get_json()
    for field in ("os", "atividade", "cliente", "solicitante", "descricao", "comentario"):
        if field in body:
            setattr(p, field, body[field].strip() if isinstance(body[field], str) else body[field])
    if "data_limite" in body:
        p.data_limite = date.fromisoformat(body["data_limite"])
    if "responsavel_id" in body:
        p.responsavel_id = body["responsavel_id"]
    db.session.commit()
    return jsonify(p.to_dict())


@app.route("/api/projetos/<int:pid>", methods=["DELETE"])
@requer_perfil_api("admin")
def api_deletar_projeto(pid):
    p = Projeto.query.get_or_404(pid)
    # Deletar histórico de fases
    ProjetoFase.query.filter_by(projeto_id=pid).delete()
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  API: KANBAN — Mover projeto entre fases
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/projetos/<int:pid>/mover-fase", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_mover_fase(pid):
    p = Projeto.query.get_or_404(pid)
    body = request.get_json()
    nova_fase_id = body.get("fase_id")
    if not nova_fase_id:
        return jsonify({"erro": "fase_id é obrigatório"}), 400
    nova_fase = Fase.query.get_or_404(nova_fase_id)
    # Fechar fase atual
    fase_ativa = ProjetoFase.query.filter_by(projeto_id=pid, data_saida=None).first()
    if fase_ativa:
        fase_ativa.data_saida = datetime.utcnow()
    # Abrir nova fase
    pf = ProjetoFase(
        projeto_id=pid,
        id_fase=nova_fase_id,
        responsavel_fase_id=body.get("responsavel_fase_id", p.responsavel_id),
    )
    db.session.add(pf)
    p.fase_atual_id = nova_fase_id
    if body.get("responsavel_fase_id"):
        p.responsavel_id = body["responsavel_fase_id"]
    db.session.commit()
    # Notificar equipe da nova fase
    if pf.funcionarios:
        notificar_mudanca_fase(p, nova_fase, pf.funcionarios)
    return jsonify(p.to_dict())


# ═══════════════════════════════════════════════════════════════════════════════
#  API: Atribuir funcionários a uma fase do projeto
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/projeto-fase/<int:pf_id>/atribuir", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_atribuir_funcionario(pf_id):
    pf = ProjetoFase.query.get_or_404(pf_id)
    body = request.get_json()
    func_id = body.get("funcionario_id")
    if not func_id:
        return jsonify({"erro": "funcionario_id é obrigatório"}), 400
    funcionario = Funcionario.query.get_or_404(func_id)
    fase = db.session.get(Fase, pf.id_fase)
    # Validar: funcionário deve ter uma das funções exigidas pela fase
    if fase and fase.funcoes_exigidas:
        funcoes_func = {f.id_funcao for f in funcionario.funcoes}
        funcoes_fase = {f.id_funcao for f in fase.funcoes_exigidas}
        if not funcoes_func.intersection(funcoes_fase):
            nomes_exigidas = ", ".join([f.nome_funcao for f in fase.funcoes_exigidas])
            return jsonify({
                "erro": f"O funcionário '{funcionario.nome}' não possui as funções exigidas por esta fase. Funções necessárias: {nomes_exigidas}"
            }), 400
    # Verificar se já está atribuído
    if funcionario in pf.funcionarios:
        return jsonify({"erro": "Funcionário já atribuído a esta fase"}), 409
    pf.funcionarios.append(funcionario)
    db.session.commit()
    # Notificar
    projeto = db.session.get(Projeto, pf.projeto_id)
    notificar_atribuicao(funcionario, projeto, fase)
    return jsonify(pf.to_dict())


@app.route("/api/projeto-fase/<int:pf_id>/remover", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_remover_funcionario_fase(pf_id):
    pf = ProjetoFase.query.get_or_404(pf_id)
    body = request.get_json()
    func_id = body.get("funcionario_id")
    funcionario = Funcionario.query.get_or_404(func_id)
    if funcionario in pf.funcionarios:
        pf.funcionarios.remove(funcionario)
        db.session.commit()
    return jsonify(pf.to_dict())


# ═══════════════════════════════════════════════════════════════════════════════
#  API: Kanban board data
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/kanban", methods=["GET"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_kanban():
    """Retorna dados do board Kanban: fases como colunas + projetos."""
    u = get_usuario_logado()
    fases = Fase.query.order_by(Fase.ordem).all()
    projetos_query = Projeto.query
    if u.perfil == "funcionario" and u.funcionario:
        func_id = u.funcionario.id_func
        projetos_query = projetos_query.join(ProjetoFase).join(
            projeto_fase_funcionario,
            projeto_fase_funcionario.c.id_projeto_fase == ProjetoFase.id,
        ).filter(
            projeto_fase_funcionario.c.id_funcionario == func_id
        ).distinct()
    projetos = projetos_query.all()
    # Montar board
    board = {}
    for fase in fases:
        board[fase.id_fase] = {
            **fase.to_dict(include_funcoes=False),
            "projetos": [],
        }
    # Projetos sem fase
    board["sem_fase"] = {"id": None, "nome": "Sem Fase", "cor": "#94a3b8", "ordem": -1, "projetos": []}
    for p in projetos:
        key = p.fase_atual_id if p.fase_atual_id and p.fase_atual_id in board else "sem_fase"
        board[key]["projetos"].append(p.to_dict())
    return jsonify(list(board.values()))


# ═══════════════════════════════════════════════════════════════════════════════
#  API: Funcionários elegíveis para uma fase
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/fases/<int:fid>/funcionarios-elegiveis", methods=["GET"])
@requer_perfil_api("admin", "gestor")
def api_funcionarios_elegiveis(fid):
    fase = Fase.query.get_or_404(fid)
    if not fase.funcoes_exigidas:
        # Se a fase não exige função, todos são elegíveis
        funcionarios = Funcionario.query.all()
    else:
        funcao_ids = [f.id_funcao for f in fase.funcoes_exigidas]
        funcionarios = Funcionario.query.join(
            funcionario_funcao
        ).filter(
            funcionario_funcao.c.id_funcao.in_(funcao_ids)
        ).distinct().all()
    return jsonify([f.to_dict() for f in funcionarios])


# ═══════════════════════════════════════════════════════════════════════════════
#  API: Comentários do projeto
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/projetos/<int:pid>/comentarios", methods=["GET"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_listar_comentarios(pid):
    Projeto.query.get_or_404(pid)
    comentarios = Comentario.query.filter_by(projeto_id=pid).order_by(
        Comentario.criado_em.desc()
    ).all()
    return jsonify([c.to_dict() for c in comentarios])


@app.route("/api/projetos/<int:pid>/comentarios", methods=["POST"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_criar_comentario(pid):
    Projeto.query.get_or_404(pid)
    u = get_usuario_logado()
    body = request.get_json()
    texto = body.get("texto", "").strip()
    if not texto:
        return jsonify({"erro": "Texto é obrigatório"}), 400
    comentario = Comentario(
        projeto_id=pid,
        usuario_id=u.id,
        texto=texto,
    )
    db.session.add(comentario)
    db.session.commit()
    return jsonify(comentario.to_dict()), 201


@app.route("/api/comentarios/<int:cid>", methods=["DELETE"])
@requer_perfil_api("admin")
def api_deletar_comentario(cid):
    c = Comentario.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  SEED: Criar admin padrão se não existir
# ═══════════════════════════════════════════════════════════════════════════════

def seed_admin():
    """Cria o admin padrão se nenhum admin existir."""
    if Usuario.query.filter_by(perfil="admin").count() == 0:
        admin = Usuario(
            nome="Administrador",
            email="admin@mind.com.br",
            hash_senha=bcrypt.generate_password_hash("admin123").decode("utf-8"),
            perfil="admin",
            trocar_senha=False,
        )
        db.session.add(admin)
        db.session.commit()
        print("[SEED] Usuário admin criado: admin@mind.com.br / admin123")


def seed_dados_reais():
    """Popula funções, funcionários, fases e usuários da Mind."""
    from seed_data import seed
    seed(bcrypt)


with app.app_context():
    seed_dados_reais()
    seed_admin()


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
