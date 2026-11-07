"""Quem tem a função Diretor ou Gerente tem acesso de admin."""
import unittest

from helpers import app, db, ADMIN, cliente_logado
from models import Usuario, Funcionario, Funcao


class AcessoPorFuncaoTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin = cliente_logado(ADMIN)
        funcoes = {f["nome"]: f["id"] for f in cls.admin.get("/api/funcoes").get_json()}
        cls.gerente, cls.revisor = funcoes["Gerente"], funcoes["Revisor"]

    def novo(self, email, perfil, funcao_ids):
        self.admin.post("/api/funcionarios", json={"nome": email, "email": email, "funcao_ids": funcao_ids})
        self.admin.post("/api/usuarios", json={"nome": email, "email": email, "perfil": perfil})
        return cliente_logado(email)

    def test_john_gestor_e_gerente_vira_admin(self):
        me = cliente_logado("john@mind.com.br").get("/api/me").get_json()
        self.assertEqual(me["perfil_cadastrado"], "gestor")
        self.assertEqual(me["perfil"], "admin")
        self.assertTrue(me["admin_por_funcao"])
        self.assertIn("usuarios", me["abas"])

    def test_funcionario_com_funcao_gerente_acessa_rotas_de_admin(self):
        c = self.novo("gerente.novo@teste.com", "funcionario", [self.gerente])
        self.assertEqual(c.get("/api/usuarios").status_code, 200)
        self.assertEqual(c.get("/admin").status_code, 200)

    def test_sem_a_funcao_continua_com_o_perfil_cadastrado(self):
        c = self.novo("revisor.novo@teste.com", "funcionario", [self.revisor])
        self.assertEqual(c.get("/api/me").get_json()["perfil"], "funcionario")
        self.assertEqual(c.get("/api/usuarios").status_code, 403)
        self.assertEqual(c.get("/admin").status_code, 302)

    def test_perder_a_funcao_tira_o_acesso(self):
        c = self.novo("ex.gerente@teste.com", "funcionario", [self.gerente])
        self.assertEqual(c.get("/api/usuarios").status_code, 200)
        fid = c.get("/api/me").get_json()["funcionario_id"]
        self.admin.put(f"/api/funcionarios/{fid}", json={"funcao_ids": [self.revisor]})
        self.assertEqual(c.get("/api/usuarios").status_code, 403)

    def test_usuario_sem_funcionario_usa_o_perfil_cadastrado(self):
        with app.app_context():
            db.session.add(Usuario(nome="Só login", email="so.login@teste.com", perfil="gestor", hash_senha="x"))
            db.session.commit()
        self.assertEqual(cliente_logado("so.login@teste.com").get("/api/me").get_json()["perfil"], "gestor")


if __name__ == "__main__":
    unittest.main()
