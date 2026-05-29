"""
Job periódico para verificação de SLA.
Verifica diariamente os projetos com prazo ultrapassado e envia notificações.
"""
from datetime import date

from models import db, Projeto, Objeto, ObjetoFase
from notifications import notificar_sla_estourado, notificar_sla_objeto_estourado, notificar_sla_fase_estourado


def verificar_sla_projetos():
    """Busca projetos e objetos fora do SLA e notifica os responsáveis."""
    hoje = date.today()
    
    # 1. Macro Projetos Atrasados
    projetos_atrasados = Projeto.query.filter(
        Projeto.data_limite < hoje
    ).all()

    count_proj = 0
    for projeto in projetos_atrasados:
        # Apenas se houver um objeto não-finalizado? Por enquanto, todos vencidos
        dias_atraso = (hoje - projeto.data_limite).days
        if projeto.responsavel:
            notificar_sla_estourado(projeto, projeto.responsavel, dias_atraso)
            count_proj += 1

    # 2. Objetos Atrasados
    objetos_atrasados = Objeto.query.filter(
        Objeto.data_limite < hoje,
        Objeto.fase_atual_id.isnot(None),  # Só objetos ativos
    ).all()

    count_obj = 0
    for obj in objetos_atrasados:
        dias_atraso = (hoje - obj.data_limite).days
        if obj.responsavel:
            notificar_sla_objeto_estourado(obj.projeto, obj, obj.responsavel, dias_atraso)
            count_obj += 1

    # 3. Fases Atrasadas
    fases_atrasadas = ObjetoFase.query.filter(
        ObjetoFase.data_saida.is_(None),
        ObjetoFase.data_limite < hoje
    ).all()

    count_fase = 0
    for of in fases_atrasadas:
        dias_atraso = (hoje - of.data_limite).days
        obj = of.objeto
        if obj and obj.responsavel:
            notificar_sla_fase_estourado(obj.projeto, obj, obj.responsavel, dias_atraso, of.fase.nome_fase)
            count_fase += 1

    total = count_proj + count_obj + count_fase
    print(f"[SLA CHECK] {count_proj} notificação projeto, {count_obj} notificação objeto, {count_fase} notificação fase.")
    return total
