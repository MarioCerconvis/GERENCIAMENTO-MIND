"""
Notificações por e-mail.

Fluxo:
1. As funções notificar_*() montam o e-mail e chamam enviar_email(), que só
   grava o e-mail na fila (tabela emails_pendentes) na mesma transação da ação.
2. Ao fim da requisição, o app agenda processar_fila() para depois que a
   resposta foi entregue (response.call_on_close) — o usuário não espera o envio
   e não usamos threads (o PythonAnywhere não permite threads em web apps).
3. Falhas ficam na fila e são tentadas de novo no próximo envio ou pelo comando
   `flask processar-emails` (tarefa agendada, nos planos pagos).

Provedores (variável EMAIL_PROVEDOR):
- "smtp"  : qualquer servidor SMTP (Gmail com senha de app, Google Workspace...).
- "brevo" : API HTTP do Brevo — funciona no plano gratuito do PythonAnywhere,
            que só libera HTTP(S) para sites da lista de permitidos.
Com EMAIL_ATIVO=false nada é enviado: o e-mail é impresso no log (simulação).
"""
import html
import json
import re
import smtplib
import urllib.error
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr

from flask import current_app, g, has_request_context

MAX_TENTATIVAS = 5
TIMEOUT_ENVIO = 15  # segundos


def _get_config():
    return {
        "ativo": current_app.config.get("EMAIL_ATIVO", False),
        "provedor": current_app.config.get("EMAIL_PROVEDOR", "smtp"),
        "smtp_host": current_app.config.get("SMTP_HOST", ""),
        "smtp_port": current_app.config.get("SMTP_PORT", 587),
        "smtp_user": current_app.config.get("SMTP_USER", ""),
        "smtp_pass": current_app.config.get("SMTP_PASS", ""),
        "brevo_api_key": current_app.config.get("BREVO_API_KEY", ""),
        "remetente": current_app.config.get("EMAIL_REMETENTE", ""),
        "app_url": current_app.config.get("APP_URL", "").rstrip("/"),
        "redirecionar_para": current_app.config.get("EMAIL_REDIRECIONAR_PARA", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Fila
# ═══════════════════════════════════════════════════════════════════════════════

def _email_usuario_logado():
    if not has_request_context():
        return None
    from auth import get_usuario_logado
    u = get_usuario_logado()
    return u.email.lower() if u and u.email else None


def enviar_email(destinatarios, assunto, corpo_html, tipo="geral"):
    """Coloca o e-mail na fila (um registro por destinatário).

    Quem fez a ação não recebe e-mail sobre ela. Não faz commit: o e-mail só
    existe se a transação da ação for confirmada.
    """
    from models import db, EmailPendente

    autor = _email_usuario_logado()
    vistos = set()
    for d in destinatarios or []:
        email = (d or "").strip().lower()
        if not email or email in vistos or email == autor:
            continue
        vistos.add(email)
        db.session.add(EmailPendente(destinatario=email, assunto=assunto[:255], corpo_html=corpo_html, tipo=tipo))

    if vistos and has_request_context():
        g.despachar_emails = True


def _enviar_smtp(cfg, destinatario, assunto, corpo_html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = cfg["remetente"] or cfg["smtp_user"]
    msg["To"] = destinatario
    msg.attach(MIMEText(_html_para_texto(corpo_html), "plain", "utf-8"))
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))
    porta = int(cfg["smtp_port"])
    if porta == 465:
        servidor = smtplib.SMTP_SSL(cfg["smtp_host"], porta, timeout=TIMEOUT_ENVIO)
    else:
        servidor = smtplib.SMTP(cfg["smtp_host"], porta, timeout=TIMEOUT_ENVIO)
    with servidor as s:
        if porta != 465:
            s.starttls()
        s.login(cfg["smtp_user"], cfg["smtp_pass"])
        s.sendmail(cfg["smtp_user"], [destinatario], msg.as_string())


def _enviar_brevo(cfg, destinatario, assunto, corpo_html):
    nome, email = parseaddr(cfg["remetente"])
    payload = {
        "sender": {"name": nome or "Gerenciamento MIND", "email": email},
        "to": [{"email": destinatario}],
        "subject": assunto,
        "htmlContent": corpo_html,
        "textContent": _html_para_texto(corpo_html),
    }
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": cfg["brevo_api_key"],
            "accept": "application/json",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        # urllib respeita o proxy HTTPS configurado pelo PythonAnywhere (plano gratuito)
        with urllib.request.urlopen(req, timeout=TIMEOUT_ENVIO) as resp:
            if resp.status >= 300:
                raise RuntimeError(f"Brevo respondeu {resp.status}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Brevo respondeu {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


def _html_para_texto(corpo_html):
    texto = re.sub(r"<br[^>]*>|</p>|</tr>|</h2>", "\n", corpo_html)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    return re.sub(r"[ \t]+", " ", texto).strip()


def _transportar(cfg, email):
    if not cfg["ativo"]:
        print(f"\n{'='*60}\n[SIMULACAO DE E-MAIL]\nPara: {email.destinatario}\n"
              f"Assunto: {email.assunto}\n{_html_para_texto(email.corpo_html)}\n{'='*60}\n")
        return
    destinatario, assunto = email.destinatario, email.assunto
    if cfg["redirecionar_para"]:
        # Modo de teste: tudo vai para um endereço só, sem incomodar os funcionários
        assunto = f"[TESTE → {destinatario}] {assunto}"
        destinatario = cfg["redirecionar_para"]
    if cfg["provedor"] == "brevo":
        _enviar_brevo(cfg, destinatario, assunto, email.corpo_html)
    else:
        _enviar_smtp(cfg, destinatario, assunto, email.corpo_html)


def enviar_teste(destinatario):
    """Envia um e-mail de teste na hora (sem fila). Levanta a exceção do provedor se falhar."""
    from types import SimpleNamespace
    cfg = _get_config()
    if not cfg["ativo"]:
        raise RuntimeError("EMAIL_ATIVO não está como true no .env — nada seria enviado.")
    corpo = _email_wrap("Teste de e-mail", "#22c55e", [
        ("Provedor:", _esc(cfg["provedor"])),
        ("Remetente:", _esc(cfg["remetente"])),
    ], extra_html="<p>Se você recebeu esta mensagem, as notificações do Gerenciamento MIND estão funcionando.</p>")
    _transportar(cfg, SimpleNamespace(destinatario=destinatario, assunto="[MIND] Teste de e-mail", corpo_html=corpo))


def processar_fila(limite=50):
    """Envia os e-mails pendentes. Retorna (enviados, falhas). Faz commit."""
    from models import db, EmailPendente

    cfg = _get_config()
    pendentes = (
        EmailPendente.query
        .filter(EmailPendente.enviado_em.is_(None), EmailPendente.tentativas < MAX_TENTATIVAS)
        .order_by(EmailPendente.id)
        .limit(limite)
        .all()
    )
    enviados = falhas = 0
    for email in pendentes:
        try:
            _transportar(cfg, email)
            email.enviado_em = datetime.utcnow()
            email.ultimo_erro = None
            enviados += 1
        except Exception as e:  # noqa: BLE001 — qualquer falha fica registrada para nova tentativa
            email.tentativas += 1
            email.ultimo_erro = str(e)[:1000]
            falhas += 1
            print(f"[ERRO E-MAIL] {email.destinatario}: {e}")
        db.session.commit()  # registra cada envio: se o processo cair, não reenvia os já enviados
    return enviados, falhas


# ═══════════════════════════════════════════════════════════════════════════════
#  Templates
# ═══════════════════════════════════════════════════════════════════════════════

def _esc(valor):
    return html.escape(str(valor or ""))


def _chip_fase(fase):
    if not fase:
        return "Sem fase"
    return f'<span style="background:{_esc(fase.cor)};color:white;padding:2px 10px;border-radius:12px;">{_esc(fase.nome_fase)}</span>'


def _email_wrap(title, color, rows, extra_html=""):
    trs = ""
    for i, (label, value) in enumerate(rows):
        bg = "background:#f8fafc;" if i % 2 == 0 else ""
        trs += f'<tr style="{bg}"><td style="padding:10px 16px;color:#64748b;border-bottom:1px solid #e2e8f0;">{label}</td><td style="padding:10px 16px;border-bottom:1px solid #e2e8f0;">{value}</td></tr>'
    link = ""
    try:
        app_url = _get_config()["app_url"]
    except RuntimeError:
        app_url = ""
    if app_url:
        link = (f'<p><a href="{_esc(app_url)}/kanban" style="display:inline-block;background:#6366f1;color:white;'
                f'padding:10px 18px;border-radius:8px;text-decoration:none;">Abrir no Gerenciamento MIND</a></p>')
    return (f'<div style="font-family:Segoe UI,Arial,sans-serif;max-width:600px;"><h2 style="color:{color};">{title}</h2>'
            f'<table style="border-collapse:collapse;width:100%;margin:16px 0;">{trs}</table>{extra_html}{link}'
            f'<p style="font-size:12px;color:#94a3b8;">Gerenciamento MIND — notificação automática</p></div>')


def _os_modulo(projeto, objeto):
    return f"{projeto.os} - {objeto.nome}" if objeto else projeto.os


# ═══════════════════════════════════════════════════════════════════════════════
#  Notificações
# ═══════════════════════════════════════════════════════════════════════════════

def notificar_atribuicao(funcionario, projeto, fase, objeto=None):
    corpo = _email_wrap("Nova Atribuição de Módulo", "#6366f1", [
        ("Projeto (OS):", f"<strong>{_esc(_os_modulo(projeto, objeto))}</strong>"),
        ("Cliente:", _esc(projeto.cliente)),
        ("Fase:", _chip_fase(fase)),
        ("Prazo:", objeto.data_limite.strftime("%d/%m/%Y") if (objeto and objeto.data_limite) else (projeto.data_limite.strftime("%d/%m/%Y") if projeto.data_limite else "N/A")),
    ])
    enviar_email([funcionario.email], f"[MIND] Nova atribuição - {_os_modulo(projeto, objeto)} - {fase.nome_fase if fase else ''}",
                 corpo, tipo="atribuicao")


def notificar_remocao(funcionario, projeto, fase, objeto):
    corpo = _email_wrap("Você foi removido de uma fase", "#64748b", [
        ("Projeto (OS):", f"<strong>{_esc(_os_modulo(projeto, objeto))}</strong>"),
        ("Fase:", _chip_fase(fase)),
    ])
    enviar_email([funcionario.email], f"[MIND] Removido da fase - {_os_modulo(projeto, objeto)}", corpo, tipo="remocao")


def notificar_mudanca_fase(projeto, objeto, fase_nova, equipe_nova):
    corpo = _email_wrap("Módulo Movido para Nova Fase", "#6366f1", [
        ("Projeto (OS):", f"<strong>{_esc(_os_modulo(projeto, objeto))}</strong>"),
        ("Cliente:", _esc(projeto.cliente)),
        ("Nova fase:", _chip_fase(fase_nova)),
        ("Prazo do módulo:", objeto.data_limite.strftime("%d/%m/%Y") if objeto.data_limite else "N/A"),
    ])
    enviar_email([f.email for f in equipe_nova], f"[MIND] Módulo movido - {_os_modulo(projeto, objeto)} - {fase_nova.nome_fase}",
                 corpo, tipo="mudanca_fase")


def notificar_comentario(objeto, comentario, destinatarios):
    autor = comentario.usuario.nome if comentario.usuario else "Alguém"
    texto = _esc(comentario.texto).replace("\n", "<br>")
    corpo = _email_wrap("Novo comentário no card", "#0ea5e9", [
        ("Projeto (OS):", f"<strong>{_esc(_os_modulo(objeto.projeto, objeto))}</strong>"),
        ("Fase atual:", _chip_fase(objeto.fase_atual)),
        ("Autor:", _esc(autor)),
    ], extra_html=f'<blockquote style="margin:0 0 16px;padding:12px 16px;background:#f1f5f9;border-left:4px solid #0ea5e9;border-radius:4px;">{texto}</blockquote>')
    enviar_email(destinatarios, f"[MIND] Comentário de {autor} - {_os_modulo(objeto.projeto, objeto)}", corpo, tipo="comentario")


def notificar_prioridade(funcionario, itens, destacar_ids=()):
    """Envia a fila atualizada do funcionário. `itens` vem de app._fila_dict()["itens"]."""
    if not itens:
        return
    linhas = ""
    for item in itens:
        destaque = item["objeto_fase_id"] in destacar_ids
        estilo = "background:#eef2ff;font-weight:600;" if destaque else ""
        linhas += (f'<tr style="{estilo}"><td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:center;">'
                   f'<strong>{item["prioridade"]}</strong></td>'
                   f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">{_esc(item["os"])} - {_esc(item["modulo"])}'
                   f'{" ← alterado" if destaque else ""}</td>'
                   f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">{_esc(item["fase_nome"])}</td></tr>')
    tabela = ('<table style="border-collapse:collapse;width:100%;margin:0 0 16px;">'
              '<tr style="color:#64748b;text-align:left;"><th style="padding:8px 12px;">#</th><th style="padding:8px 12px;">OS - Módulo</th>'
              f'<th style="padding:8px 12px;">Fase</th></tr>{linhas}</table>')
    corpo = _email_wrap("Sua fila de prioridades mudou", "#f97316", [
        ("Funcionário:", _esc(funcionario.nome)),
        ("Trabalhos atuais:", str(len(itens))),
    ], extra_html=f'<p style="margin:0 0 8px;">Nova ordem (1 = mais importante):</p>{tabela}')
    enviar_email([funcionario.email], "[MIND] Sua fila de prioridades foi alterada", corpo, tipo="prioridade")


def notificar_etapa_futura(funcionario, objeto, fase, etapa):
    prazo = etapa.get("data_limite")
    corpo = _email_wrap("Você foi incluído no roadmap de um módulo", "#8b5cf6", [
        ("Projeto (OS):", f"<strong>{_esc(_os_modulo(objeto.projeto, objeto))}</strong>"),
        ("Etapa futura:", _chip_fase(fase)),
        ("Prazo previsto:", datetime.fromisoformat(prazo).strftime("%d/%m/%Y") if prazo else "A definir"),
    ], extra_html='<p style="font-size:13px;color:#64748b;">Você receberá outro aviso quando o módulo chegar a essa etapa.</p>')
    enviar_email([funcionario.email], f"[MIND] Etapa futura - {_os_modulo(objeto.projeto, objeto)} - {fase.nome_fase}",
                 corpo, tipo="roadmap")


def notificar_sla_estourado(projeto, responsavel, dias_atraso):
    if not responsavel or not responsavel.email:
        return
    corpo = _email_wrap("SLA Macro do Projeto Ultrapassado", "#ef4444", [
        ("Projeto (OS):", f"<strong>{_esc(projeto.os)}</strong>"),
        ("Cliente:", _esc(projeto.cliente)),
        ("Dias de atraso:", f'<strong style="color:#ef4444;">{dias_atraso} dia(s)</strong>'),
        ("Prazo original:", projeto.data_limite.strftime("%d/%m/%Y") if projeto.data_limite else "N/A"),
    ])
    enviar_email([responsavel.email], f"[MIND] SLA Macro ultrapassado - {projeto.os} - {dias_atraso} dia(s)", corpo, tipo="sla")


def notificar_sla_objeto_estourado(projeto, objeto, responsavel, dias_atraso):
    if not responsavel or not responsavel.email:
        return
    corpo = _email_wrap("SLA do Módulo Ultrapassado", "#ef4444", [
        ("Projeto (OS):", f"<strong>{_esc(_os_modulo(projeto, objeto))}</strong>"),
        ("Cliente:", _esc(projeto.cliente)),
        ("Dias de atraso:", f'<strong style="color:#ef4444;">{dias_atraso} dia(s)</strong>'),
        ("Fase atual:", _esc(objeto.fase_atual.nome_fase if objeto.fase_atual else "Sem fase")),
        ("Prazo original do Módulo:", objeto.data_limite.strftime("%d/%m/%Y") if objeto.data_limite else "N/A"),
    ])
    enviar_email([responsavel.email], f"[MIND] SLA Módulo ultrapassado - {_os_modulo(projeto, objeto)}", corpo, tipo="sla")


def notificar_sla_fase_estourado(projeto, objeto, responsavel, dias_atraso, fase_nome):
    if not responsavel or not responsavel.email:
        return
    corpo = _email_wrap("SLA da Fase Ultrapassado", "#ef4444", [
        ("Projeto (OS):", f"<strong>{_esc(_os_modulo(projeto, objeto))}</strong>"),
        ("Cliente:", _esc(projeto.cliente)),
        ("Fase Atrasada:", _esc(fase_nome)),
        ("Dias de atraso:", f'<strong style="color:#ef4444;">{dias_atraso} dia(s)</strong>'),
    ])
    enviar_email([responsavel.email], f"[MIND] SLA Fase ultrapassado - {_os_modulo(projeto, objeto)} - {fase_nome}", corpo, tipo="sla")
