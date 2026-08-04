import asyncio
import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)

from app.core.config import get_settings


logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """
    Erro interno lançado quando não for possível
    enviar um e-mail.
    """

    pass


class EmailService:
    """
    Serviço responsável pelo envio de e-mails
    relacionados à autenticação.
    """

    def build_password_reset_url(
        self,
        token: str,
    ) -> str:
        """
        Adiciona o token à URL do frontend.

        Exemplo:

        http://localhost:5173/reset-password?token=abc123
        """

        settings = get_settings()

        base_url = (
            settings.frontend_reset_password_url.strip()
        )

        parsed_url = urlsplit(base_url)

        query_parameters = dict(
            parse_qsl(
                parsed_url.query,
                keep_blank_values=True,
            )
        )

        query_parameters["token"] = token

        return urlunsplit(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                urlencode(query_parameters),
                parsed_url.fragment,
            )
        )

    async def send_password_reset_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        token: str,
    ) -> None:
        """
        Envia o e-mail com o link de recuperação.

        Em desenvolvimento, quando SMTP_ENABLED=false,
        o link é exibido no terminal.
        """

        settings = get_settings()

        reset_url = self.build_password_reset_url(
            token
        )

        if not settings.smtp_enabled:
            if settings.app_environment == "production":
                logger.error(
                    "SMTP está desabilitado em produção. "
                    "O e-mail de recuperação não foi enviado."
                )

                raise EmailDeliveryError(
                    "Serviço de e-mail não configurado."
                )

            logger.warning(
                "\n"
                "==================================================\n"
                "RECUPERAÇÃO DE SENHA — AMBIENTE DE DESENVOLVIMENTO\n"
                "Destinatário: %s\n"
                "Link: %s\n"
                "==================================================",
                recipient_email,
                reset_url,
            )

            return

        message = self._create_password_reset_message(
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            reset_url=reset_url,
        )

        try:
            # smtplib é síncrono. O envio é colocado em outra
            # thread para não bloquear o event loop do FastAPI.
            await asyncio.to_thread(
                self._send_smtp_message,
                message,
            )

        except (
            smtplib.SMTPException,
            OSError,
        ) as exc:
            logger.exception(
                "Falha ao enviar e-mail de recuperação "
                "para %s.",
                recipient_email,
            )

            raise EmailDeliveryError(
                "Não foi possível enviar o e-mail "
                "de recuperação."
            ) from exc

    def _create_password_reset_message(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        reset_url: str,
    ) -> EmailMessage:
        """
        Monta as versões texto e HTML do e-mail.
        """

        settings = get_settings()

        message = EmailMessage()

        message["Subject"] = (
            "Redefinição de senha — "
            f"{settings.app_name}"
        )

        message["From"] = settings.smtp_from_email
        message["To"] = recipient_email

        plain_text = f"""
Olá, {recipient_name}.

Recebemos uma solicitação para redefinir a senha da sua conta.

Acesse o link abaixo para criar uma nova senha:

{reset_url}

O link expira em {
    settings.password_reset_token_minutes
} minutos e poderá ser utilizado apenas uma vez.

Caso você não tenha solicitado essa alteração, ignore este e-mail.

{settings.app_name}
""".strip()

        html_content = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
</head>
<body
    style="
        margin: 0;
        padding: 24px;
        background-color: #f5f5f5;
        font-family: Arial, sans-serif;
        color: #222222;
    "
>
    <div
        style="
            max-width: 600px;
            margin: 0 auto;
            padding: 32px;
            background-color: #ffffff;
            border-radius: 8px;
        "
    >
        <h2 style="margin-top: 0;">
            Redefinição de senha
        </h2>

        <p>
            Olá, {recipient_name}.
        </p>

        <p>
            Recebemos uma solicitação para redefinir
            a senha da sua conta.
        </p>

        <p>
            Clique no botão abaixo para criar uma
            nova senha:
        </p>

        <p style="margin: 32px 0;">
            <a
                href="{reset_url}"
                style="
                    display: inline-block;
                    padding: 12px 20px;
                    background-color: #222222;
                    color: #ffffff;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: bold;
                "
            >
                Redefinir senha
            </a>
        </p>

        <p>
            O link expira em
            <strong>
                {settings.password_reset_token_minutes}
                minutos
            </strong>
            e poderá ser utilizado apenas uma vez.
        </p>

        <p>
            Caso você não tenha solicitado essa alteração,
            ignore este e-mail.
        </p>

        <hr
            style="
                border: 0;
                border-top: 1px solid #dddddd;
                margin: 24px 0;
            "
        >

        <small>
            {settings.app_name}
        </small>
    </div>
</body>
</html>
""".strip()

        message.set_content(
            plain_text
        )

        message.add_alternative(
            html_content,
            subtype="html",
        )

        return message

    def _send_smtp_message(
        self,
        message: EmailMessage,
    ) -> None:
        """
        Executa o envio SMTP de forma síncrona.

        Esse método é chamado por asyncio.to_thread().
        """

        settings = get_settings()

        if not settings.smtp_host:
            raise EmailDeliveryError(
                "SMTP_HOST não configurado."
            )

        smtp_password = (
            settings.smtp_password.get_secret_value()
            if settings.smtp_password is not None
            else None
        )

        with smtplib.SMTP(
            host=settings.smtp_host,
            port=settings.smtp_port,
            timeout=30,
        ) as smtp:
            smtp.ehlo()

            if settings.smtp_use_tls:
                smtp.starttls()
                smtp.ehlo()

            if (
                settings.smtp_username
                and smtp_password
            ):
                smtp.login(
                    settings.smtp_username,
                    smtp_password,
                )

            smtp.send_message(
                message
            )


def get_email_service() -> EmailService:
    """
    Retorna uma instância do serviço de e-mail.
    """

    return EmailService()