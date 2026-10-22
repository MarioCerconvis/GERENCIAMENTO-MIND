"""
Priorização numérica por funcionário.

Cada funcionário tem uma fila com os seus trabalhos atuais, numerada de 1
(mais importante) a n (n = quantidade de trabalhos atuais dele). Um trabalho
atual é uma linha de objeto_fase_funcionario cuja fase está ativa
(data_saida NULL) e que o funcionário ainda não aprovou.

Invariante: as prioridades dos trabalhos atuais de um funcionário são sempre
exatamente 1..n, sem buracos nem repetições. Toda rota que muda a equipe de
uma fase, encerra uma fase ou registra uma aprovação chama
renumerar_prioridades() para os funcionários afetados — trabalhos novos entram
no fim da fila, e os que saem liberam a posição.
"""
from sqlalchemy import case

from models import db, ObjetoFase, objeto_fase_funcionario as off


class FilaDesatualizada(ValueError):
    """A ordem enviada não corresponde aos trabalhos atuais do funcionário."""


def _ordenacao():
    # NULL por último (cross-DB), depois prioridade, depois ordem de atribuição
    return (
        case((off.c.prioridade.is_(None), 1), else_=0),
        off.c.prioridade,
        off.c.atribuido_em,
        off.c.id_objeto_fase,
    )


def _filtro_trabalhos_atuais(func_id):
    return db.and_(
        off.c.id_funcionario == func_id,
        off.c.aprovado_em.is_(None),
        off.c.id_objeto_fase.in_(
            db.select(ObjetoFase.id).where(ObjetoFase.data_saida.is_(None))
        ),
    )


def fila_funcionario(func_id):
    """IDs de ObjetoFase dos trabalhos atuais do funcionário, na ordem de prioridade."""
    rows = db.session.execute(
        db.select(off.c.id_objeto_fase)
        .where(_filtro_trabalhos_atuais(func_id))
        .order_by(*_ordenacao())
    ).fetchall()
    return [r.id_objeto_fase for r in rows]


def _gravar_ordem(func_id, ordem_ids):
    for posicao, of_id in enumerate(ordem_ids, start=1):
        db.session.execute(
            off.update()
            .where(off.c.id_funcionario == func_id, off.c.id_objeto_fase == of_id)
            .values(prioridade=posicao)
        )
    # Trabalhos que deixaram de ser atuais não ocupam posição na fila
    db.session.execute(
        off.update()
        .where(
            off.c.id_funcionario == func_id,
            off.c.prioridade.isnot(None),
            db.not_(_filtro_trabalhos_atuais(func_id)),
        )
        .values(prioridade=None)
    )


def renumerar_prioridades(*func_ids):
    """Recompacta a fila (1..n) de cada funcionário informado.

    Mantém a ordem relativa existente; trabalhos sem prioridade (recém-atribuídos)
    vão para o fim, na ordem em que foram atribuídos. Não faz commit.
    """
    db.session.flush()
    for func_id in {f for f in func_ids if f}:
        _gravar_ordem(func_id, fila_funcionario(func_id))


def definir_ordem(func_id, ordem_ids):
    """Substitui a ordem da fila do funcionário. Não faz commit.

    `ordem_ids` deve conter exatamente os trabalhos atuais dele; caso contrário a
    fila mudou desde que a tela foi carregada e a ordem é recusada.
    """
    atual = fila_funcionario(func_id)
    try:
        ordem_ids = [int(i) for i in ordem_ids]
    except (TypeError, ValueError):
        raise FilaDesatualizada("Ordem inválida.")
    if len(ordem_ids) != len(set(ordem_ids)) or set(ordem_ids) != set(atual):
        raise FilaDesatualizada(
            "A fila deste funcionário mudou desde que a tela foi carregada. Recarregue e tente novamente."
        )
    _gravar_ordem(func_id, ordem_ids)


def mover_para_posicao(func_id, objeto_fase_id, posicao):
    """Move um trabalho para a posição informada (1..n), deslocando os demais. Não faz commit."""
    fila = fila_funcionario(func_id)
    if objeto_fase_id not in fila:
        raise FilaDesatualizada("Este trabalho não está na fila atual do funcionário.")
    posicao = max(1, min(int(posicao), len(fila)))
    fila.remove(objeto_fase_id)
    fila.insert(posicao - 1, objeto_fase_id)
    _gravar_ordem(func_id, fila)


def total_trabalhos(func_id):
    return db.session.execute(
        db.select(db.func.count()).select_from(off).where(_filtro_trabalhos_atuais(func_id))
    ).scalar()


def prioridades_da_fase(fase_ativa):
    """Prioridade do card na fila de cada funcionário da fase ativa (para o to_dict)."""
    rows = {r.id_funcionario: r for r in fase_ativa._get_aprovacao_rows()}
    resultado = []
    for f in fase_ativa.funcionarios:
        row = rows.get(f.id_func)
        aprovado = bool(row and row.aprovado_em)
        resultado.append({
            "funcionario_id": f.id_func,
            "nome": f.nome,
            "prioridade": None if aprovado or not row else row.prioridade,
            "total": total_trabalhos(f.id_func),
            "aprovado": aprovado,
        })
    return resultado


def priorizacao_inicial():
    """Monta as filas a partir das flags antigas (Urgente > Prioridade > Importante > sem flag),
    respeitando a ordem manual do kanban e, por fim, a data de atribuição.
    Usada uma única vez, quando a coluna de prioridade é criada."""
    from models import Objeto

    func_ids = [r[0] for r in db.session.execute(
        db.select(off.c.id_funcionario).distinct()
    ).fetchall()]
    for func_id in func_ids:
        rows = db.session.execute(
            db.select(off.c.id_objeto_fase)
            .join(ObjetoFase, ObjetoFase.id == off.c.id_objeto_fase)
            .join(Objeto, Objeto.id == ObjetoFase.objeto_id)
            .where(_filtro_trabalhos_atuais(func_id))
            .order_by(
                db.func.coalesce(Objeto.prioridade, 0).desc(),
                db.func.coalesce(Objeto.ordem_kanban, 0),
                off.c.atribuido_em,
                off.c.id_objeto_fase,
            )
        ).fetchall()
        _gravar_ordem(func_id, [r.id_objeto_fase for r in rows])
