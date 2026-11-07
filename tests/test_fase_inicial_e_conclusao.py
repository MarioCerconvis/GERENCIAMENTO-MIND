"""Funcionário da fase inicial, troca de funcionário na etapa atual e conclusão do módulo."""
import unittest

from helpers import (
    app, db, ADMIN, cliente_logado, criar_projeto, funcionario_id, fase_id, fase_ativa_id,
)


class FaseInicialEConclusaoTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin = cliente_logado(ADMIN)
        cls.revisao = fase_id("Revisão Ortográfica")
        cls.envio = fase_id("Envio ao Cliente")
        cls.renato = funcionario_id("Renato")
        cls.lucas = funcionario_id("Lucas")
        cls.juliana = funcionario_id("Juliana")  # não é revisora

    def card(self, oid):
        return self.admin.get(f"/api/objetos/{oid}").get_json()

    def fila(self, func_id):
        return [i["objeto_id"] for i in self.admin.get(f"/api/prioridades/{func_id}").get_json()["itens"]]

    def modulo_fase_unica(self, func=None):
        projeto = criar_projeto(self.admin, [{"nome": "Fase única", "fase_id": self.revisao, "funcionario_id": func}])
        return projeto["objetos"][0]["id"]

    def board(self, query=""):
        return {o["id"]: col["id"] for col in self.admin.get(f"/api/kanban{query}").get_json() for o in col["objetos"]}

    # ── 1. Funcionário da fase inicial ─────────────────────────────────

    def test_funcionario_da_fase_inicial_entra_na_equipe_e_na_fila(self):
        oid = self.modulo_fase_unica(self.renato)
        c = self.card(oid)
        self.assertEqual([f["id"] for f in c["funcionarios_fase_atual"]], [self.renato])
        self.assertEqual(c["responsavel_id"], self.renato)
        self.assertEqual(c["etapas_pre_definidas"][0]["funcionario_id"], self.renato)
        self.assertIn(oid, self.fila(self.renato))

    def test_funcionario_sem_a_funcao_da_fase_inicial_e_recusado(self):
        res = self.admin.post("/api/projetos", json={
            "os": "FASE-INICIAL-INVALIDA", "data_limite": "2030-12-31",
            "objetos": [{"nome": "X", "fase_id": self.revisao, "funcionario_id": self.juliana}],
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("Juliana", res.get_json()["erro"])

    def test_novo_modulo_em_os_existente_tambem_atribui(self):
        projeto = criar_projeto(self.admin, [{"nome": "Base", "fase_id": self.revisao}])
        res = self.admin.post(f"/api/projetos/{projeto['id']}/objetos", json={
            "nome": "Novo", "fase_id": self.revisao,
            "etapas_pre_definidas": [{"fase_id": self.revisao, "funcionario_id": self.lucas}],
        })
        self.assertEqual(res.status_code, 201, res.get_json())
        self.assertEqual([f["id"] for f in res.get_json()["funcionarios_fase_atual"]], [self.lucas])

    # ── 2. Trocar o funcionário da etapa atual ─────────────────────────

    def test_trocar_funcionario_em_modulo_de_fase_unica(self):
        oid = self.modulo_fase_unica(self.renato)
        etapa = self.card(oid)["etapas_pre_definidas"][0]
        res = self.admin.put(f"/api/objetos/{oid}", json={"etapas_pre_definidas": [
            {**etapa, "funcionario_id": self.lucas, "data_limite": "2030-05-20"},
        ]})
        self.assertEqual(res.status_code, 200, res.get_json())
        c = self.card(oid)
        self.assertEqual([f["id"] for f in c["funcionarios_fase_atual"]], [self.lucas])
        self.assertEqual(c["sla_fase"]["data_limite"], "2030-05-20")
        self.assertNotIn(oid, self.fila(self.renato))
        self.assertIn(oid, self.fila(self.lucas))

    def test_etapa_atual_continua_com_a_fase_travada(self):
        oid = self.modulo_fase_unica(self.renato)
        res = self.admin.put(f"/api/objetos/{oid}", json={"etapas_pre_definidas": [{"fase_id": self.envio}]})
        self.assertEqual(res.status_code, 400)

    def test_modulo_antigo_sem_equipe_recebe_o_funcionario_da_etapa(self):
        """Módulos criados antes da correção têm o funcionário na etapa, mas não na equipe."""
        oid = self.modulo_fase_unica(self.renato)
        with app.app_context():
            from models import ObjetoFase
            of = ObjetoFase.query.filter_by(objeto_id=oid, data_saida=None).one()
            of.funcionarios = []
            db.session.commit()
        etapa = self.card(oid)["etapas_pre_definidas"][0]
        self.admin.put(f"/api/objetos/{oid}", json={"etapas_pre_definidas": [etapa]})
        self.assertEqual([f["id"] for f in self.card(oid)["funcionarios_fase_atual"]], [self.renato])

    # ── 3. Concluir a última fase ──────────────────────────────────────

    def test_card_de_fase_unica_pode_ser_concluido(self):
        oid = self.modulo_fase_unica(self.renato)
        self.assertTrue(self.card(oid)["pode_concluir_fase"])
        res = self.admin.post(f"/api/objetos/{oid}/concluir-fase")
        self.assertEqual(res.status_code, 200, res.get_json())
        c = self.card(oid)
        self.assertIsNotNone(c["concluido_em"])
        self.assertFalse(c["pode_concluir_fase"])
        self.assertIsNone(c["fase_ativa_id"])
        self.assertNotIn(oid, self.fila(self.renato))
        # Sai do board; aparece na coluna de concluídos quando pedido
        self.assertNotIn(oid, self.board())
        self.assertEqual(self.board("?concluidos=1").get(oid), "concluidos")
        # Não conclui de novo nem edita o roadmap
        self.assertEqual(self.admin.post(f"/api/objetos/{oid}/concluir-fase").status_code, 400)
        self.assertEqual(self.admin.put(f"/api/objetos/{oid}", json={"etapas_pre_definidas": [
            {"fase_id": self.revisao}, {"fase_id": self.envio}]}).status_code, 400)
        self.assertEqual(self.admin.post(f"/api/objetos/{oid}/mover-fase", json={"fase_id": self.envio}).status_code, 400)

    def test_ultima_fase_de_roadmap_longo_tambem_conclui(self):
        projeto = criar_projeto(self.admin, [{
            "nome": "Duas fases", "fase_id": self.revisao,
            "etapas_pre_definidas": [{"fase_id": self.revisao}, {"fase_id": self.envio}],
        }])
        oid = projeto["objetos"][0]["id"]
        self.admin.post(f"/api/objetos/{oid}/concluir-fase")  # vai para Envio
        self.assertEqual(self.card(oid)["fase_atual_id"], self.envio)
        self.admin.post(f"/api/objetos/{oid}/concluir-fase")  # última → conclui
        self.assertIsNotNone(self.card(oid)["concluido_em"])

    def test_funcionario_aprovando_a_ultima_fase_conclui(self):
        oid = self.modulo_fase_unica(self.renato)
        renato = cliente_logado("renato@mind.com.br")
        res = renato.post(f"/api/objetos/{oid}/concluir-fase")
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertTrue(res.get_json()["concluido"])
        self.assertIsNotNone(self.card(oid)["concluido_em"])

    def test_remover_unico_membro_nao_conclui_nem_avanca(self):
        oid = self.modulo_fase_unica(self.renato)
        self.admin.post(f"/api/objeto-fase/{fase_ativa_id(self.admin, oid)}/remover", json={"funcionario_id": self.renato})
        c = self.card(oid)
        self.assertIsNone(c["concluido_em"])
        self.assertIsNotNone(c["fase_ativa_id"])

    def test_reabrir_modulo_concluido(self):
        oid = self.modulo_fase_unica(self.renato)
        self.admin.post(f"/api/objetos/{oid}/concluir-fase")
        res = self.admin.post(f"/api/objetos/{oid}/reabrir")
        self.assertEqual(res.status_code, 200, res.get_json())
        c = self.card(oid)
        self.assertIsNone(c["concluido_em"])
        self.assertEqual(c["fase_atual_id"], self.revisao)
        self.assertEqual([f["id"] for f in c["funcionarios_fase_atual"]], [self.renato])
        self.assertIn(oid, self.fila(self.renato))
        self.assertEqual(self.admin.post(f"/api/objetos/{oid}/reabrir").status_code, 400)

    def test_modulo_concluido_nao_gera_alerta_de_sla(self):
        from sla_checker import verificar_sla_projetos
        projeto = criar_projeto(self.admin, [{"nome": "Atrasado", "fase_id": self.revisao,
                                              "funcionario_id": self.renato, "data_limite": "2020-01-01"}],
                                data_limite="2030-01-01")
        oid = projeto["objetos"][0]["id"]
        self.admin.post(f"/api/objetos/{oid}/concluir-fase")
        with app.app_context():
            from unittest import mock
            with mock.patch("sla_checker.notificar_sla_objeto_estourado") as aviso:
                verificar_sla_projetos()
            avisados = [call.args[1].id for call in aviso.call_args_list]
            self.assertNotIn(oid, avisados)

    def test_historico_mostra_a_conclusao(self):
        projeto = criar_projeto(self.admin, [{"nome": "Hist", "fase_id": self.revisao, "funcionario_id": self.renato}])
        oid = projeto["objetos"][0]["id"]
        self.admin.post(f"/api/objetos/{oid}/concluir-fase")
        eventos = self.admin.get(f"/api/historico/{projeto['os']}").get_json()["modulos"][0]["eventos"]
        self.assertEqual(eventos[-1]["tipo"], "conclusao")


if __name__ == "__main__":
    unittest.main()
