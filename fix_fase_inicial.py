"""
Script de correção única: prepend da fase inicial em etapas_pre_definidas
para todos os Objetos que possuem fase_atual_id definida mas cuja
etapas_pre_definidas não começa com a fase que foi a primeira do histórico.

Uso:
    python fix_fase_inicial.py
"""
from app import app, db
from models import Objeto, ObjetoFase, parse_etapas, serialize_etapas


def fix():
    with app.app_context():
        objetos = Objeto.query.filter(
            Objeto.fase_atual_id.isnot(None),
            Objeto.etapas_pre_definidas.isnot(None),
        ).all()

        corrigidos = 0
        ignorados = 0

        for o in objetos:
            etapas = parse_etapas(o.etapas_pre_definidas)
            if not etapas:
                ignorados += 1
                continue

            # Descobrir a primeira fase pela qual o objeto passou
            historico = (
                ObjetoFase.query
                .filter_by(objeto_id=o.id)
                .order_by(ObjetoFase.data_entrada.asc())
                .all()
            )
            primeira_fase_id = historico[0].id_fase if historico else o.fase_atual_id

            # Se a primeira etapa do roadmap JÁ é a fase inicial, pular
            if etapas[0]["fase_id"] == primeira_fase_id:
                ignorados += 1
                continue

            # Prepend da fase inicial
            etapa_inicial = {
                "fase_id": primeira_fase_id,
                "data_limite": o.data_limite.isoformat() if o.data_limite else None,
                "funcionario_id": o.responsavel_id,
            }
            etapas.insert(0, etapa_inicial)
            o.etapas_pre_definidas = serialize_etapas(etapas)
            corrigidos += 1
            print(f"  ✔ Corrigido: Objeto #{o.id} '{o.nome}' — "
                  f"prepend fase #{primeira_fase_id}")

        if corrigidos:
            db.session.commit()
            print(f"\n✅ {corrigidos} objeto(s) corrigido(s), "
                  f"{ignorados} já estavam corretos.")
        else:
            print(f"\n✅ Nenhum objeto precisava de correção "
                  f"({ignorados} já estavam corretos).")


if __name__ == "__main__":
    fix()
