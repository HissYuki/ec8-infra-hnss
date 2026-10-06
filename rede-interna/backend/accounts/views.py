from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from .authentication import begin_mfa, dashboard_route, login_route, mfa_route, verified
from .forms import CadastroPacienteForm, PatientAuthenticationForm, ProfessionalAuthenticationForm


def authenticated_redirect(request):
    if verified(request.user) and not request.session.get('mfa_reenroll'):
        return redirect(dashboard_route(request.user))
    return redirect(mfa_route(request))


def role_login(request, form_class, template):
    if request.user.is_authenticated:
        return authenticated_redirect(request)
    form = form_class(request, data=request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return begin_mfa(request)
    return render(request, template, {'form': form, 'next': request.GET.get('next', '')})


@sensitive_post_parameters('password')
def login_paciente(request):
    return role_login(request, PatientAuthenticationForm, 'registration/login_paciente.html')


@sensitive_post_parameters('password')
def login_medico(request):
    return role_login(request, ProfessionalAuthenticationForm, 'registration/login_medico.html')


@sensitive_post_parameters('password1', 'password2')
def registrar_paciente(request):
    if request.user.is_authenticated:
        return authenticated_redirect(request)
    form = CadastroPacienteForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return begin_mfa(request)
    return render(request, 'registration/registrar_paciente.html', {'form': form})


@require_POST
def logout_usuario(request):
    # Preserve o destino antes de logout() substituir request.user por AnonymousUser.
    route = login_route(request.user) if request.user.is_authenticated else 'accounts:login_paciente'
    logout(request)
    return redirect(route)


def inicio(request):
    return render(request, 'inicio.html')
