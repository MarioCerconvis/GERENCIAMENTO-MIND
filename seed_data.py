"""
seed_data.py — Popula o banco com dados reais da Mind
"""
from models import db, Usuario, Funcionario, Funcao, Fase


def seed(bcrypt):
    """Popula o banco com dados reais. Deve ser chamado dentro de app_context."""
    # Verifica se já foi populado
    if Funcao.query.count() > 0:
        print("[SEED] Banco já possui dados. Pulando seed de dados reais.")
        return

    print("[SEED] Populando banco com dados reais da Mind...")

    # ═══ FUNÇÕES ═══════════════════════════════════════════════════════
    funcoes_nomes = [
        "Diretor",
        "Web Designer",
        "Gerente",
        "Redator",
        "Revisor",
        "Tradutor",
        "Diagramação",
        "Gravação de Locução",
    ]
    funcoes = {}
    for nome in funcoes_nomes:
        f = Funcao(nome_funcao=nome)
        db.session.add(f)
        db.session.flush()
        funcoes[nome] = f
        print(f"  ✅ Função: {nome}")

    # ═══ FUNCIONÁRIOS ══════════════════════════════════════════════════
    funcionarios_data = [
        # (nome, email, [funções], terceiro?)
        ("Eduardo", "eduardo@mind.com.br", ["Diretor"], False),
        ("Carol", "carol@mind.com.br", ["Web Designer"], False),
        ("John", "john@mind.com.br", ["Gerente"], False),
        ("Renato", "renato@mind.com.br", ["Redator", "Revisor", "Tradutor"], False),
        ("Lucas", "lucas@mind.com.br", ["Redator", "Revisor", "Tradutor"], False),
        ("Luiza", "luiza@mind.com.br", ["Revisor", "Tradutor"], False),
        ("Marina", "marina@mind.com.br", ["Revisor", "Tradutor"], False),
        ("Juliana", "juliana@mind.com.br", ["Diagramação"], False),
        ("Beatriz", "beatriz@mind.com.br", ["Diagramação"], False),
        ("Gustavo", "gustavo@mind.com.br", ["Web Designer"], False),
        ("Leandro", "leandro@mind.com.br", ["Diagramação"], False),
        ("Petter", "petter@mind.com.br", ["Revisor", "Tradutor"], False),
        ("Gabriela (Terceiros)", "gabriela@terceiros.com.br", ["Gravação de Locução"], True),
        ("Marcos - Eco Voz (Terceiros)", "marcos.ecovoz@terceiros.com.br", ["Gravação de Locução"], True),
        ("Ricardo (Terceiros)", "ricardo@terceiros.com.br", ["Tradutor"], True),
    ]

    for nome, email, func_nomes, terceiro in funcionarios_data:
        func = Funcionario(nome=nome, email=email)
        func.funcoes = [funcoes[fn] for fn in func_nomes]
        db.session.add(func)
        tag = " [TERCEIRO]" if terceiro else ""
        funcoes_str = ", ".join(func_nomes)
        print(f"  ✅ Funcionário: {nome} ({funcoes_str}){tag}")

    # ═══ USUÁRIOS ══════════════════════════════════════════════════════
    # Criar contas de login para os internos (não-terceiros)
    usuarios_data = [
        ("Eduardo", "eduardo@mind.com.br", "admin"),
        ("John", "john@mind.com.br", "gestor"),
        ("Carol", "carol@mind.com.br", "funcionario"),
        ("Renato", "renato@mind.com.br", "funcionario"),
        ("Lucas", "lucas@mind.com.br", "funcionario"),
        ("Luiza", "luiza@mind.com.br", "funcionario"),
        ("Marina", "marina@mind.com.br", "funcionario"),
        ("Juliana", "juliana@mind.com.br", "funcionario"),
        ("Beatriz", "beatriz@mind.com.br", "funcionario"),
        ("Gustavo", "gustavo@mind.com.br", "funcionario"),
        ("Leandro", "leandro@mind.com.br", "funcionario"),
        ("Petter", "petter@mind.com.br", "funcionario"),
    ]

    db.session.flush()  # Garantir IDs dos funcionários

    for nome, email, perfil in usuarios_data:
        # Não criar se já existe (admin@mind.com.br do seed original)
        if Usuario.query.filter_by(email=email).first():
            continue
        u = Usuario(
            nome=nome,
            email=email,
            perfil=perfil,
            hash_senha=bcrypt.generate_password_hash("Trocar@123").decode("utf-8"),
            trocar_senha=True,
        )
        db.session.add(u)
        db.session.flush()
        # Vincular ao funcionário
        func = Funcionario.query.filter_by(email=email).first()
        if func:
            func.usuario_id = u.id
        print(f"  ✅ Usuário: {nome} ({email}) — perfil: {perfil}")

    # ═══ FASES ═════════════════════════════════════════════════════════
    fases_data = [
        # (nome, cor, ordem, [funções exigidas])
        ("Revisão Ortográfica", "#8b5cf6", 1,
         ["Revisor"]),
        ("Criação de Layout e Diagramação", "#3b82f6", 2,
         ["Web Designer", "Diagramação"]),
        ("Revisão da Diagramação e Ancoragem", "#f59e0b", 3,
         ["Revisor"]),
        ("Correção", "#ef4444", 4,
         ["Redator", "Revisor"]),
        ("Envio ao Cliente", "#06b6d4", 5,
         []),  # Sem restrição de função
        ("Atualização da Diagramação", "#10b981", 6,
         ["Diagramação"]),
        ("Revisão da Atualização e Reancoragem", "#6366f1", 7,
         ["Revisor"]),
    ]

    for nome, cor, ordem, func_nomes in fases_data:
        fase = Fase(
            nome_fase=nome,
            cor=cor,
            ordem=ordem,
            descricao="",
        )
        if func_nomes:
            fase.funcoes_exigidas = [funcoes[fn] for fn in func_nomes]
        db.session.add(fase)
        funcoes_str = ", ".join(func_nomes) if func_nomes else "Sem restrição"
        print(f"  ✅ Fase {ordem}: {nome} (exige: {funcoes_str})")

    db.session.commit()

    print()
    print("═══════════════════════════════════════════════════════")
    print(f"  Seed concluído!")
    print(f"  {len(funcoes_nomes)} funções")
    print(f"  {len(funcionarios_data)} funcionários (3 terceiros)")
    print(f"  {len(usuarios_data)} contas de usuário")
    print(f"  {len(fases_data)} fases")
    print(f"  Senha padrão: Trocar@123 (troca obrigatória no 1o login)")
    print("═══════════════════════════════════════════════════════")
