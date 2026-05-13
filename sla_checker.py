"""
Job periódico para verificação de SLA.
Verifica diariamente os projetos com prazo ultrapassado e envia notificações.
"""
from datetime import date

from models import db, Projeto
from notifications import notificar_sla_estourado


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

    print(f"[SLA CHECK] {count} notificação(ões) enviada(s) de {len(projetos_atrasados)} projeto(s) atrasado(s).")
    return count
