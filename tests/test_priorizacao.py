"""Priorização numérica por funcionário-fase (1 = mais importante, n = total de trabalhos atuais)."""
import itertools
import unittest

from helpers import (
    app, db, ADMIN, GESTOR, cliente_logado, criar_projeto, atribuir,
    fase_id, fase_ativa_id,
)
from models import Objeto, ObjetoFase, Usuario, Funcionario, objeto_fase_funcionario as off

_seq = itertools.count(1)


class PriorizacaoTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin = cliente_logado(ADMIN)
        cls.revisao = fase_id("Revisão Ortográfica")
        cls.envio = fase_id("Envio ao Cliente")
        cls.revisor_funcao = next(f["id"] for f in cls.admin.get("/api/funcoes").get_json() if f["nome"] == "Revisor")

    # ── helpers ──────────────────────────────────────────────────────────

    def novo_revisor(self, com_login=False):
        n = next(_seq)
        email = f"revisor{n}@teste.com"
        res = self.admin.post("/api/funcionarios", json={
            "nome": f"Revisor Teste {n}", "email": email, "funcao_ids": [self.revisor_funcao],
        })
        self.assertEqual(res.status_code, 201, res.get_json())
        fid = res.get_json()["id"]
        if com_login:
            with app.app_context():
                u = Usuario(nome=f"Revisor Teste {n}", email=email, perfil="funcionario", hash_senha="x")
                db.session.add(u)
                db.session.flush()
                db.session.get(Funcionario, fid).usuario_id = u.id
                db.session.commit()
        return fid

    def novo_modulo(self, roadmap_ate_envio=True, funcionario_envio=None):
        etapas = [{"fase_id": self.revisao, "data_limite": None, "funcionario_id": None}]
        if roadmap_ate_envio:
            etapas.append({"fase_id": self.envio, "data_limite": None, "funcionario_id": funcionario_envio})
        projeto = criar_projeto(self.admin, [{
            "nome": f"Módulo {next(_seq)}", "fase_id": self.revisao, "etapas_pre_definidas": etapas,
        }])
        return projeto["objetos"][0]["id"]

    def fila(self, func_id):
        res = self.admin.get(f"/api/prioridades/{func_id}")
        self.assertEqual(res.status_code, 200)
        itens = res.get_json()["itens"]
        self.assertEqual([i["prioridade"] for i in itens], list(range(1, len(itens) + 1)),
                         "fila deve ser sempre contígua 1..n")
        return [i["objeto_id"] for i in itens]

    def of_id(self, objeto_id):
        return fase_ativa_id(self.admin, objeto_id)

    # ── testes ───────────────────────────────────────────────────────────

    def test_novo_trabalho_entra_no_fim_e_faixa_acompanha_quantidade(self):
        # Funcionário A tem 2 e recebe mais 1 → 1..3; B tem 4 e recebe mais 1 → 1..5
        a, b = self.novo_revisor(), self.novo_revisor()
        mods_a = [self.novo_modulo() for _ in range(3)]
        mods_b = [self.novo_modulo() for _ in range(5)]
        for m in mods_a[:2]:
            atribuir(self.admin, m, a)
        for m in mods_b[:4]:
            atribuir(self.admin, m, b)
        self.assertEqual(self.fila(a), mods_a[:2])
        self.assertEqual(self.fila(b), mods_b[:4])

        atribuir(self.admin, mods_a[2], a)
        atribuir(self.admin, mods_b[4], b)
        self.assertEqual(self.fila(a), mods_a)
        self.assertEqual(self.fila(b), mods_b)

        card = self.admin.get(f"/api/objetos/{mods_a[2]}").get_json()
        prio = next(p for p in card["prioridades_fase_atual"] if p["funcionario_id"] == a)
        self.assertEqual((prio["prioridade"], prio["total"]), (3, 3))

    def test_mover_para_posicao_desloca_os_demais(self):
        f = self.novo_revisor()
        m1, m2, m3 = (self.novo_modulo() for _ in range(3))
        for m in (m1, m2, m3):
            atribuir(self.admin, m, f)

        res = self.admin.post(f"/api/prioridades/{f}/mover", json={"objeto_fase_id": self.of_id(m3), "posicao": 1})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(self.fila(f), [m3, m1, m2])

        # Posição fora da faixa é limitada a 1..n
        self.admin.post(f"/api/prioridades/{f}/mover", json={"objeto_fase_id": self.of_id(m3), "posicao": 99})
        self.assertEqual(self.fila(f), [m1, m2, m3])

    def test_reordenar_fila_inteira_e_recusar_fila_desatualizada(self):
        f = self.novo_revisor()
        m1, m2, m3 = (self.novo_modulo() for _ in range(3))
        for m in (m1, m2, m3):
            atribuir(self.admin, m, f)

        ordem = [self.of_id(m) for m in (m2, m3, m1)]
        res = self.admin.put(f"/api/prioridades/{f}", json={"ordem": ordem})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(self.fila(f), [m2, m3, m1])

        # Faltando um trabalho (a tela estava desatualizada) → 409 e nada muda
        res = self.admin.put(f"/api/prioridades/{f}", json={"ordem": ordem[:2]})
        self.assertEqual(res.status_code, 409)
        self.assertEqual(self.fila(f), [m2, m3, m1])
        # Repetido → 409
        res = self.admin.put(f"/api/prioridades/{f}", json={"ordem": [ordem[0]] * 3})
        self.assertEqual(res.status_code, 409)

    def test_aprovacao_libera_a_posicao(self):
        f = self.novo_revisor(com_login=True)
        colega = self.novo_revisor()
        m1, m2, m3 = (self.novo_modulo() for _ in range(3))
        for m in (m1, m2, m3):
            atribuir(self.admin, m, f)
        atribuir(self.admin, m2, colega)  # dupla aprovação em m2

        email = self.admin.get(f"/api/prioridades/{f}").get_json()["funcionario"]["nome"]
        with app.app_context():
            login = Usuario.query.filter_by(nome=email).first().email
        res = cliente_logado(login).post(f"/api/objeto-fase/{self.of_id(m2)}/aprovar")
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertFalse(res.get_json()["movido"])  # colega ainda não aprovou

        self.assertEqual(self.fila(f), [m1, m3])
        card = self.admin.get(f"/api/objetos/{m2}").get_json()
        prio_f = next(p for p in card["prioridades_fase_atual"] if p["funcionario_id"] == f)
        self.assertTrue(prio_f["aprovado"])
        self.assertIsNone(prio_f["prioridade"])
        self.assertEqual(self.fila(colega), [m2])

    def test_concluir_fase_libera_equipe_e_coloca_proximo_no_fim(self):
        f, proximo = self.novo_revisor(), self.novo_revisor()
        ja_tinha = self.novo_modulo()
        atribuir(self.admin, ja_tinha, proximo)

        m1, m2 = self.novo_modulo(funcionario_envio=proximo), self.novo_modulo()
        atribuir(self.admin, m1, f)
        atribuir(self.admin, m2, f)

        res = self.admin.post(f"/api/objetos/{m1}/concluir-fase")
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(self.fila(f), [m2])
        self.assertEqual(self.fila(proximo), [ja_tinha, m1])

    def test_mover_fase_manual_libera_equipe(self):
        f = self.novo_revisor()
        m1, m2 = self.novo_modulo(), self.novo_modulo()
        atribuir(self.admin, m1, f)
        atribuir(self.admin, m2, f)
        res = self.admin.post(f"/api/objetos/{m1}/mover-fase", json={"fase_id": self.envio})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(self.fila(f), [m2])

    def test_remover_e_reatribuir_equipe_renumeram(self):
        f, outro = self.novo_revisor(), self.novo_revisor()
        m1, m2, m3 = (self.novo_modulo() for _ in range(3))
        for m in (m1, m2, m3):
            atribuir(self.admin, m, f)

        res = self.admin.post(f"/api/objeto-fase/{self.of_id(m1)}/remover", json={"funcionario_id": f})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(self.fila(f), [m2, m3])

        res = self.admin.put(f"/api/objetos/{m2}/reatribuir-fase", json={"funcionarios_ids": [outro]})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(self.fila(f), [m3])
        self.assertEqual(self.fila(outro), [m2])

    def test_excluir_modulo_renumera(self):
        f = self.novo_revisor()
        projeto = criar_projeto(self.admin, [
            {"nome": "Excluir A", "fase_id": self.revisao},
            {"nome": "Excluir B", "fase_id": self.revisao},
        ])
        a, b = (o["id"] for o in projeto["objetos"])
        atribuir(self.admin, a, f)
        atribuir(self.admin, b, f)
        self.assertEqual(self.admin.delete(f"/api/objetos/{a}").status_code, 200)
        self.assertEqual(self.fila(f), [b])

        self.assertEqual(self.admin.delete(f"/api/projetos/{projeto['id']}").status_code, 200)
        self.assertEqual(self.fila(f), [])

    def test_permissoes(self):
        f = self.novo_revisor()
        m = self.novo_modulo()
        atribuir(self.admin, m, f)
        gestor = cliente_logado(GESTOR)
        self.assertEqual(gestor.get("/api/prioridades").status_code, 200)
        self.assertEqual(gestor.put(f"/api/prioridades/{f}", json={"ordem": [self.of_id(m)]}).status_code, 403)
        self.assertEqual(gestor.post(f"/api/prioridades/{f}/mover",
                                     json={"objeto_fase_id": self.of_id(m), "posicao": 1}).status_code, 403)
        carol = cliente_logado("carol@mind.com.br")
        self.assertEqual(carol.get("/api/prioridades").status_code, 403)

    def test_priorizacao_inicial_respeita_flags_antigas(self):
        from prioridades import priorizacao_inicial
        f = self.novo_revisor()
        m_sem, m_urgente, m_importante = (self.novo_modulo() for _ in range(3))
        for m in (m_sem, m_urgente, m_importante):
            atribuir(self.admin, m, f)
        with app.app_context():
            db.session.get(Objeto, m_urgente).prioridade = 3
            db.session.get(Objeto, m_importante).prioridade = 1
            # Simula o banco antes da migração: sem prioridade numérica
            db.session.execute(off.update().where(off.c.id_funcionario == f).values(prioridade=None))
            db.session.commit()
            priorizacao_inicial()
            db.session.commit()
        self.assertEqual(self.fila(f), [m_urgente, m_importante, m_sem])

    def test_ensure_schema_adiciona_coluna_em_banco_antigo(self):
        """Banco criado antes desta versão (sem a coluna) é migrado no boot."""
        import os
        import tempfile
        from sqlalchemy import create_engine, inspect, text
        caminho = os.path.join(tempfile.mkdtemp(), "antigo.db")
        engine = create_engine(f"sqlite:///{caminho}")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE objeto_fase_funcionario (id_objeto_fase INTEGER, id_funcionario INTEGER, "
                              "atribuido_em DATETIME, aprovado_em DATETIME)"))
        from schema import _adicionar_coluna
        uri_original = app.config["SQLALCHEMY_DATABASE_URI"]
        with app.app_context():
            ext = app.extensions["sqlalchemy"]
            ext._app_engines[app][None] = engine
            try:
                self.assertTrue(_adicionar_coluna("objeto_fase_funcionario", "prioridade", "INTEGER NULL"))
                self.assertFalse(_adicionar_coluna("objeto_fase_funcionario", "prioridade", "INTEGER NULL"))
            finally:
                db.session.remove()
                ext._app_engines[app][None] = create_engine(uri_original)
        cols = {c["name"] for c in inspect(engine).get_columns("objeto_fase_funcionario")}
        self.assertIn("prioridade", cols)


if __name__ == "__main__":
    unittest.main()
