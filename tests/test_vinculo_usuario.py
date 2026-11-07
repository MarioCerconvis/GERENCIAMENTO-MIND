"""Usuário (login) e funcionário com o mesmo e-mail são ligados automaticamente."""
import unittest

from helpers import app, db, ADMIN, cliente_logado, criar_projeto, atribuir, fase_id
from models import Usuario, Funcionario


class VinculoUsuarioFuncionarioTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin = cliente_logado(ADMIN)

    def test_criar_funcionario_depois_do_usuario(self):
        res = self.admin.post("/api/usuarios", json={"nome": "Ana", "email": "ana@teste.com", "perfil": "funcionario"})
        self.assertEqual(res.status_code, 201)
        self.assertIsNone(res.get_json()["funcionario_id"])
        res = self.admin.post("/api/funcionarios", json={"nome": "Ana", "email": "ANA@teste.com"})
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.get_json()["tem_login"])
        self.assertEqual(res.get_json()["perfil"], "funcionario")

    def test_criar_usuario_depois_do_funcionario_e_ver_os_proprios_cards(self):
        res = self.admin.post("/api/funcionarios", json={"nome": "Bia", "email": "bia@teste.com"})
        fid = res.get_json()["id"]
        self.assertFalse(res.get_json()["tem_login"])
        res = self.admin.post("/api/usuarios", json={"nome": "Bia", "email": "bia@teste.com", "perfil": "funcionario"})
        self.assertEqual(res.get_json()["funcionario_id"], fid)

        # Login com a senha padrão funciona e a pessoa vê o card atribuído a ela
        projeto = criar_projeto(self.admin, [{"nome": "Card da Bia", "fase_id": fase_id("Envio ao Cliente")}])
        atribuir(self.admin, projeto["objetos"][0]["id"], fid)
        c = app.test_client()
        res = c.post("/login", data={"email": "bia@teste.com", "senha": "Trocar@123"})
        self.assertEqual(res.headers.get("Location"), "/trocar-senha")
        nomes = [o["nome"] for col in c.get("/api/kanban").get_json() for o in col["objetos"]]
        self.assertIn("Card da Bia", nomes)

    def test_trocar_email_do_funcionario_liga_ao_usuario(self):
        self.admin.post("/api/usuarios", json={"nome": "Caio", "email": "caio@teste.com", "perfil": "funcionario"})
        fid = self.admin.post("/api/funcionarios", json={"nome": "Caio", "email": "caio.errado@teste.com"}).get_json()["id"]
        res = self.admin.put(f"/api/funcionarios/{fid}", json={"email": "caio@teste.com"})
        self.assertTrue(res.get_json()["tem_login"])

    def test_vinculo_de_cadastros_antigos(self):
        from app import vincular_usuarios_funcionarios
        with app.app_context():
            u = Usuario(nome="Dani", email="dani@teste.com", perfil="funcionario", hash_senha="x")
            f = Funcionario(nome="Dani", email="dani@teste.com")
            db.session.add_all([u, f])
            db.session.commit()
            self.assertIsNone(f.usuario_id)
            self.assertGreaterEqual(vincular_usuarios_funcionarios(), 1)
            db.session.commit()
            self.assertEqual(f.usuario_id, u.id)


if __name__ == "__main__":
    unittest.main()
