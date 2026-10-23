"""Notificações por e-mail: fila, gatilhos e transporte."""
import unittest
from unittest import mock

from helpers import (
    app, db, ADMIN, cliente_logado, criar_projeto, atribuir, funcionario_id, fase_id, fase_ativa_id,
)
from models import EmailPendente
import notifications


def emails_para(email, tipo=None):
    with app.app_context():
        q = EmailPendente.query.filter_by(destinatario=email)
        if tipo:
            q = q.filter_by(tipo=tipo)
        return q.all()


def limpar_fila():
    with app.app_context():
        EmailPendente.query.delete()
        db.session.commit()


class NotificacoesTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.admin = cliente_logado(ADMIN)
        cls.revisao = fase_id("Revisão Ortográfica")
        cls.envio = fase_id("Envio ao Cliente")
        cls.renato = funcionario_id("Renato")
        cls.lucas = funcionario_id("Lucas")

    def setUp(self):
        limpar_fila()

    def novo_modulo(self, **extra):
        projeto = criar_projeto(self.admin, [{"nome": "Notif", "fase_id": self.revisao, **extra}])
        return projeto["objetos"][0]["id"]

    def test_atribuicao_gera_email_enviado_apos_a_resposta(self):
        oid = self.novo_modulo()
        res = self.admin.post(f"/api/objeto-fase/{fase_ativa_id(self.admin, oid)}/atribuir",
                              json={"funcionario_id": self.renato})
        self.assertEqual(res.status_code, 200)
        emails = emails_para("renato@mind.com.br", "atribuicao")
        self.assertEqual(len(emails), 1)
        self.assertIsNone(emails[0].enviado_em)  # na fila, ainda não enviado

        # O servidor WSGI fecha a resposta depois de entregá-la; só então o envio roda.
        # (O cliente de teste não fecha sozinho.) Em simulação, o e-mail é marcado como enviado.
        res.close()
        self.assertIsNotNone(emails_para("renato@mind.com.br", "atribuicao")[0].enviado_em)

    def test_quem_faz_a_acao_nao_recebe_email(self):
        eduardo = funcionario_id("Eduardo")  # o admin logado nos testes
        projeto = criar_projeto(self.admin, [{"nome": "Notif", "fase_id": self.envio}])  # fase sem função exigida
        atribuir(self.admin, projeto["objetos"][0]["id"], eduardo)
        self.assertEqual(emails_para("eduardo@mind.com.br"), [])

    def test_comentario_avisa_equipe_e_responsavel_menos_o_autor(self):
        oid = self.novo_modulo(responsavel_id=self.lucas)
        atribuir(self.admin, oid, self.renato)
        limpar_fila()
        renato = cliente_logado("renato@mind.com.br")
        res = renato.post(f"/api/objetos/{oid}/comentarios", json={"texto": "Revisão <b>feita</b>"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(emails_para("lucas@mind.com.br", "comentario")), 1)
        self.assertEqual(emails_para("renato@mind.com.br"), [])  # autor
        # Texto do comentário é escapado no HTML
        self.assertIn("&lt;b&gt;feita&lt;/b&gt;", emails_para("lucas@mind.com.br", "comentario")[0].corpo_html)

    def test_mudanca_de_prioridade_avisa_o_funcionario(self):
        m1, m2 = self.novo_modulo(), self.novo_modulo()
        atribuir(self.admin, m1, self.lucas)
        atribuir(self.admin, m2, self.lucas)
        limpar_fila()
        of2 = fase_ativa_id(self.admin, m2)
        res = self.admin.post(f"/api/prioridades/{self.lucas}/mover", json={"objeto_fase_id": of2, "posicao": 1})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(emails_para("lucas@mind.com.br", "prioridade")), 1)

        # Mesma posição: nada mudou, nenhum e-mail
        limpar_fila()
        self.admin.post(f"/api/prioridades/{self.lucas}/mover", json={"objeto_fase_id": of2, "posicao": 1})
        self.assertEqual(emails_para("lucas@mind.com.br", "prioridade"), [])

    def test_remocao_e_reatribuicao(self):
        oid = self.novo_modulo()
        atribuir(self.admin, oid, self.renato)
        limpar_fila()
        res = self.admin.put(f"/api/objetos/{oid}/reatribuir-fase", json={"funcionarios_ids": [self.lucas]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(emails_para("lucas@mind.com.br", "atribuicao")), 1)
        self.assertEqual(len(emails_para("renato@mind.com.br", "remocao")), 1)

        limpar_fila()
        of_id = fase_ativa_id(self.admin, oid)
        self.admin.post(f"/api/objeto-fase/{of_id}/remover", json={"funcionario_id": self.lucas})
        self.assertEqual(len(emails_para("lucas@mind.com.br", "remocao")), 1)

    def test_inclusao_no_roadmap_avisa_so_quem_entrou(self):
        oid = self.novo_modulo(etapas_pre_definidas=[
            {"fase_id": self.revisao}, {"fase_id": self.envio, "funcionario_id": self.renato},
        ])
        self.assertEqual(len(emails_para("renato@mind.com.br", "roadmap")), 1)
        limpar_fila()
        # Mantém Renato e inclui Lucas numa nova etapa: só Lucas é avisado
        res = self.admin.put(f"/api/objetos/{oid}", json={"etapas_pre_definidas": [
            {"fase_id": self.revisao}, {"fase_id": self.envio, "funcionario_id": self.renato},
            {"fase_id": self.revisao, "funcionario_id": self.lucas},
        ]})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(emails_para("renato@mind.com.br", "roadmap"), [])
        self.assertEqual(len(emails_para("lucas@mind.com.br", "roadmap")), 1)

    def test_acao_que_falha_nao_envia_email(self):
        oid = self.novo_modulo()
        res = self.admin.put(f"/api/objetos/{oid}", json={"etapas_pre_definidas": [{"fase_id": 999999}]})
        self.assertEqual(res.status_code, 400)
        with app.app_context():
            self.assertEqual(EmailPendente.query.count(), 0)

    def test_falha_de_envio_fica_na_fila_para_nova_tentativa(self):
        with app.app_context():
            db.session.add(EmailPendente(destinatario="x@teste.com", assunto="A", corpo_html="<p>oi</p>"))
            db.session.commit()
            app.config["EMAIL_ATIVO"] = True
            try:
                with mock.patch.object(notifications, "_enviar_smtp", side_effect=OSError("sem rede")):
                    self.assertEqual(notifications.processar_fila(), (0, 1))
                e = EmailPendente.query.filter_by(destinatario="x@teste.com").one()
                self.assertIsNone(e.enviado_em)
                self.assertEqual(e.tentativas, 1)
                self.assertIn("sem rede", e.ultimo_erro)

                with mock.patch.object(notifications, "_enviar_smtp") as envio:
                    self.assertEqual(notifications.processar_fila(), (1, 0))
                    envio.assert_called_once()
                self.assertIsNotNone(EmailPendente.query.filter_by(destinatario="x@teste.com").one().enviado_em)
            finally:
                app.config["EMAIL_ATIVO"] = False

    def test_provedor_brevo_usa_api_http(self):
        with app.app_context():
            db.session.add(EmailPendente(destinatario="y@teste.com", assunto="Assunto", corpo_html="<p>oi</p>"))
            db.session.commit()
            app.config.update(EMAIL_ATIVO=True, EMAIL_PROVEDOR="brevo", BREVO_API_KEY="chave-teste",
                              EMAIL_REMETENTE="Gerenciamento MIND <sistema@mind.com.br>")
            try:
                resposta = mock.MagicMock(status=201)
                resposta.__enter__.return_value = resposta
                with mock.patch("urllib.request.urlopen", return_value=resposta) as urlopen:
                    self.assertEqual(notifications.processar_fila(), (1, 0))
                req = urlopen.call_args[0][0]
                self.assertEqual(req.full_url, "https://api.brevo.com/v3/smtp/email")
                self.assertEqual(req.get_header("Api-key"), "chave-teste")
                self.assertIn(b'"y@teste.com"', req.data)
                self.assertIn(b'"sistema@mind.com.br"', req.data)
            finally:
                app.config.update(EMAIL_ATIVO=False, EMAIL_PROVEDOR="smtp")

    def test_comando_processar_emails(self):
        with app.app_context():
            db.session.add(EmailPendente(destinatario="z@teste.com", assunto="A", corpo_html="<p>oi</p>"))
            db.session.commit()
        resultado = app.test_cli_runner().invoke(args=["processar-emails"])
        self.assertIn("E-mails enviados: 1", resultado.output)


if __name__ == "__main__":
    unittest.main()
