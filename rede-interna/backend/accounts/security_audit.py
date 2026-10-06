"""Security metadata only: never log credentials, patient data or request bodies."""
import json
import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

logger = logging.getLogger('hospital.security')
ALLOWED_EVENTS = {
    'password_login_accepted', 'password_login_failed', 'logout',
    'mfa_enrolled', 'mfa_verified', 'mfa_failed', 'mfa_recovery_used',
}

def audit(event, user=None):
    if event not in ALLOWED_EVENTS:
        raise ValueError('Unsupported security event')
    role = 'unknown'
    if user is not None:
        if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
            role = 'ADMINISTRADOR'
        elif getattr(user, 'tipo', None) in ('PACIENTE', 'MEDICO', 'COORDENADOR'):
            role = user.tipo
    logger.info(json.dumps({'source': 'hospital.security', 'event': event, 'role': role}))

@receiver(user_logged_in, dispatch_uid='hospital.security.login')
def login_event(sender, user, **kwargs):
    # Password accepted is distinct from completing MFA.
    audit('password_login_accepted', user)

@receiver(user_logged_out, dispatch_uid='hospital.security.logout')
def logout_event(sender, user, **kwargs):
    audit('logout', user)

@receiver(user_login_failed, dispatch_uid='hospital.security.failed')
def failed_event(sender, **kwargs):
    audit('password_login_failed')
