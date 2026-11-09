"""Funcionário é a fonte de nome e e-mail; o acesso ao sistema é definido no cadastro dele."""
import unittest

from helpers import app, db, ADMIN, GESTOR, cliente_logado
from models import Usuario, Funcionario


class CadastroUnicoTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin = cliente_logado(ADMIN)

    def novo_func(self, email, **extra):
        res = self.admin.post("/api/funcionarios", json={"nome": email.split("@")[0], "email": email, **extra})
        self.assertEqual(res.status_code, 201, res.get_json())
        return res.get_json()

    def login(self, email, senha="Trocar@123"):
        return app.test_client().post("/login", data={"email": email, "senha": senha})

    def test_dar_acesso_cria_login_com_o_email_do_funcionario(self):
        f = self.novo_func("paula@teste.com")
        self.assertIsNone(f["acesso"])
        res = self.admin.put(f"/api/funcionarios/{f['id']}/acesso", json={"ativo": True, "perfil": "gestor"})
        self.assertEqual(res.status_code, 200, res.get_json())
        acesso = res.get_json()["acesso"]
        self.assertTrue(acesso["ativo"])
        self.assertEqual(acesso["perfil_cadastrado"], "gestor")
        self.assertTrue(acesso["trocar_senha"])
        self.assertEqual(self.login("paula@teste.com").headers.get("Location"), "/trocar-senha")

    def test_criar_funcionario_ja_com_acesso(self):
        f = self.novo_func("rui@teste.com", acesso={"ativo": True, "perfil": "funcionario"})
        self.assertTrue(f["acesso"]["ativo"])
        self.assertEqual(self.login("rui@teste.com").status_code, 302)

    def test_trocar_email_do_funcionario_muda_o_login(self):
        f = self.novo_func("antigo@teste.com", acesso={"ativo": True})
        res = self.admin.put(f"/api/funcionarios/{f['id']}", json={"email": "Novo@Teste.com", "nome": "Novo Nome"})
        self.assertEqual(res.status_code, 200, res.get_json())
        with app.app_context():
            u = db.session.get(Usuario, res.get_json()["usuario_id"])
            self.assertEqual((u.email, u.nome), ("novo@teste.com", "Novo Nome"))
        self.assertEqual(self.login("novo@teste.com").headers.get("Location"), "/trocar-senha")
        self.assertIn("incorretos", self.login("antigo@teste.com").get_data(as_text=True))

    def test_desligar_acesso_impede_login_e_religar_reaproveita_a_conta(self):
        f = self.novo_func("lia@teste.com", acesso={"ativo": True})
        uid = f["usuario_id"]
        self.admin.put(f"/api/funcionarios/{f['id']}/acesso", json={"ativo": False})
        self.assertIn("incorretos", self.login("lia@teste.com").get_data(as_text=True))
        res = self.admin.put(f"/api/funcionarios/{f['id']}/acesso", json={"ativo": True})
        self.assertEqual(res.get_json()["usuario_id"], uid)

    def test_email_de_outro_funcionario_ou_conta_e_recusado(self):
        self.novo_func("ocupado@teste.com")
        f = self.novo_func("livre@teste.com", acesso={"ativo": True})
        res = self.admin.put(f"/api/funcionarios/{f['id']}", json={"email": "ocupado@teste.com"})
        self.assertEqual(res.status_code, 409)
        # Conta avulsa com o e-mail desejado
        self.admin.post("/api/usuarios", json={"nome": "Avulsa", "email": "avulsa@teste.com", "perfil": "gestor"})
        res = self.admin.put(f"/api/funcionarios/{f['id']}", json={"email": "avulsa@teste.com"})
        self.assertEqual(res.status_code, 409)

    def test_so_admin_define_acesso(self):
        f = self.novo_func("gina@teste.com")
        gestor = cliente_logado(GESTOR)
        self.assertEqual(gestor.put(f"/api/funcionarios/{f['id']}/acesso", json={"ativo": True}).status_code, 403)
        res = gestor.post("/api/funcionarios", json={"nome": "X", "email": "x.gestor@teste.com", "acesso": {"ativo": True}})
        self.assertEqual(res.status_code, 403)

    def test_admin_nao_remove_o_proprio_acesso(self):
        with app.app_context():
            fid = Usuario.query.filter_by(email=ADMIN).first().funcionario.id_func
        res = self.admin.put(f"/api/funcionarios/{fid}/acesso", json={"ativo": False})
        self.assertEqual(res.status_code, 409)
        self.assertEqual(self.admin.delete(f"/api/funcionarios/{fid}").status_code, 400)

    def test_excluir_funcionario_desativa_o_login(self):
        f = self.novo_func("saida@teste.com", acesso={"ativo": True})
        self.admin.delete(f"/api/funcionarios/{f['id']}")
        with app.app_context():
            self.assertFalse(db.session.get(Usuario, f["usuario_id"]).ativo)

    def test_sincronizacao_de_cadastros_divergentes(self):
        """Caso relatado: o e-mail do funcionário foi atualizado e o do login ficou antigo."""
        from app import sincronizar_contas_com_funcionarios
        f = self.novo_func("real@empresa.com", acesso={"ativo": True})
        with app.app_context():
            u = db.session.get(Usuario, f["usuario_id"])
            u.email, u.nome = "ficticio@mind.com.br", "Nome antigo"
            db.session.commit()
            self.assertGreaterEqual(sincronizar_contas_com_funcionarios(), 1)
            db.session.commit()
            u = db.session.get(Usuario, f["usuario_id"])
            self.assertEqual((u.email, u.nome), ("real@empresa.com", "real"))


if __name__ == "__main__":
    unittest.main()
