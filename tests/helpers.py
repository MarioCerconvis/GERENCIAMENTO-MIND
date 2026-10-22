"""
Utilitários compartilhados pelos testes.

Importar este módulo ANTES de `app`: ele aponta o app para um banco SQLite
temporário (o banco de desenvolvimento em instance/ nunca é tocado) e desliga
o envio de e-mails. O seed de dados reais roda no banco temporário, então os
testes podem usar os funcionários e fases da Mind.

Rodar: venv/bin/python -m unittest discover -s tests -v
"""
import os
import sys
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="gerenciamento-mind-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP_DIR, 'test.db')}"
os.environ["EMAIL_ATIVO"] = "false"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, db  # noqa: E402
from models import Usuario, Funcionario, Fase  # noqa: E402

app.config["TESTING"] = True

_contador_os = [0]


def nova_os():
    """Código de OS único para cada projeto criado nos testes."""
    _contador_os[0] += 1
    return f"TESTE-{os.getpid()}-{_contador_os[0]}"


def usuario_id(email):
    with app.app_context():
        return Usuario.query.filter_by(email=email).first().id


def funcionario_id(nome):
    with app.app_context():
        return Funcionario.query.filter_by(nome=nome).first().id_func


def fase_id(nome):
    with app.app_context():
        return Fase.query.filter_by(nome_fase=nome).first().id_fase


def cliente_logado(email):
    """Test client com sessão do usuário informado."""
    client = app.test_client()
    uid = usuario_id(email)
    with client.session_transaction() as sess:
        sess["usuario_id"] = uid
    return client


ADMIN = "eduardo@mind.com.br"
GESTOR = "john@mind.com.br"


def criar_projeto(client, objetos, **campos):
    """Cria uma OS via API e devolve o JSON do projeto."""
    body = {
        "os": nova_os(),
        "nome": "Projeto de teste",
        "data_limite": "2030-12-31",
        "objetos": objetos,
    }
    body.update(campos)
    res = client.post("/api/projetos", json=body)
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def fase_ativa_id(client, objeto_id):
    return client.get(f"/api/objetos/{objeto_id}").get_json()["fase_ativa_id"]


def atribuir(client, objeto_id, func_id):
    of_id = fase_ativa_id(client, objeto_id)
    res = client.post(f"/api/objeto-fase/{of_id}/atribuir", json={"funcionario_id": func_id})
    assert res.status_code == 200, res.get_json()
    return res.get_json()
