from io import BytesIO

import django_otp
import segno
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from .authentication import finish_mfa, verified
from .forms import RecoveryCodeForm, TOTPForm
from .security_audit import audit


def enrollment_device(request):
    # Serializa criação/ativação por usuário, inclusive entre sessões diferentes.
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    existing = TOTPDevice.objects.filter(user=request.user, confirmed=True).exists()
    if existing and not (request.session.get('mfa_reenroll') and verified(request.user)):
        return None
    device, _ = TOTPDevice.objects.get_or_create(
        user=request.user, name='hospital', confirmed=False,
    )
    return device


def recovery_codes(user):
    device, _ = StaticDevice.objects.get_or_create(user=user, name='recovery', confirmed=True)
    device.token_set.all().delete()
    codes = [StaticToken.random_token() for _ in range(10)]
    StaticToken.objects.bulk_create([StaticToken(device=device, token=code) for code in codes])
    return [f'{code[:4].upper()}-{code[4:].upper()}' for code in codes]


@login_required
@never_cache
@sensitive_post_parameters('token')
def setup(request):
    if verified(request.user) and not request.session.get('mfa_reenroll'):
        return finish_mfa(request)
    form = TOTPForm(request.POST if request.method == 'POST' else None)
    with transaction.atomic():
        device = enrollment_device(request)
        if device is None:
            return redirect('accounts:mfa_verify')
        if request.method == 'POST' and form.is_valid():
            device = django_otp.verify_token(request.user, device.persistent_id, form.cleaned_data['token'])
            if device is not None:
                device.confirmed = True
                device.save(update_fields=['confirmed'])
                TOTPDevice.objects.filter(user=request.user).exclude(pk=device.pk).delete()
                codes = recovery_codes(request.user)
                django_otp.login(request, device)
                request.session.pop('mfa_reenroll', None)
                audit('mfa_enrolled', request.user)
                return render(request, 'accounts/mfa_codes.html', {'codes': codes})
            audit('mfa_failed', request.user)
            form.add_error('token', 'Código inválido ou temporariamente bloqueado. Tente novamente.')
    return render(request, 'accounts/mfa_setup.html', {'form': form})


@login_required
@never_cache
def qr(request):
    if verified(request.user) and not request.session.get('mfa_reenroll'):
        return HttpResponse(status=404)
    with transaction.atomic():
        device = enrollment_device(request)
        if device is None:
            return HttpResponse(status=404)
        output = BytesIO()
        segno.make(device.config_url).save(output, kind='svg', scale=5)
    return HttpResponse(output.getvalue(), content_type='image/svg+xml')


@login_required
@never_cache
@sensitive_post_parameters('token')
def verify(request):
    if request.session.get('mfa_reenroll'):
        return redirect('accounts:mfa_setup')
    if verified(request.user):
        return finish_mfa(request)
    device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    if device is None:
        return redirect('accounts:mfa_setup')
    form = TOTPForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        device = django_otp.verify_token(request.user, device.persistent_id, form.cleaned_data['token'])
        if device is not None:
            django_otp.login(request, device)
            audit('mfa_verified', request.user)
            return finish_mfa(request)
        audit('mfa_failed', request.user)
        form.add_error('token', 'Código inválido, já utilizado ou temporariamente bloqueado.')
    return render(request, 'accounts/mfa_verify.html', {'form': form})


@login_required
@never_cache
@sensitive_post_parameters('token')
def recover(request):
    if request.session.get('mfa_reenroll'):
        return redirect('accounts:mfa_setup')
    if verified(request.user):
        return finish_mfa(request)
    form = RecoveryCodeForm(request.POST if request.method == 'POST' else None)
    device = StaticDevice.objects.filter(user=request.user, name='recovery', confirmed=True).first()
    if request.method == 'POST' and form.is_valid():
        accepted = device and django_otp.verify_token(request.user, device.persistent_id, form.cleaned_data['token'])
        if accepted:
            django_otp.login(request, accepted)
            request.session['mfa_reenroll'] = True
            audit('mfa_recovery_used', request.user)
            return redirect('accounts:mfa_setup')
        audit('mfa_failed', request.user)
        form.add_error('token', 'Código inválido, já utilizado ou temporariamente bloqueado.')
    return render(request, 'accounts/mfa_recover.html', {'form': form})


@login_required
@never_cache
def finish(request):
    if not verified(request.user) or request.session.get('mfa_reenroll'):
        return redirect('accounts:mfa_setup' if request.session.get('mfa_reenroll') else 'accounts:mfa_verify')
    return finish_mfa(request)
