from functools import wraps

from flask import session, redirect, url_for, jsonify


def get_usuario_logado():
    """Retorna o objeto do usuário logado ou None."""
    uid = session.get("usuario_id")
    if not uid:
        return None
    from models import Usuario
    return Usuario.query.get(uid)


def requer_login(f):
    """Decorator: exige que o usuário esteja logado."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        u = get_usuario_logado()
        if not u:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped


def requer_perfil(*perfis):
    """Decorator: exige que o usuário tenha um dos perfis listados.

    Uso:
        @requer_perfil("admin", "gestor")
        def minha_rota():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            u = get_usuario_logado()
            if not u or u.perfil not in perfis:
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def requer_perfil_api(*perfis):
    """Decorator para rotas de API: retorna 401/403 em JSON."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            u = get_usuario_logado()
            if not u:
                return jsonify({"erro": "Não autenticado"}), 401
            if u.perfil not in perfis:
                return jsonify({"erro": "Sem permissão"}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ─── Mapa de permissões ──────────────────────────────────────────────────────

PERMISSOES = {
    "admin": {
        "usuarios", "funcionarios", "funcoes", "fases", "projetos",
        "kanban", "configuracoes",
    },
    "gestor": {
        "funcionarios", "funcoes", "fases", "projetos", "kanban",
    },
    "funcionario": {
        "kanban",  # Só vê os projetos atribuídos a ele
    },
}


def usuario_pode(usuario, recurso):
    """Verifica se o usuário tem acesso a um recurso."""
    return recurso in PERMISSOES.get(usuario.perfil, set())


def get_abas_usuario(usuario):
    """Retorna lista de abas permitidas para o usuário no frontend."""
    mapa = {
        "admin": ["kanban", "projetos", "funcionarios", "funcoes", "fases", "usuarios", "configuracoes"],
        "gestor": ["kanban", "projetos", "funcionarios", "funcoes", "fases"],
        "funcionario": ["kanban"],
    }
    return mapa.get(usuario.perfil, [])
