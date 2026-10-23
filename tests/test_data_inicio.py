"""Data de início prevista do módulo e de cada etapa do roadmap."""
import unittest
from datetime import date, timedelta

from helpers import app, db, ADMIN, cliente_logado, criar_projeto, fase_id
from models import Objeto


def dia(delta):
    return (date.today() + timedelta(days=delta)).isoformat()


class DataInicioTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin = cliente_logado(ADMIN)
        cls.revisao = fase_id("Revisão Ortográfica")
        cls.envio = fase_id("Envio ao Cliente")

    def etapa(self, fase, inicio=None, fim=None):
        return {"fase_id": fase, "data_inicio": inicio, "data_limite": fim, "funcionario_id": None}

    def card(self, oid):
        return self.admin.get(f"/api/objetos/{oid}").get_json()

    def test_criar_os_com_inicio_do_modulo_e_das_etapas(self):
        projeto = criar_projeto(self.admin, [{
            "nome": "Com início", "fase_id": self.revisao,
            "data_inicio": "2030-01-05", "data_limite": "2030-03-31",
            "etapas_pre_definidas": [self.etapa(self.envio, "2030-02-01", "2030-02-10")],
        }])
        c = self.card(projeto["objetos"][0]["id"])
        self.assertEqual(c["data_inicio"], "2030-01-05")
        # A fase inicial (inserida automaticamente) herda o início do módulo
        self.assertEqual(c["etapas_pre_definidas"][0]["data_inicio"], "2030-01-05")
        self.assertEqual(c["etapas_pre_definidas"][1]["data_inicio"], "2030-02-01")

    def test_inicio_depois_do_fim_e_recusado(self):
        res = self.admin.post("/api/projetos", json={
            "os": "INICIO-INVALIDO", "data_limite": "2030-12-31",
            "objetos": [{"nome": "X", "fase_id": self.revisao, "data_inicio": "2030-05-01", "data_limite": "2030-04-01"}],
        })
        self.assertEqual(res.status_code, 400)
        res = self.admin.post("/api/projetos", json={
            "os": "INICIO-INVALIDO-2", "data_limite": "2030-12-31",
            "objetos": [{"nome": "X", "fase_id": self.revisao,
                         "etapas_pre_definidas": [self.etapa(self.revisao, "2030-05-01", "2030-04-01")]}],
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("início previsto", res.get_json()["erro"])

    def test_editar_datas_do_modulo(self):
        projeto = criar_projeto(self.admin, [{"nome": "Editar", "fase_id": self.revisao, "data_limite": "2030-06-30"}])
        oid = projeto["objetos"][0]["id"]
        res = self.admin.put(f"/api/objetos/{oid}", json={"data_inicio": "2030-06-01"})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(self.card(oid)["data_inicio"], "2030-06-01")

        # Início depois do fim
        self.assertEqual(self.admin.put(f"/api/objetos/{oid}", json={"data_inicio": "2030-07-01"}).status_code, 400)
        # Fim antes do início já salvo
        self.assertEqual(self.admin.put(f"/api/objetos/{oid}", json={"data_limite": "2030-05-01"}).status_code, 400)
        # Limpar o início
        self.assertEqual(self.admin.put(f"/api/objetos/{oid}", json={"data_inicio": None}).status_code, 200)
        self.assertIsNone(self.card(oid)["data_inicio"])

    def test_data_de_inicio_vencida_nao_move_o_card(self):
        """Passar do início previsto da próxima etapa só gera alerta; o card segue na fase atual."""
        projeto = criar_projeto(self.admin, [{
            "nome": "Início vencido", "fase_id": self.revisao,
            "etapas_pre_definidas": [
                self.etapa(self.revisao, dia(-10), dia(-3)),
                self.etapa(self.envio, dia(-2), dia(5)),
            ],
        }])
        oid = projeto["objetos"][0]["id"]
        c = self.card(oid)
        self.assertEqual(c["fase_atual_id"], self.revisao)
        alerta = c["alertas_inicio"]["proxima_atrasada"]
        self.assertEqual(alerta["dias"], 2)
        self.assertEqual(alerta["fase_nome"], "Envio ao Cliente")

        # Só depois de concluir a fase atual o card vai para a próxima
        res = self.admin.post(f"/api/objetos/{oid}/concluir-fase")
        self.assertEqual(res.get_json()["fase_atual_id"], self.envio)
        self.assertIsNone(self.card(oid)["alertas_inicio"]["proxima_atrasada"])

    def test_alerta_aguardando_inicio(self):
        projeto = criar_projeto(self.admin, [{
            "nome": "Futuro", "fase_id": self.revisao, "data_inicio": dia(4), "data_limite": dia(30),
        }])
        alerta = self.card(projeto["objetos"][0]["id"])["alertas_inicio"]["aguardando"]
        self.assertEqual(alerta, {"data": dia(4), "dias": 4})

    def test_editar_inicio_de_etapa_futura_no_roadmap(self):
        projeto = criar_projeto(self.admin, [{
            "nome": "Roadmap", "fase_id": self.revisao,
            "etapas_pre_definidas": [self.etapa(self.revisao), self.etapa(self.envio)],
        }])
        oid = projeto["objetos"][0]["id"]
        res = self.admin.put(f"/api/objetos/{oid}", json={"etapas_pre_definidas": [
            self.etapa(self.revisao), self.etapa(self.envio, "2030-09-01", "2030-09-15"),
        ]})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(self.card(oid)["etapas_pre_definidas"][1]["data_inicio"], "2030-09-01")

        hist = self.admin.get(f"/api/historico/{projeto['os']}").get_json()
        futura = next(e for e in hist["modulos"][0]["eventos"] if e["tipo"] == "fase_futura")
        self.assertEqual(futura["inicio_str"], "01/09/2030")

    def test_adicionar_modulo_com_inicio(self):
        projeto = criar_projeto(self.admin, [{"nome": "Base", "fase_id": self.revisao}])
        res = self.admin.post(f"/api/projetos/{projeto['id']}/objetos", json={
            "nome": "Novo", "fase_id": self.revisao, "data_inicio": "2030-02-01", "data_limite": "2030-03-01",
        })
        self.assertEqual(res.status_code, 201, res.get_json())
        self.assertEqual(res.get_json()["data_inicio"], "2030-02-01")

    def test_etapas_legadas_sem_data_inicio_continuam_funcionando(self):
        projeto = criar_projeto(self.admin, [{"nome": "Legado", "fase_id": self.revisao}])
        oid = projeto["objetos"][0]["id"]
        with app.app_context():
            # Formato salvo antes desta versão (sem data_inicio)
            db.session.get(Objeto, oid).etapas_pre_definidas = (
                f'[{{"fase_id": {self.revisao}, "data_limite": null, "funcionario_id": null}}, '
                f'{{"fase_id": {self.envio}, "data_limite": "2030-01-01", "funcionario_id": null}}]'
            )
            db.session.commit()
        c = self.card(oid)
        self.assertIsNone(c["etapas_pre_definidas"][1]["data_inicio"])
        self.assertIsNone(c["alertas_inicio"]["proxima_atrasada"])


if __name__ == "__main__":
    unittest.main()
