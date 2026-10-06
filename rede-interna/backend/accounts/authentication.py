"""Encaminhamento e estado de autenticação compartilhados, incluindo o Admin."""
import time

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice


def is_patient(user):
    return user.tipo == 'PACIENTE' and not user.is_staff and not user.is_superuser


def login_route(user):
    if user.is_staff or user.is_superuser:
        return 'admin:login'
    if user.tipo in ('MEDICO', 'COORDENADOR'):
        return 'accounts:login_medico'
    return 'accounts:login_paciente'


def dashboard_route(user):
    if user.is_staff or user.is_superuser:
        return 'admin:index'
    return {
        'PACIENTE': 'pacientes:dashboard',
        'MEDICO': 'medicos:dashboard',
        'COORDENADOR': 'coordenador:dashboard',
    }.get(user.tipo, 'inicio')


def verified(user):
    return user.is_authenticated and getattr(user, 'is_verified', lambda: False)()


def safe_destination(request, value):
    if value and url_has_allowed_host_and_scheme(
        value, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return value
    return reverse(dashboard_route(request.user))


def begin_mfa(request, destination=None):
    request.session.pop(DEVICE_ID_SESSION_KEY, None)
    request.session['mfa_started_at'] = time.time()
    request.session['mfa_next'] = safe_destination(
        request, destination or request.POST.get('next') or request.GET.get('next')
    )
    request.session.pop('mfa_reenroll', None)
    return redirect(mfa_route(request))


def mfa_route(request):
    if request.session.get('mfa_reenroll'):
        return 'accounts:mfa_setup'
    if TOTPDevice.objects.filter(user=request.user, confirmed=True).exists():
        return 'accounts:mfa_verify'
    return 'accounts:mfa_setup'


def pending_expired(request):
    started = request.session.get('mfa_started_at', 0)
    return not isinstance(started, (int, float)) or time.time() - started > settings.MFA_LOGIN_TIMEOUT


def expire_login(request):
    route = login_route(request.user)
    logout(request)
    return redirect(route)


def finish_mfa(request):
    destination = safe_destination(request, request.session.pop('mfa_next', None))
    request.session.pop('mfa_started_at', None)
    request.session.pop('mfa_reenroll', None)
    return redirect(destination)
