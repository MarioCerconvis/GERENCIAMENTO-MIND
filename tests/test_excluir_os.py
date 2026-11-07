"""Exclusão de OS (com confirmação) e de módulos."""
import unittest

from helpers import app, db, ADMIN, GESTOR, cliente_logado, criar_projeto, funcionario_id, fase_id
from models import Comentario, Objeto, ObjetoFase, Projeto


class ExcluirOSTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin = cliente_logado(ADMIN)
        cls.revisao = fase_id("Revisão Ortográfica")
        cls.renato = funcionario_id("Renato")

    def nova_os(self):
        projeto = criar_projeto(self.admin, [
            {"nome": "A", "fase_id": self.revisao, "funcionario_id": self.renato},
            {"nome": "B", "fase_id": self.revisao},
        ])
        a, b = (o["id"] for o in projeto["objetos"])
        self.admin.post(f"/api/objetos/{a}/comentarios", json={"texto": "no módulo"})
        self.admin.post(f"/api/projetos/{projeto['id']}/comentarios", json={"texto": "na OS"})
        return projeto, a, b

    def fila_renato(self):
        return [i["objeto_id"] for i in self.admin.get(f"/api/prioridades/{self.renato}").get_json()["itens"]]

    def test_excluir_os_apaga_modulos_historico_e_comentarios(self):
        projeto, a, b = self.nova_os()
        self.assertIn(a, self.fila_renato())
        res = self.admin.delete(f"/api/projetos/{projeto['id']}", json={"os": projeto["os"]})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(res.get_json()["modulos_excluidos"], 2)
        with app.app_context():
            self.assertIsNone(db.session.get(Projeto, projeto["id"]))
            self.assertEqual(Objeto.query.filter(Objeto.id.in_([a, b])).count(), 0)
            self.assertEqual(ObjetoFase.query.filter(ObjetoFase.objeto_id.in_([a, b])).count(), 0)
            self.assertEqual(Comentario.query.filter_by(projeto_id=projeto["id"]).count(), 0)
        self.assertNotIn(a, self.fila_renato())

    def test_excluir_os_exige_o_codigo_exato(self):
        projeto, _, _ = self.nova_os()
        self.assertEqual(self.admin.delete(f"/api/projetos/{projeto['id']}").status_code, 400)
        self.assertEqual(self.admin.delete(f"/api/projetos/{projeto['id']}", json={"os": "outra"}).status_code, 400)
        self.assertEqual(self.admin.get(f"/api/projetos/{projeto['id']}").status_code, 200)

    def test_so_admin_exclui_os(self):
        projeto, _, _ = self.nova_os()
        res = cliente_logado(GESTOR).delete(f"/api/projetos/{projeto['id']}", json={"os": projeto["os"]})
        self.assertEqual(res.status_code, 403)

    def test_excluir_modulo_e_bloquear_o_ultimo(self):
        projeto, a, b = self.nova_os()
        self.assertEqual(self.admin.delete(f"/api/objetos/{a}").status_code, 200)
        self.assertNotIn(a, self.fila_renato())
        res = self.admin.delete(f"/api/objetos/{b}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Exclua a OS", res.get_json()["erro"])


if __name__ == "__main__":
    unittest.main()
