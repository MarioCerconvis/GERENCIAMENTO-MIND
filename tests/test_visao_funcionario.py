"""Admin/Gestor vê os cards atuais, concluídos e futuros de qualquer funcionário."""
import unittest

from helpers import (
    app, db, ADMIN, GESTOR, cliente_logado, criar_projeto, atribuir,
    funcionario_id, fase_id, fase_ativa_id,
)
from models import Usuario


def cards(board):
    """{nome_do_modulo: relacao} de todos os cards do board."""
    return {o["nome"]: o["relacao_funcionario"] for col in board for o in col["objetos"]}


class VisaoFuncionarioTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin = cliente_logado(ADMIN)
        cls.revisao = fase_id("Revisão Ortográfica")
        cls.envio = fase_id("Envio ao Cliente")
        cls.renato = funcionario_id("Renato")
        cls.luiza = funcionario_id("Luiza")

        projeto = criar_projeto(cls.admin, [
            {   # Renato na fase atual, Luiza na próxima etapa
                "nome": "V1-atual-e-futuro", "fase_id": cls.revisao,
                "etapas_pre_definidas": [
                    {"fase_id": cls.revisao, "data_limite": None, "funcionario_id": cls.renato},
                    {"fase_id": cls.envio, "data_limite": None, "funcionario_id": cls.luiza},
                ],
            },
            {   # Só Luiza, no futuro
                "nome": "V2-so-futuro", "fase_id": cls.revisao,
                "etapas_pre_definidas": [
                    {"fase_id": cls.revisao, "data_limite": None, "funcionario_id": None},
                    {"fase_id": cls.envio, "data_limite": None, "funcionario_id": cls.luiza},
                ],
            },
            {"nome": "V3-sem-relacao", "fase_id": cls.revisao},
        ])
        cls.obj = {o["nome"]: o["id"] for o in projeto["objetos"]}
        atribuir(cls.admin, cls.obj["V1-atual-e-futuro"], cls.renato)

    def board(self, client, query=""):
        res = client.get(f"/api/kanban{query}")
        self.assertEqual(res.status_code, 200, res.get_json())
        return cards(res.get_json())

    def test_admin_sem_filtro_ve_todos_os_cards(self):
        c = self.board(self.admin)
        for nome in ("V1-atual-e-futuro", "V2-so-futuro", "V3-sem-relacao"):
            self.assertIn(nome, c)
            self.assertIsNone(c[nome])

    def test_admin_ve_cards_futuros_de_funcionario_sem_card_atual(self):
        c = self.board(self.admin, f"?funcionario_id={self.luiza}")
        self.assertEqual(c.get("V1-atual-e-futuro"), ["futuro"])
        self.assertEqual(c.get("V2-so-futuro"), ["futuro"])
        self.assertNotIn("V3-sem-relacao", c)

    def test_gestor_tambem_pode_filtrar(self):
        c = self.board(cliente_logado(GESTOR), f"?funcionario_id={self.renato}")
        self.assertEqual(c.get("V1-atual-e-futuro"), ["pendente"])
        self.assertNotIn("V2-so-futuro", c)

    def test_relacao_muda_apos_conclusao_da_fase(self):
        # Projeto próprio para não interferir nos outros testes
        projeto = criar_projeto(self.admin, [{
            "nome": "V4-transicao", "fase_id": self.revisao,
            "etapas_pre_definidas": [
                {"fase_id": self.revisao, "data_limite": None, "funcionario_id": self.renato},
                {"fase_id": self.envio, "data_limite": None, "funcionario_id": self.luiza},
            ],
        }])
        oid = projeto["objetos"][0]["id"]
        atribuir(self.admin, oid, self.renato)

        renato = cliente_logado("renato@mind.com.br")
        res = renato.post(f"/api/objeto-fase/{fase_ativa_id(self.admin, oid)}/aprovar")
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertTrue(res.get_json()["movido"])

        self.assertEqual(self.board(self.admin, f"?funcionario_id={self.renato}").get("V4-transicao"), ["concluido"])
        self.assertEqual(self.board(self.admin, f"?funcionario_id={self.luiza}").get("V4-transicao"), ["pendente"])

    def test_funcionario_nao_consegue_ver_cards_de_outro(self):
        carol = cliente_logado("carol@mind.com.br")
        c = self.board(carol, f"?funcionario_id={self.renato}")
        self.assertNotIn("V1-atual-e-futuro", c)

    def test_funcionario_ve_os_proprios_cards(self):
        luiza = cliente_logado("luiza@mind.com.br")
        c = self.board(luiza)
        self.assertEqual(c.get("V2-so-futuro"), ["futuro"])
        self.assertNotIn("V3-sem-relacao", c)

    def test_usuario_funcionario_sem_vinculo_nao_ve_cards(self):
        with app.app_context():
            u = Usuario(nome="Sem vínculo", email="sem.vinculo@teste.com", perfil="funcionario", hash_senha="x")
            db.session.add(u)
            db.session.commit()
        c = self.board(cliente_logado("sem.vinculo@teste.com"))
        self.assertEqual(c, {})

    def test_funcionario_id_invalido(self):
        self.assertEqual(self.admin.get("/api/kanban?funcionario_id=abc").status_code, 400)
        self.assertEqual(self.admin.get("/api/kanban?funcionario_id=999999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
