"""
Job periódico para verificação de SLA.
Verifica diariamente os projetos com prazo ultrapassado e envia notificações.
"""
from datetime import date

from models import db, Projeto, ProjetoFase
from notifications import notificar_sla_estourado, notificar_sla_fase_estourado


def verificar_sla_projetos():
    """Busca projetos fora do SLA e notifica os responsáveis."""
    hoje = date.today()
    projetos_atrasados = Projeto.query.filter(
        Projeto.data_limite < hoje,
        Projeto.fase_atual_id.isnot(None),  # Só projetos com fase ativa
    ).all()

    count = 0
    for projeto in projetos_atrasados:
        dias_atraso = (hoje - projeto.data_limite).days
        if projeto.responsavel:
            notificar_sla_estourado(projeto, projeto.responsavel, dias_atraso)
            count += 1

    fases_atrasadas = ProjetoFase.query.filter(
        ProjetoFase.data_saida.is_(None),
        ProjetoFase.data_limite < hoje
    ).all()

    count_fase = 0
    for pf in fases_atrasadas:
        dias_atraso = (hoje - pf.data_limite).days
        projeto = pf.projeto
        if projeto and projeto.responsavel:
            notificar_sla_fase_estourado(projeto, projeto.responsavel, dias_atraso, pf.fase.nome_fase)
            count_fase += 1

    print(f"[SLA CHECK] {count} notificação projeto, {count_fase} notificação fase.")
    return count + count_fase
