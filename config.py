import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configurações da aplicação GERENCIAMENTO-MIND."""

    # ─── Flask ────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "gerenciamento-mind-dev-secret-2026")

    # ─── Banco de dados ──────────────────────────────────────────────────────
    # Desenvolvimento: SQLite local
    # Produção: mysql+pymysql://user:pass@host/db
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///gerenciamento.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ─── Acesso ──────────────────────────────────────────────────────────────
    # Usuários cujo funcionário tem uma destas funções têm acesso de admin,
    # independentemente do perfil cadastrado (separadas por vírgula).
    FUNCOES_ADMIN = [
        f.strip().lower()
        for f in os.environ.get("FUNCOES_ADMIN", "Diretor,Gerente").split(",")
        if f.strip()
    ]
    # O MySQL do PythonAnywhere encerra conexões paradas há ~5 min. Sem isto, a
    # primeira consulta depois de um tempo sem uso falha ("MySQL server has gone
    # away") e a página dá erro 500. pool_recycle renova a conexão antes disso e
    # pool_pre_ping descarta conexões mortas antes de usá-las.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    # ─── E-mail ──────────────────────────────────────────────────────────────
    # EMAIL_ATIVO=false: os e-mails só aparecem no log (simulação)
    EMAIL_ATIVO = os.environ.get("EMAIL_ATIVO", "false").lower() == "true"
    # "smtp" (Gmail, Google Workspace, outro servidor) ou "brevo" (API HTTP,
    # funciona no plano gratuito do PythonAnywhere)
    EMAIL_PROVEDOR = os.environ.get("EMAIL_PROVEDOR", "smtp").lower()
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    # Endereço público do sistema, usado no botão "Abrir" dos e-mails
    APP_URL = os.environ.get("APP_URL", "")
    # Modo de teste: se preenchido, TODOS os e-mails vão para este endereço (o
    # destinatário original aparece no assunto). Deixe vazio em produção.
    EMAIL_REDIRECIONAR_PARA = os.environ.get("EMAIL_REDIRECIONAR_PARA", "").strip()
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.exemplo.com.br")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER", "sistema@exemplo.com.br")
    SMTP_PASS = os.environ.get("SMTP_PASS", "")
    EMAIL_REMETENTE = os.environ.get(
        "EMAIL_REMETENTE",
        "Gerenciamento MIND <sistema@exemplo.com.br>"
    )

    # ─── SLA ──────────────────────────────────────────────────────────────────
    # Horário de verificação diária do SLA (usado pelo sla_checker)
    SLA_CHECK_HOUR = int(os.environ.get("SLA_CHECK_HOUR", 8))
    SLA_CHECK_MINUTE = int(os.environ.get("SLA_CHECK_MINUTE", 0))
