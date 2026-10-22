"""Editar o roadmap de um card e adicionar/remover módulos da OS."""
import unittest

from helpers import (
    app, db, ADMIN, cliente_logado, criar_projeto, atribuir, funcionario_id, fase_id,
)
from models import Comentario, Fase


class RoadmapModulosTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin = cliente_logado(ADMIN)
        cls.revisao = fase_id("Revisão Ortográfica")
        cls.layout = fase_id("Criação de Layout e Diagramação")
        cls.correcao = fase_id("Correção")
        cls.envio = fase_id("Envio ao Cliente")
        cls.renato = funcionario_id("Renato")   # Redator/Revisor
        cls.juliana = funcionario_id("Juliana")  # Diagramação

    def etapa(self, fase, func=None, data=None):
        return {"fase_id": fase, "funcionario_id": func, "data_limite": data}

    def novo_modulo_em_andamento(self):
        """Módulo com roadmap revisão → layout → envio, já na 2ª etapa (layout)."""
        projeto = criar_projeto(self.admin, [{
            "nome": "Roadmap", "fase_id": self.revisao,
            "etapas_pre_definidas": [
                self.etapa(self.revisao), self.etapa(self.layout), self.etapa(self.envio),
            ],
        }])
        oid = projeto["objetos"][0]["id"]
        res = self.admin.post(f"/api/objetos/{oid}/concluir-fase")
        self.assertEqual(res.status_code, 200, res.get_json())
        return projeto, oid

    def put_etapas(self, oid, etapas):
        return self.admin.put(f"/api/objetos/{oid}", json={"etapas_pre_definidas": etapas})

    # ── Edição do roadmap ───────────────────────────────────────────────

    def test_indice_da_fase_atual_vem_do_backend(self):
        _, oid = self.novo_modulo_em_andamento()
        card = self.admin.get(f"/api/objetos/{oid}").get_json()
        self.assertEqual(card["indice_fase_atual"], 1)

    def test_editar_etapas_futuras(self):
        _, oid = self.novo_modulo_em_andamento()
        res = self.put_etapas(oid, [
            self.etapa(self.revisao), self.etapa(self.layout),
            self.etapa(self.correcao, self.renato, "2030-01-10"),  # nova etapa no meio
            self.etapa(self.envio),
        ])
        self.assertEqual(res.status_code, 200, res.get_json())
        etapas = self.admin.get(f"/api/objetos/{oid}").get_json()["etapas_pre_definidas"]
        self.assertEqual([e["fase_id"] for e in etapas], [self.revisao, self.layout, self.correcao, self.envio])
        self.assertEqual(etapas[2], {"fase_id": self.correcao, "funcionario_id": self.renato,
                                     "data_inicio": None, "data_limite": "2030-01-10"})

        # Concluir a fase atual segue o roadmap editado
        res = self.admin.post(f"/api/objetos/{oid}/concluir-fase")
        self.assertEqual(res.get_json()["fase_atual_id"], self.correcao)

    def test_remover_todas_as_etapas_futuras(self):
        _, oid = self.novo_modulo_em_andamento()
        res = self.put_etapas(oid, [self.etapa(self.revisao), self.etapa(self.layout)])
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertFalse(res.get_json()["has_proxima_etapa"])

    def test_etapas_cumpridas_e_atual_sao_travadas(self):
        _, oid = self.novo_modulo_em_andamento()
        # Remover etapa já cumprida
        self.assertEqual(self.put_etapas(oid, [self.etapa(self.layout), self.etapa(self.envio)]).status_code, 400)
        # Trocar a etapa atual
        self.assertEqual(self.put_etapas(oid, [self.etapa(self.revisao), self.etapa(self.correcao)]).status_code, 400)
        # Reordenar cumprida/atual
        self.assertEqual(self.put_etapas(oid, [self.etapa(self.layout), self.etapa(self.revisao)]).status_code, 400)
        # Nada mudou
        etapas = self.admin.get(f"/api/objetos/{oid}").get_json()["etapas_pre_definidas"]
        self.assertEqual([e["fase_id"] for e in etapas], [self.revisao, self.layout, self.envio])

    def test_dados_das_etapas_travadas_nao_sao_sobrescritos(self):
        _, oid = self.novo_modulo_em_andamento()
        self.put_etapas(oid, [
            self.etapa(self.revisao, self.renato, "2031-01-01"),  # tentativa de mudar etapa cumprida
            self.etapa(self.layout), self.etapa(self.envio),
        ])
        etapas = self.admin.get(f"/api/objetos/{oid}").get_json()["etapas_pre_definidas"]
        self.assertEqual(etapas[0], {"fase_id": self.revisao, "funcionario_id": None, "data_inicio": None, "data_limite": None})

    def test_validacoes_de_etapa(self):
        _, oid = self.novo_modulo_em_andamento()
        base = [self.etapa(self.revisao), self.etapa(self.layout)]
        # Fase inexistente
        self.assertEqual(self.put_etapas(oid, base + [self.etapa(999999)]).status_code, 400)
        # Funcionário sem a função exigida (Juliana não é revisora)
        res = self.put_etapas(oid, base + [self.etapa(self.revisao, self.juliana)])
        self.assertEqual(res.status_code, 400)
        self.assertIn("Juliana", res.get_json()["erro"])
        # Data inválida
        self.assertEqual(self.put_etapas(oid, base + [self.etapa(self.envio, None, "31/12/2030")]).status_code, 400)
        # Fase desativada
        with app.app_context():
            inativa = Fase(nome_fase="Fase desativada teste", ativa=False)
            db.session.add(inativa)
            db.session.commit()
            inativa_id = inativa.id_fase
        self.assertEqual(self.put_etapas(oid, base + [self.etapa(inativa_id)]).status_code, 400)

    def test_modulo_sem_fase_pode_ter_roadmap_inteiro_editado(self):
        projeto = criar_projeto(self.admin, [{"nome": "Sem fase", "fase_id": None}])
        oid = projeto["objetos"][0]["id"]
        res = self.put_etapas(oid, [self.etapa(self.layout, self.juliana), self.etapa(self.envio)])
        self.assertEqual(res.status_code, 200, res.get_json())
        res = self.admin.post(f"/api/objetos/{oid}/concluir-fase")
        self.assertEqual(res.get_json()["fase_atual_id"], self.layout)

    # ── Módulos da OS ───────────────────────────────────────────────────

    def test_adicionar_modulo_com_roadmap_a_os_existente(self):
        projeto, _ = self.novo_modulo_em_andamento()
        res = self.admin.post(f"/api/projetos/{projeto['id']}/objetos", json={
            "nome": "Módulo novo", "fase_id": self.layout, "data_limite": "2030-06-30",
            "etapas_pre_definidas": [
                self.etapa(self.layout, self.juliana, "2030-03-01"),
                self.etapa(self.envio, None, "2030-06-30"),
            ],
        })
        self.assertEqual(res.status_code, 201, res.get_json())
        novo = self.admin.get(f"/api/objetos/{res.get_json()['id']}").get_json()
        self.assertEqual(novo["fase_atual_id"], self.layout)
        self.assertEqual([e["fase_id"] for e in novo["etapas_pre_definidas"]], [self.layout, self.envio])
        self.assertEqual(novo["sla_fase"]["data_limite"], "2030-03-01")

    def test_adicionar_modulo_valida_roadmap_e_limite(self):
        projeto, _ = self.novo_modulo_em_andamento()
        pid = projeto["id"]
        res = self.admin.post(f"/api/projetos/{pid}/objetos", json={
            "nome": "Inválido", "fase_id": self.revisao,
            "etapas_pre_definidas": [self.etapa(self.revisao, self.juliana)],
        })
        self.assertEqual(res.status_code, 400)
        for i in range(5):
            self.assertEqual(self.admin.post(f"/api/projetos/{pid}/objetos",
                                             json={"nome": f"Extra {i}", "fase_id": self.revisao}).status_code, 201)
        res = self.admin.post(f"/api/projetos/{pid}/objetos", json={"nome": "Sétimo", "fase_id": self.revisao})
        self.assertEqual(res.status_code, 400)

    def test_remover_modulo_mantem_comentarios_na_os(self):
        projeto = criar_projeto(self.admin, [
            {"nome": "Fica", "fase_id": self.revisao},
            {"nome": "Sai", "fase_id": self.revisao},
        ])
        fica, sai = (o["id"] for o in projeto["objetos"])
        atribuir(self.admin, sai, self.renato)
        self.admin.post(f"/api/objetos/{sai}/comentarios", json={"texto": "comentário do módulo removido"})

        self.assertEqual(self.admin.delete(f"/api/objetos/{sai}").status_code, 200)
        self.assertEqual(self.admin.get(f"/api/objetos/{sai}").status_code, 404)
        with app.app_context():
            c = Comentario.query.filter_by(texto="comentário do módulo removido").one()
            self.assertIsNone(c.objeto_id)
            self.assertEqual(c.projeto_id, projeto["id"])

        # Último módulo não pode ser removido
        self.assertEqual(self.admin.delete(f"/api/objetos/{fica}").status_code, 400)


if __name__ == "__main__":
    unittest.main()
