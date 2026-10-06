"""Códigos de recuperação; hashing e vinculação à conta fornecidos pelo Django."""
import logging
import secrets
from datetime import timedelta
from smtplib import SMTPException
from uuid import UUID

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .authentication import is_patient
from .forms import PatientPasswordResetForm
from .models import PatientPasswordResetCode, User

logger = logging.getLogger(__name__)


def eligible(user):
    return is_patient(user) and user.is_active and user.has_usable_password()


def issue_code(email):
    code = f'{secrets.randbelow(1_000_000):06d}'
    code_hash = make_password(code)
    # E-mails ambíguos não autorizam a recuperação de uma conta arbitrária.
    candidates = list(PatientPasswordResetForm().get_users(email))
    if len(candidates) != 1:
        return None
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=candidates[0].pk)
        if not eligible(user) or user.email.casefold() != email.casefold():
            return None
        previous = PatientPasswordResetCode.objects.filter(user=user).first()
        now = timezone.now()
        if previous and (now - previous.last_sent_at).total_seconds() < settings.PASSWORD_RESET_RESEND_INTERVAL:
            return str(previous.pk) if usable(previous) and not previous.verified_at else None
        PatientPasswordResetCode.objects.filter(user=user).delete()
        challenge = PatientPasswordResetCode.objects.create(
            user=user, code_hash=code_hash, state_token=default_token_generator.make_token(user),
            expires_at=now + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT), last_sent_at=now,
        )
        try:
            send_mail(
                'Código de recuperação de senha',
                render_to_string('accounts/password_reset_email.txt', {
                    'code': code, 'minutes': settings.PASSWORD_RESET_TIMEOUT // 60,
                }), settings.DEFAULT_FROM_EMAIL, [user.email],
            )
        except (OSError, SMTPException) as exc:
            # A resposta pública é igual mesmo em falhas de SMTP. Sem dados pessoais no log.
            logger.error('Falha no envio da recuperação de senha (%s).', type(exc).__name__)
            challenge.expires_at = now
            challenge.code_hash = make_password(None)
            challenge.save(update_fields=['expires_at', 'code_hash'])
            return None
        return str(challenge.pk)


def locked_challenge(identifier):
    """Chamado dentro de atomic; mesma ordem de locks na emissão e verificação."""
    try:
        identifier = UUID(str(identifier))
    except (ValueError, TypeError, AttributeError):
        return None
    user_id = PatientPasswordResetCode.objects.filter(pk=identifier).values_list('user_id', flat=True).first()
    if user_id is None:
        return None
    user = User.objects.select_for_update().filter(pk=user_id).first()
    challenge = PatientPasswordResetCode.objects.select_for_update().filter(pk=identifier, user_id=user_id).first()
    if challenge is None or user is None:
        return None
    challenge.user = user
    return challenge


def usable(challenge):
    return bool(
        challenge and eligible(challenge.user) and not challenge.used_at
        and challenge.expires_at > timezone.now()
        and challenge.attempts < settings.PASSWORD_RESET_MAX_ATTEMPTS
        and default_token_generator.check_token(challenge.user, challenge.state_token)
    )
