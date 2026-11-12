# ruff: noqa: E501  (templates HTML longs volontaires)
"""Service d'envoi d'emails transactionnels.

Config SMTP : lue depuis la table system_settings (modifiable par l'admin),
avec fallback sur les variables d'environnement. Chaque envoi est journalisé
dans email_logs (traçabilité admin).
"""

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("revizio.mail")


# Cache de config SMTP (surchargé par l'admin via update_smtp_cache)
_smtp_override: dict = {}


def update_smtp_cache(cfg: dict) -> None:
    """Met à jour la config SMTP en mémoire (appelé par l'endpoint admin)."""
    _smtp_override.update(cfg)


def _smtp_config() -> dict:
    """Config SMTP effective (env par défaut ; surchargée par l'admin si présente)."""
    base = {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "user": settings.smtp_user,
        "password": settings.smtp_password,
        "use_tls": settings.smtp_use_tls,
        "from": settings.smtp_from,
    }
    base.update({k: v for k, v in _smtp_override.items() if v not in (None, "")})
    return base


def _send(to: str, subject: str, html: str, text: str = "", template: str = "") -> bool:
    cfg = _smtp_config()
    if not cfg["host"]:
        logger.info("[MAIL-DEV] to=%s subject=%s", to, subject)
        _log(to, subject, template, "logged", None)
        return True

    msg = EmailMessage()
    msg["From"] = cfg["from"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text or _strip_html(html))
    msg.add_alternative(html, subtype="html")

    try:
        if cfg["use_tls"]:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
                server.starttls()
                if cfg["user"]:
                    server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15) as server:
                if cfg["user"]:
                    server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        _log(to, subject, template, "sent", None)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Échec envoi email à %s: %s", to, exc)
        _log(to, subject, template, "failed", str(exc)[:300])
        return False


def _log(to: str, subject: str, template: str, status: str, error: str | None) -> None:
    """Journalise l'envoi (best-effort, ne bloque jamais)."""
    try:
        import asyncio

        from app.core.database import AsyncSessionLocal
        from app.models import EmailLog

        async def _write():
            async with AsyncSessionLocal() as db:
                db.add(
                    EmailLog(
                        to_email=to,
                        subject=subject,
                        template=template,
                        status=status,
                        error=error,
                    )
                )
                await db.commit()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_write())
        except RuntimeError:
            asyncio.run(_write())
    except Exception:  # noqa: BLE001
        pass


def _strip_html(html: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", html).strip()


def _layout(title: str, body: str, cta_url: str | None = None, cta_label: str = "") -> str:
    cta = (
        f'<p style="margin:24px 0"><a href="{cta_url}" '
        f'style="background:#00E5FF;color:#0A0B0F;padding:12px 24px;border-radius:8px;'
        f'text-decoration:none;font-weight:600">{cta_label}</a></p>'
        if cta_url
        else ""
    )
    return f"""<!doctype html><html><body style="margin:0;background:#0A0B0F;font-family:Inter,Arial,sans-serif">
<div style="max-width:560px;margin:0 auto;padding:32px 24px;color:#F0F2F8">
  <div style="font-size:22px;font-weight:700;color:#00E5FF;margin-bottom:24px">Revizio</div>
  <h1 style="font-size:20px;margin:0 0 16px">{title}</h1>
  <div style="font-size:15px;line-height:1.6;color:#A0A6B8">{body}</div>
  {cta}
  <hr style="border:none;border-top:1px solid #1F2330;margin:32px 0">
  <p style="font-size:12px;color:#5C6274">Revizio — enregistrez, transcrivez, révisez.</p>
</div></body></html>"""


def send_welcome(to: str, name: str) -> bool:
    body = f"""<p>Bonjour {name},</p>
<p>Bienvenue sur Revizio ! Votre compte est créé.</p>
<p>Pour enregistrer vos cours, téléchargez l'application desktop, puis connectez-vous
avec vos identifiants.</p>"""
    return _send(
        to,
        "Bienvenue sur Revizio",
        _layout("Bienvenue !", body, f"{settings.frontend_url}/download", "Télécharger l'app"),
        template="welcome",
    )


def send_password_reset(to: str, name: str, token: str) -> bool:
    url = f"{settings.frontend_url}/reset-password?token={token}"
    body = f"""<p>Bonjour {name},</p>
<p>Vous avez demandé la réinitialisation de votre mot de passe. Ce lien expire dans 1 heure.</p>
<p>Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.</p>"""
    return _send(
        to,
        "Réinitialisation de votre mot de passe",
        _layout("Mot de passe oublié", body, url, "Réinitialiser mon mot de passe"),
        template="password_reset",
    )


def send_quota_alert(to: str, name: str, used: str, quota: str) -> bool:
    body = f"""<p>Bonjour {name},</p>
<p>Vous avez atteint <strong>{used}</strong> sur un quota de <strong>{quota}</strong> ce mois-ci.</p>"""
    return _send(
        to,
        "Alerte quota Revizio",
        _layout(
            "Quota bientôt atteint", body, f"{settings.frontend_url}/settings", "Voir mes réglages"
        ),
        template="quota_alert",
    )


def send_key_request_notification(admin_email: str, user_email: str, provider: str) -> bool:
    body = f"""<p>L'utilisateur <strong>{user_email}</strong> demande une clé plateforme
pour le provider <strong>{provider}</strong>.</p>"""
    return _send(
        admin_email,
        "Revizio — demande de clé",
        _layout("Demande de clé", body, f"{settings.frontend_url}/admin", "Ouvrir l'admin"),
        template="key_request",
    )


def send_abuse_alert(admin_email: str, user_email: str, reason: str) -> bool:
    body = f"""<p>Activité suspecte détectée pour <strong>{user_email}</strong> :</p>
<p>{reason}</p>"""
    return _send(
        admin_email,
        "Revizio — alerte usage anormal",
        _layout("Usage anormal détecté", body, f"{settings.frontend_url}/admin", "Voir l'admin"),
        template="abuse_alert",
    )


def send_test(to: str) -> bool:
    body = "<p>Ceci est un email de test envoyé depuis l'administration Revizio.</p>"
    return _send(
        to,
        "Revizio — test SMTP",
        _layout("Test SMTP", body),
        template="test",
    )
