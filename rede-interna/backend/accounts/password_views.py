from uuid import uuid4

from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import FormView, TemplateView
from django.urls import reverse_lazy

from .forms import PasswordResetCodeForm, PatientPasswordResetForm
from .password_recovery import issue_code, locked_challenge, usable


@method_decorator(never_cache, name='dispatch')
class PatientPasswordResetView(FormView):
    form_class = PatientPasswordResetForm
    template_name = 'accounts/password_reset_form.html'
    success_url = reverse_lazy('accounts:password_reset_done')

    def form_valid(self, form):
        self.request.session.pop('reset_verified_id', None)
        identifier = issue_code(form.cleaned_data['email'])
        self.request.session['reset_code_id'] = identifier or str(uuid4())
        return super().form_valid(form)


@method_decorator(never_cache, name='dispatch')
@method_decorator(sensitive_post_parameters('code'), name='dispatch')
class PatientPasswordResetDoneView(FormView):
    form_class = PasswordResetCodeForm
    template_name = 'accounts/password_reset_done.html'
    success_url = reverse_lazy('accounts:password_reset_confirm')

    def form_valid(self, form):
        with transaction.atomic():
            challenge = locked_challenge(self.request.session.get('reset_code_id'))
            if usable(challenge) and not challenge.verified_at:
                accepted = check_password(form.cleaned_data['code'], challenge.code_hash)
                if accepted:
                    challenge.verified_at = timezone.now()
                    challenge.code_hash = make_password(None)
                    challenge.save(update_fields=['verified_at', 'code_hash'])
                    self.request.session['reset_verified_id'] = str(challenge.pk)
                    return super().form_valid(form)
                challenge.attempts += 1
                challenge.save(update_fields=['attempts'])
        form.add_error('code', 'Código inválido, expirado ou indisponível. Solicite outro código se necessário.')
        return self.form_invalid(form)


@method_decorator(never_cache, name='dispatch')
@method_decorator(sensitive_post_parameters('new_password1', 'new_password2'), name='dispatch')
class PatientPasswordResetConfirmView(View):
    def get(self, request):
        return self.handle_form(request)

    def post(self, request):
        return self.handle_form(request)

    def handle_form(self, request):
        # O código é necessário antes de acessar o formulário de nova senha.
        with transaction.atomic():
            challenge = locked_challenge(request.session.get('reset_code_id'))
            valid = (usable(challenge) and challenge.verified_at
                     and request.session.get('reset_verified_id') == str(challenge.pk))
            if not valid:
                return redirect('accounts:password_reset_done')
            form = SetPasswordForm(challenge.user, request.POST if request.method == 'POST' else None)
            if request.method == 'POST' and form.is_valid():
                form.save()
                challenge.used_at = timezone.now()
                challenge.save(update_fields=['used_at'])
                request.session.pop('reset_code_id', None)
                request.session.pop('reset_verified_id', None)
                return redirect('accounts:password_reset_complete')
        return render(request, 'accounts/password_reset_confirm.html', {'form': form})


class PatientPasswordResetCompleteView(TemplateView):
    template_name = 'accounts/password_reset_complete.html'
