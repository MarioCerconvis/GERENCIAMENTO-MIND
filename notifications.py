import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app


def _get_config():
    return {
        "ativo": current_app.config.get("EMAIL_ATIVO", False),
        "smtp_host": current_app.config.get("SMTP_HOST", ""),
        "smtp_port": current_app.config.get("SMTP_PORT", 587),
        "smtp_user": current_app.config.get("SMTP_USER", ""),
        "smtp_pass": current_app.config.get("SMTP_PASS", ""),
        "remetente": current_app.config.get("EMAIL_REMETENTE", ""),
    }


def enviar_email(destinatarios, assunto, corpo_html):
    if not destinatarios:
        return
    cfg = _get_config()
    if not cfg["ativo"]:
        texto = re.sub(r"<br[^>]*>", "\n", corpo_html)
        texto = re.sub(r"<[^>]+>", "", texto).strip()
        print(f"\n{'='*60}\n[SIMULACAO DE E-MAIL]\nPara: {', '.join(destinatarios)}\nAssunto: {assunto}\n{texto}\n{'='*60}\n")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = cfg["remetente"]
        msg["To"] = ", ".join(destinatarios)
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as s:
            s.starttls()
            s.login(cfg["smtp_user"], cfg["smtp_pass"])
            s.sendmail(cfg["smtp_user"], destinatarios, msg.as_string())
    except Exception as e:
        print(f"[ERRO E-MAIL] {e}")


def _email_wrap(title, color, rows):
    trs = ""
    for i, (label, value) in enumerate(rows):
        bg = "background:#f8fafc;" if i % 2 == 0 else ""
        trs += f'<tr style="{bg}"><td style="padding:10px 16px;color:#64748b;border-bottom:1px solid #e2e8f0;">{label}</td><td style="padding:10px 16px;border-bottom:1px solid #e2e8f0;">{value}</td></tr>'
    return f'<div style="font-family:Segoe UI,Arial,sans-serif;max-width:600px;"><h2 style="color:{color};">{title}</h2><table style="border-collapse:collapse;width:100%;margin:16px 0;">{trs}</table><p style="font-size:12px;color:#94a3b8;">Gerenciamento MIND</p></div>'


def notificar_atribuicao(funcionario, projeto, fase):
    corpo = _email_wrap("Nova Atribuicao de Projeto", "#6366f1", [
        ("Projeto (OS):", f"<strong>{projeto.os}</strong>"),
        ("Cliente:", projeto.cliente or ""),
        ("Fase:", f'<span style="background:{fase.cor};color:white;padding:2px 10px;border-radius:12px;">{fase.nome_fase}</span>'),
        ("Prazo:", projeto.data_limite.strftime("%d/%m/%Y") if projeto.data_limite else "N/A"),
    ])
    enviar_email([funcionario.email], f"[MIND] Nova atribuicao - {projeto.os} - {fase.nome_fase}", corpo)


def notificar_sla_estourado(projeto, responsavel, dias_atraso):
    if not responsavel or not responsavel.email:
        return
    corpo = _email_wrap("Projeto Fora do SLA", "#ef4444", [
        ("Projeto (OS):", f"<strong>{projeto.os}</strong>"),
        ("Cliente:", projeto.cliente or ""),
        ("Dias de atraso:", f'<strong style="color:#ef4444;">{dias_atraso} dia(s)</strong>'),
        ("Fase atual:", projeto.fase_atual.nome_fase if projeto.fase_atual else "Sem fase"),
        ("Prazo original:", projeto.data_limite.strftime("%d/%m/%Y") if projeto.data_limite else "N/A"),
    ])
    enviar_email([responsavel.email], f"[MIND] SLA ultrapassado - {projeto.os} - {dias_atraso} dia(s)", corpo)


def notificar_mudanca_fase(projeto, fase_nova, equipe_nova):
    destinatarios = [f.email for f in equipe_nova if f.email]
    if not destinatarios:
        return
    corpo = _email_wrap("Projeto Movido para Nova Fase", "#6366f1", [
        ("Projeto (OS):", f"<strong>{projeto.os}</strong>"),
        ("Cliente:", projeto.cliente or ""),
        ("Nova fase:", f'<span style="background:{fase_nova.cor};color:white;padding:2px 10px;border-radius:12px;">{fase_nova.nome_fase}</span>'),
        ("Prazo:", projeto.data_limite.strftime("%d/%m/%Y") if projeto.data_limite else "N/A"),
    ])
    enviar_email(destinatarios, f"[MIND] Projeto movido - {projeto.os} - {fase_nova.nome_fase}", corpo)
