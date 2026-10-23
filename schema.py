"""
Migrações leves de schema, aplicadas na inicialização do app.

O projeto não usa Alembic: db.create_all() cria tabelas novas, mas não adiciona
colunas a tabelas existentes (SQLite em dev, MySQL em produção). Cada migração
abaixo verifica se já foi aplicada antes de rodar, então é seguro executar
ensure_schema() a cada boot — inclusive com vários workers subindo juntos.
"""
from sqlalchemy import inspect, text

from models import db


def _colunas(tabela):
    return {c["name"] for c in inspect(db.engine).get_columns(tabela)}


def _adicionar_coluna(tabela, coluna, ddl_tipo):
    """Adiciona a coluna se ainda não existir. Retorna True se esta chamada a criou."""
    if coluna in _colunas(tabela):
        return False
    try:
        db.session.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {ddl_tipo}"))
        db.session.commit()
        print(f"[SCHEMA] Coluna {tabela}.{coluna} criada.")
        return True
    except Exception:
        # Outro worker pode ter criado a coluna ao mesmo tempo
        db.session.rollback()
        if coluna in _colunas(tabela):
            return False
        raise


def ensure_schema():
    # Priorização numérica por funcionário-fase
    if _adicionar_coluna("objeto_fase_funcionario", "prioridade", "INTEGER NULL"):
        from prioridades import priorizacao_inicial
        priorizacao_inicial()
        db.session.commit()
        print("[SCHEMA] Filas de prioridade montadas a partir das flags antigas.")

    # Data de início prevista do módulo
    _adicionar_coluna("objetos", "data_inicio", "DATE NULL")
