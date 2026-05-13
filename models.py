from datetime import datetime, date

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def configure_db(app):
    """Inicializa o SQLAlchemy com as configurações do app."""
    db.init_app(app)


# ─── Tabela associativa: funcionario <-> funcao (N:N) ─────────────────────────

funcionario_funcao = db.Table(
    "funcionario_funcao",
    db.Column("id_funcionario", db.Integer, db.ForeignKey("funcionarios.id_func"), primary_key=True),
    db.Column("id_funcao", db.Integer, db.ForeignKey("funcoes.id_funcao"), primary_key=True),
)

# ─── Tabela associativa: fase <-> funcao (N:N) ───────────────────────────────

fase_funcao = db.Table(
    "fase_funcao",
    db.Column("id_fase", db.Integer, db.ForeignKey("fases.id_fase"), primary_key=True),
    db.Column("id_funcao", db.Integer, db.ForeignKey("funcoes.id_funcao"), primary_key=True),
)

# ─── Tabela associativa: projeto_fase <-> funcionario (N:N) ──────────────────

projeto_fase_funcionario = db.Table(
    "projeto_fase_funcionario",
    db.Column("id_projeto_fase", db.Integer, db.ForeignKey("projeto_fase.id"), primary_key=True),
    db.Column("id_funcionario", db.Integer, db.ForeignKey("funcionarios.id_func"), primary_key=True),
    db.Column("atribuido_em", db.DateTime, default=datetime.utcnow),
)


# ─── Usuario (login/autenticação) ────────────────────────────────────────────

class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    hash_senha = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(20), nullable=False, default="funcionario")  # admin | gestor | funcionario
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    trocar_senha = db.Column(db.Boolean, default=False)

    # Relacionamento com funcionario (1:1 opcional)
    funcionario = db.relationship("Funcionario", backref="usuario", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "email": self.email,
            "perfil": self.perfil,
            "ativo": self.ativo,
            "criado_em": self.criado_em.isoformat() if self.criado_em else "",
            "trocar_senha": self.trocar_senha,
            "funcionario_id": self.funcionario.id_func if self.funcionario else None,
        }


# ─── Funcionario ──────────────────────────────────────────────────────────────

class Funcionario(db.Model):
    __tablename__ = "funcionarios"
    id_func = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)

    # N:N com funcoes
    funcoes = db.relationship("Funcao", secondary=funcionario_funcao, backref="funcionarios", lazy="subquery")

    # Projetos onde é responsável geral
    projetos_responsavel = db.relationship("Projeto", backref="responsavel", foreign_keys="Projeto.responsavel_id")

    def to_dict(self, include_funcoes=True):
        d = {
            "id": self.id_func,
            "nome": self.nome,
            "email": self.email,
            "usuario_id": self.usuario_id,
        }
        if include_funcoes:
            d["funcoes"] = [f.to_dict() for f in self.funcoes]
        return d


# ─── Funcao ───────────────────────────────────────────────────────────────────

class Funcao(db.Model):
    __tablename__ = "funcoes"
    id_funcao = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome_funcao = db.Column(db.String(100), unique=True, nullable=False)

    def to_dict(self):
        return {
            "id": self.id_funcao,
            "nome": self.nome_funcao,
        }


# ─── Fase ─────────────────────────────────────────────────────────────────────

class Fase(db.Model):
    __tablename__ = "fases"
    id_fase = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome_fase = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(255), nullable=True)
    cor = db.Column(db.String(7), default="#6366f1")  # Hex color para o Kanban
    ordem = db.Column(db.Integer, default=0)  # Posição sugerida

    # N:N com funcoes (funções exigidas por esta fase)
    funcoes_exigidas = db.relationship("Funcao", secondary=fase_funcao, backref="fases", lazy="subquery")

    def to_dict(self, include_funcoes=True):
        d = {
            "id": self.id_fase,
            "nome": self.nome_fase,
            "descricao": self.descricao or "",
            "cor": self.cor,
            "ordem": self.ordem,
        }
        if include_funcoes:
            d["funcoes_exigidas"] = [f.to_dict() for f in self.funcoes_exigidas]
        return d


# ─── Projeto ──────────────────────────────────────────────────────────────────

