"""Mudar o card de fase (Concluído, arrastar ou "Mover") aplica o funcionário e o prazo do roadmap."""
import unittest

from helpers import app, db, ADMIN, cliente_logado, criar_projeto, funcionario_id, fase_id
from models import ObjetoFase


class MoverComRoadmapTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin = cliente_logado(ADMIN)
        cls.revisao = fase_id("Revisão Ortográfica")
        cls.envio = fase_id("Envio ao Cliente")
        cls.layout = fase_id("Criação de Layout e Diagramação")
        cls.eduardo = funcionario_id("Eduardo")
        cls.renato = funcionario_id("Renato")

    def modulo(self):
        """Caso do print: fase inicial sem funcionário e etapa 2 com funcionário e datas."""
        projeto = criar_projeto(self.admin, [{
            "nome": "M", "fase_id": self.revisao,
            "etapas_pre_definidas": [
                {"fase_id": self.revisao, "funcionario_id": self.renato},
                {"fase_id": self.envio, "data_inicio": "2030-11-09", "data_limite": "2030-11-13", "funcionario_id": self.eduardo},
            ],
        }])
        return projeto["objetos"][0]["id"]

    def card(self, oid):
        return self.admin.get(f"/api/objetos/{oid}").get_json()

    def assert_eduardo_atribuido(self, oid):
        c = self.card(oid)
        self.assertEqual(c["fase_atual_id"], self.envio)
        self.assertEqual([f["id"] for f in c["funcionarios_fase_atual"]], [self.eduardo])
        self.assertEqual(c["responsavel_id"], self.eduardo)
        self.assertEqual(c["sla_fase"]["data_limite"], "2030-11-13")
        fila = [i["objeto_id"] for i in self.admin.get(f"/api/prioridades/{self.eduardo}").get_json()["itens"]]
        self.assertIn(oid, fila)

    def test_concluido_atribui_e_atualiza_responsavel(self):
        oid = self.modulo()
        self.admin.post(f"/api/objetos/{oid}/concluir-fase")
        self.assert_eduardo_atribuido(oid)

    def test_mover_ou_arrastar_para_a_proxima_etapa_atribui(self):
        oid = self.modulo()
        res = self.admin.post(f"/api/objetos/{oid}/mover-fase", json={"fase_id": self.envio})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assert_eduardo_atribuido(oid)
        # O roadmap reconhece a etapa 2 como atual
        self.assertEqual(self.card(oid)["indice_fase_atual"], 1)

    def test_prazo_informado_ao_mover_tem_prioridade(self):
        oid = self.modulo()
        self.admin.post(f"/api/objetos/{oid}/mover-fase", json={"fase_id": self.envio, "data_limite_fase": "2030-12-01"})
        self.assertEqual(self.card(oid)["sla_fase"]["data_limite"], "2030-12-01")

    def test_voltar_para_etapa_anterior_atribui_o_funcionario_dela(self):
        oid = self.modulo()
        self.admin.post(f"/api/objetos/{oid}/concluir-fase")  # vai para Envio
        self.admin.post(f"/api/objetos/{oid}/mover-fase", json={"fase_id": self.revisao})  # retrabalho
        c = self.card(oid)
        self.assertEqual([f["id"] for f in c["funcionarios_fase_atual"]], [self.renato])

    def test_mover_para_fase_fora_do_roadmap_nao_atribui_ninguem(self):
        oid = self.modulo()
        self.admin.post(f"/api/objetos/{oid}/mover-fase", json={"fase_id": self.layout})
        c = self.card(oid)
        self.assertEqual(c["funcionarios_fase_atual"], [])
        self.assertIsNone(c["sla_fase"])

    def test_modulo_afetado_se_corrige_salvando_o_roadmap(self):
        """Cards que já mudaram de fase sem a atribuição: salvar o roadmap corrige."""
        oid = self.modulo()
        self.admin.post(f"/api/objetos/{oid}/concluir-fase")
        with app.app_context():
            of = ObjetoFase.query.filter_by(objeto_id=oid, data_saida=None).one()
            of.funcionarios = []  # estado do print
            db.session.commit()
        etapas = self.card(oid)["etapas_pre_definidas"]
        self.admin.put(f"/api/objetos/{oid}", json={"etapas_pre_definidas": etapas})
        self.assertEqual([f["id"] for f in self.card(oid)["funcionarios_fase_atual"]], [self.eduardo])


if __name__ == "__main__":
    unittest.main()
