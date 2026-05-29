import sys

def update_app():
    with open('app.py', 'r') as f:
        content = f.read()

    # Find where API: PROJETOS starts
    start_str = "# ═══════════════════════════════════════════════════════════════════════════════\n#  API: PROJETOS"
    end_str = "# ═══════════════════════════════════════════════════════════════════════════════\n#  SEED: Criar admin padrão se não existir"
    
    start_idx = content.find(start_str)
    end_idx = content.find(end_str)

    if start_idx == -1 or end_idx == -1:
        print("Could not find delimiters.")
        return

    new_api_code = """# ═══════════════════════════════════════════════════════════════════════════════
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
        data_limite_fase_str = obj_data.get("fase_data_limite")
        data_limite_fase = date.fromisoformat(data_limite_fase_str) if data_limite_fase_str else None
        
        # Se não enviou nome, usa nome padrão
        nome_obj = obj_data.get("nome", "").strip() or "Módulo 1"

        novo_obj = Objeto(
            projeto_id=novo_proj.projeto_id,
            nome=nome_obj,
            descricao=obj_data.get("descricao", ""),
            data_limite=data_limite_fase or novo_proj.data_limite,
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
        notificar_mudanca_fase(o.projeto, nova_fase, of.funcionarios) # TODO update notifications.py
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
    notificar_atribuicao(funcionario, objeto.projeto, fase)
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
    \"\"\"Retorna dados do board Kanban: fases como colunas + objetos.\"\"\"
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

"""

    new_content = content[:start_idx] + new_api_code + "\n" + content[end_idx:]
    with open('app.py', 'w') as f:
        f.write(new_content)
    print("app.py updated successfully.")

if __name__ == "__main__":
    update_app()
