from datetime import datetime, date

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_bcrypt import Bcrypt
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from models import (
    db, configure_db, Usuario, Funcionario, Funcao, Fase,
    Projeto, Objeto, ObjetoFase, Comentario, funcionario_funcao, fase_funcao,
    objeto_fase_funcionario,
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
    include_inativas = request.args.get("todas") == "1"
    if include_inativas:
        fases = Fase.query.order_by(Fase.ordem).all()
    else:
        fases = Fase.query.filter(db.or_(Fase.ativa == True, Fase.ativa == None)).order_by(Fase.ordem).all()
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
    if "ativa" in body:
        f.ativa = bool(body["ativa"])
    db.session.commit()
    return jsonify(f.to_dict())


@app.route("/api/fases/<int:fid>", methods=["DELETE"])
@requer_perfil_api("admin", "gestor")
def api_deletar_fase(fid):
    f = Fase.query.get_or_404(fid)
    
    # Verificar se a fase possui projetos atualmente nela
    em_uso_agora = Projeto.query.filter_by(fase_atual_id=fid).first()
    
    if em_uso_agora:
        return jsonify({"erro": "Não é possível excluir esta fase pois existem cards atualmente nela. Mova os cards primeiro."}), 400
    
    # Verificar se há histórico
    em_historico = ProjetoFase.query.filter_by(id_fase=fid).first()
    
    if em_historico:
        # Soft delete: desativar a fase
        f.ativa = False
        db.session.commit()
        return jsonify({"ok": True, "modo": "desativada", "msg": "Fase desativada (possui histórico). Não aparecerá mais no Kanban."})
    else:
        # Hard delete: sem histórico, pode remover de verdade
        try:
            db.session.execute(fase_funcao.delete().where(fase_funcao.c.id_fase == fid))
            db.session.delete(f)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({"erro": f"Erro ao excluir fase: {str(e)}"}), 500
        return jsonify({"ok": True, "modo": "excluida"})


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
#  API: PROJETOS & OBJETOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/projetos", methods=["GET"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_listar_projetos():
    projetos = Projeto.query.all()
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

    objetos_data = body.get("objetos", [])
    if not objetos_data:
        return jsonify({"erro": "Ao menos 1 módulo (objeto) é obrigatório."}), 400
    if len(objetos_data) > 6:
        return jsonify({"erro": "Limite máximo de 6 módulos (objetos) por OS."}), 400

    novo_proj = Projeto(
        os=os_code,
        cliente=body.get("cliente", ""),
        solicitante=body.get("solicitante", ""),
        descricao=body.get("descricao", ""),
        comentario=body.get("comentario", ""),
        data_limite=date.fromisoformat(data_limite),
        responsavel_id=body.get("responsavel_id"),
    )
    db.session.add(novo_proj)
    db.session.flush()

    for obj_data in objetos_data:
        fase_id = obj_data.get("fase_id")
        
        # O data_limite do módulo
        obj_data_limite_str = obj_data.get("data_limite")
        obj_data_limite = date.fromisoformat(obj_data_limite_str) if obj_data_limite_str else novo_proj.data_limite
        
        # O data limite da fase (se diferente, mas na UI só tem um, então usaremos o do módulo)
        data_limite_fase = obj_data_limite
        
        # Se não enviou nome, usa nome padrão
        nome_obj = obj_data.get("nome", "").strip() or "Módulo 1"

        novo_obj = Objeto(
            projeto_id=novo_proj.projeto_id,
            nome=nome_obj,
            descricao=obj_data.get("descricao", ""),
            data_limite=obj_data_limite,
            responsavel_id=obj_data.get("responsavel_id", novo_proj.responsavel_id),
            fase_atual_id=fase_id
        )
        db.session.add(novo_obj)
        db.session.flush()

        if fase_id:
            of = ObjetoFase(
                objeto_id=novo_obj.id,
                id_fase=fase_id,
                responsavel_fase_id=novo_obj.responsavel_id,
                data_limite=data_limite_fase
            )
            db.session.add(of)

    db.session.commit()
    return jsonify(novo_proj.to_dict()), 201


@app.route("/api/projetos/<int:pid>", methods=["PUT"])
@requer_perfil_api("admin", "gestor")
def api_editar_projeto(pid):
    p = Projeto.query.get_or_404(pid)
    body = request.get_json()
    for field in ("os", "cliente", "solicitante", "descricao", "comentario"):
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
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  API: OBJETOS (Cards Individuais)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/objetos/<int:oid>", methods=["GET"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_detalhe_objeto(oid):
    o = Objeto.query.get_or_404(oid)
    return jsonify(o.to_dict(include_historico=True))


@app.route("/api/objetos/<int:oid>", methods=["PUT"])
@requer_perfil_api("admin", "gestor")
def api_editar_objeto(oid):
    o = Objeto.query.get_or_404(oid)
    body = request.get_json()
    if "nome" in body:
        o.nome = body["nome"].strip()
    if "descricao" in body:
        o.descricao = body["descricao"].strip()
    if "data_limite" in body:
        o.data_limite = date.fromisoformat(body["data_limite"])
    if "responsavel_id" in body:
        o.responsavel_id = body["responsavel_id"]
    db.session.commit()
    return jsonify(o.to_dict())


@app.route("/api/projetos/<int:pid>/objetos", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_criar_objeto(pid):
    p = Projeto.query.get_or_404(pid)
    
    if p.objetos.count() >= 6:
        return jsonify({"erro": "Limite máximo de 6 objetos por projeto atingido."}), 400

    body = request.get_json()
    nome = body.get("nome", "").strip()
    if not nome:
        return jsonify({"erro": "Nome do módulo é obrigatório"}), 400
        
    fase_id = body.get("fase_id")
    data_limite_str = body.get("data_limite")
    data_limite = date.fromisoformat(data_limite_str) if data_limite_str else p.data_limite
    responsavel_id = body.get("responsavel_id", p.responsavel_id)

    novo_obj = Objeto(
        projeto_id=pid,
        nome=nome,
        descricao=body.get("descricao", ""),
        data_limite=data_limite,
        responsavel_id=responsavel_id,
        fase_atual_id=fase_id
    )
    db.session.add(novo_obj)
    db.session.flush()

    if fase_id:
        data_limite_fase_str = body.get("fase_data_limite")
        data_limite_fase = date.fromisoformat(data_limite_fase_str) if data_limite_fase_str else None
        of = ObjetoFase(
            objeto_id=novo_obj.id,
            id_fase=fase_id,
            responsavel_fase_id=responsavel_id,
            data_limite=data_limite_fase
        )
        db.session.add(of)

    db.session.commit()
    return jsonify(novo_obj.to_dict()), 201


@app.route("/api/objetos/<int:oid>", methods=["DELETE"])
@requer_perfil_api("admin", "gestor")
def api_deletar_objeto(oid):
    o = Objeto.query.get_or_404(oid)
    # Verifica se é o único objeto da OS. Se sim, não deve permitir (ou excluir a OS toda)
    if o.projeto.objetos.count() <= 1:
        return jsonify({"erro": "Não é possível excluir o único módulo de uma OS. Exclua a OS inteira."}), 400
        
    db.session.delete(o)
    db.session.commit()
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  API: KANBAN — Mover objeto entre fases
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/objetos/<int:oid>/mover-fase", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_mover_fase(oid):
    o = Objeto.query.get_or_404(oid)
    body = request.get_json()
    nova_fase_id = body.get("fase_id")
    if not nova_fase_id:
        return jsonify({"erro": "fase_id é obrigatório"}), 400
    nova_fase = Fase.query.get_or_404(nova_fase_id)
    if nova_fase.ativa == False:
        return jsonify({"erro": "Esta fase está desativada e não pode receber novos cards."}), 400
    
    # Fechar fase atual
    fase_ativa = ObjetoFase.query.filter_by(objeto_id=oid, data_saida=None).first()
    if fase_ativa:
        fase_ativa.data_saida = datetime.utcnow()
        
    data_limite_fase_str = body.get("data_limite_fase")
    data_limite_fase = date.fromisoformat(data_limite_fase_str) if data_limite_fase_str else None
    
    # Abrir nova fase
    of = ObjetoFase(
        objeto_id=oid,
        id_fase=nova_fase_id,
        responsavel_fase_id=body.get("responsavel_fase_id", o.responsavel_id),
        data_limite=data_limite_fase
    )
    db.session.add(of)
    o.fase_atual_id = nova_fase_id
    if body.get("responsavel_fase_id"):
        o.responsavel_id = body["responsavel_fase_id"]
    db.session.commit()
    
    # Notificar equipe da nova fase
    if of.funcionarios:
        notificar_mudanca_fase(o.projeto, o, nova_fase, of.funcionarios)
    return jsonify(o.to_dict())


# ═══════════════════════════════════════════════════════════════════════════════
#  API: Atribuir funcionários a uma fase do objeto
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/objeto-fase/<int:of_id>/atribuir", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_atribuir_funcionario(of_id):
    of = ObjetoFase.query.get_or_404(of_id)
    body = request.get_json()
    func_id = body.get("funcionario_id")
    if not func_id:
        return jsonify({"erro": "funcionario_id é obrigatório"}), 400
    funcionario = Funcionario.query.get_or_404(func_id)
    fase = db.session.get(Fase, of.id_fase)
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
    if funcionario in of.funcionarios:
        return jsonify({"erro": "Funcionário já atribuído a esta fase"}), 409
    of.funcionarios.append(funcionario)
    db.session.commit()
    # Notificar
    objeto = db.session.get(Objeto, of.objeto_id)
    notificar_atribuicao(funcionario, objeto.projeto, fase, objeto)
    return jsonify(of.to_dict())


@app.route("/api/objeto-fase/<int:of_id>/remover", methods=["POST"])
@requer_perfil_api("admin", "gestor")
def api_remover_funcionario_fase(of_id):
    of = ObjetoFase.query.get_or_404(of_id)
    body = request.get_json()
    func_id = body.get("funcionario_id")
    funcionario = Funcionario.query.get_or_404(func_id)
    if funcionario in of.funcionarios:
        of.funcionarios.remove(funcionario)
        db.session.commit()
    return jsonify(of.to_dict())


# ═══════════════════════════════════════════════════════════════════════════════
#  API: Kanban board data
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/kanban", methods=["GET"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_kanban():
    """Retorna dados do board Kanban: fases como colunas + objetos."""
    u = get_usuario_logado()
    fases = Fase.query.filter(db.or_(Fase.ativa == True, Fase.ativa == None)).order_by(Fase.ordem).all()
    
    objetos_query = Objeto.query
    if u.perfil == "funcionario" and u.funcionario:
        func_id = u.funcionario.id_func
        objetos_query = objetos_query.join(ObjetoFase).join(
            objeto_fase_funcionario,
            objeto_fase_funcionario.c.id_objeto_fase == ObjetoFase.id,
        ).filter(
            objeto_fase_funcionario.c.id_funcionario == func_id
        ).distinct()
    
    objetos = objetos_query.all()
    
    # Montar board
    board = {}
    for fase in fases:
        board[fase.id_fase] = {
            **fase.to_dict(include_funcoes=False),
            "projetos": [], # Mantemos a chave "projetos" por compatibilidade com JS (ou mudamos para objetos no JS)
            "objetos": [],
        }
    board["sem_fase"] = {"id": None, "nome": "Sem Fase", "cor": "#94a3b8", "ordem": -1, "projetos": [], "objetos": []}
    
    for o in objetos:
        key = o.fase_atual_id if o.fase_atual_id and o.fase_atual_id in board else "sem_fase"
        board[key]["objetos"].append(o.to_dict())
        # Alias "projetos" = "objetos" pra evitar quebrar o JS imediatamente, 
        # embora o ideal seja renomear no frontend.
        board[key]["projetos"].append(o.to_dict())
        
    return jsonify(list(board.values()))


# ═══════════════════════════════════════════════════════════════════════════════
#  API: Funcionários elegíveis para uma fase
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/fases/<int:fid>/funcionarios-elegiveis", methods=["GET"])
@requer_perfil_api("admin", "gestor")
def api_funcionarios_elegiveis(fid):
    fase = Fase.query.get_or_404(fid)
    if not fase.funcoes_exigidas:
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
#  API: Comentários
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/objetos/<int:oid>/comentarios", methods=["GET"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_listar_comentarios_objeto(oid):
    Objeto.query.get_or_404(oid)
    comentarios = Comentario.query.filter_by(objeto_id=oid).order_by(
        Comentario.criado_em.desc()
    ).all()
    return jsonify([c.to_dict() for c in comentarios])

@app.route("/api/objetos/<int:oid>/comentarios", methods=["POST"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_criar_comentario_objeto(oid):
    Objeto.query.get_or_404(oid)
    u = get_usuario_logado()
    body = request.get_json()
    texto = body.get("texto", "").strip()
    if not texto:
        return jsonify({"erro": "Texto é obrigatório"}), 400
    comentario = Comentario(
        objeto_id=oid,
        usuario_id=u.id,
        texto=texto,
    )
    db.session.add(comentario)
    db.session.commit()
    return jsonify(comentario.to_dict()), 201

@app.route("/api/projetos/<int:pid>/comentarios", methods=["GET"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_listar_comentarios_projeto(pid):
    Projeto.query.get_or_404(pid)
    comentarios = Comentario.query.filter_by(projeto_id=pid).order_by(
        Comentario.criado_em.desc()
    ).all()
    return jsonify([c.to_dict() for c in comentarios])

@app.route("/api/projetos/<int:pid>/comentarios", methods=["POST"])
@requer_perfil_api("admin", "gestor", "funcionario")
def api_criar_comentario_projeto(pid):
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