class Projeto(db.Model):
    __tablename__ = "projetos"
    projeto_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    os = db.Column(db.String(50), unique=True, nullable=False)  # Ordem de Serviço
    atividade = db.Column(db.String(200), nullable=True)
    cliente = db.Column(db.String(150), nullable=True)
    solicitante = db.Column(db.String(150), nullable=True)
    descricao = db.Column(db.Text, nullable=True)
    comentario = db.Column(db.Text, nullable=True)
    data_inclusao = db.Column(db.Date, default=date.today)
    data_limite = db.Column(db.Date, nullable=False)
    responsavel_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id_func"), nullable=True)
    fase_atual_id = db.Column(db.Integer, db.ForeignKey("fases.id_fase"), nullable=True)

    # Relacionamentos
    fase_atual = db.relationship("Fase", foreign_keys=[fase_atual_id])
    historico_fases = db.relationship("ProjetoFase", backref="projeto", lazy="dynamic",
                                      order_by="ProjetoFase.data_entrada.desc()")

    def dias_restantes_sla(self):
        """Retorna os dias restantes até o prazo. Negativo = atraso."""
        if not self.data_limite:
            return None
        return (self.data_limite - date.today()).days

    def sla_flag(self):
        """Retorna a flag de SLA: 'Dentro do SLA' ou 'Fora do SLA'."""
        dias = self.dias_restantes_sla()
        if dias is None:
            return "Sem prazo"
        return "Dentro do SLA" if dias >= 0 else "Fora do SLA"

    def dias_na_fase_atual(self):
        """Retorna quantos dias o projeto está na fase atual."""
        fase_ativa = ProjetoFase.query.filter_by(
            projeto_id=self.projeto_id, data_saida=None
        ).first()
        if not fase_ativa:
            return 0
        return (datetime.utcnow() - fase_ativa.data_entrada).days

    def to_dict(self, include_historico=False):
        d = {
            "id": self.projeto_id,
            "os": self.os,
            "atividade": self.atividade or "",
            "cliente": self.cliente or "",
            "solicitante": self.solicitante or "",
            "descricao": self.descricao or "",
            "comentario": self.comentario or "",
            "data_inclusao": self.data_inclusao.isoformat() if self.data_inclusao else "",
            "data_limite": self.data_limite.isoformat() if self.data_limite else "",
            "responsavel_id": self.responsavel_id,
            "responsavel_nome": self.responsavel.nome if self.responsavel else "",
            "fase_atual_id": self.fase_atual_id,
            "fase_atual_nome": self.fase_atual.nome_fase if self.fase_atual else "",
            "fase_atual_cor": self.fase_atual.cor if self.fase_atual else "#94a3b8",
            "sla": {
                "flag": self.sla_flag(),
                "dias_restantes": self.dias_restantes_sla(),
                "dias_na_fase": self.dias_na_fase_atual(),
            },
        }
        if include_historico:
            d["historico"] = [h.to_dict() for h in self.historico_fases.all()]
            d["comentarios"] = [c.to_dict() for c in Comentario.query.filter_by(
                projeto_id=self.projeto_id
            ).order_by(Comentario.criado_em.desc()).all()]
        return d


# ─── ProjetoFase (histórico de fases do projeto) ─────────────────────────────

class ProjetoFase(db.Model):
    __tablename__ = "projeto_fase"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey("projetos.projeto_id"), nullable=False)
    id_fase = db.Column(db.Integer, db.ForeignKey("fases.id_fase"), nullable=False)
    data_entrada = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    data_saida = db.Column(db.DateTime, nullable=True)  # NULL = fase ativa
    responsavel_fase_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id_func"), nullable=True)

    # Relacionamentos
    fase = db.relationship("Fase")
    responsavel_fase = db.relationship("Funcionario", foreign_keys=[responsavel_fase_id])
    funcionarios = db.relationship("Funcionario", secondary=projeto_fase_funcionario,
                                    backref="fases_atribuidas", lazy="subquery")

    def dias_na_fase(self):
        fim = self.data_saida or datetime.utcnow()
        return (fim - self.data_entrada).days

    def to_dict(self):
        return {
            "id": self.id,
            "fase_id": self.id_fase,
            "fase_nome": self.fase.nome_fase if self.fase else "",
            "fase_cor": self.fase.cor if self.fase else "#94a3b8",
            "data_entrada": self.data_entrada.isoformat() if self.data_entrada else "",
            "data_saida": self.data_saida.isoformat() if self.data_saida else None,
            "dias_na_fase": self.dias_na_fase(),
            "responsavel_fase_id": self.responsavel_fase_id,
            "responsavel_fase_nome": self.responsavel_fase.nome if self.responsavel_fase else "",
            "funcionarios": [f.to_dict(include_funcoes=False) for f in self.funcionarios],
        }


# ─── Comentario (independente de fase) ───────────────────────────────────────

class Comentario(db.Model):
    __tablename__ = "comentarios"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    projeto_id = db.Column(db.Integer, db.ForeignKey("projetos.projeto_id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relacionamentos
    usuario = db.relationship("Usuario")

    def to_dict(self):
        return {
            "id": self.id,
            "projeto_id": self.projeto_id,
            "usuario_id": self.usuario_id,
            "autor_nome": self.usuario.nome if self.usuario else "",
            "texto": self.texto,
            "criado_em": self.criado_em.isoformat() if self.criado_em else "",
        }
