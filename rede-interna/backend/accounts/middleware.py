from django.contrib.auth.views import redirect_to_login
from django.urls import reverse

from .authentication import expire_login, mfa_route, pending_expired, verified


class MFARequiredMiddleware:
    """Sessões com apenas senha não podem executar nenhuma view protegida."""

    public_views = {
        'inicio', 'accounts:login_paciente', 'accounts:login_medico',
        'accounts:registrar_paciente', 'accounts:logout', 'admin:login', 'admin:logout',
        'accounts:password_reset', 'accounts:password_reset_done',
        'accounts:password_reset_confirm', 'accounts:password_reset_complete',
    }
    mfa_views = {
        'accounts:mfa_setup', 'accounts:mfa_qr', 'accounts:mfa_verify',
        'accounts:mfa_recover', 'accounts:mfa_finish',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        name = request.resolver_match.view_name
        if name in self.public_views:
            return None
        if not request.user.is_authenticated:
            namespace = request.resolver_match.namespace
            if namespace == 'admin':
                route = 'admin:login'
            elif namespace in ('medicos', 'coordenador'):
                route = 'accounts:login_medico'
            else:
                route = 'accounts:login_paciente'
            return redirect_to_login(request.get_full_path(), reverse(route))
        needs_mfa = not verified(request.user) or request.session.get('mfa_reenroll')
        if needs_mfa:
            if pending_expired(request):
                return expire_login(request)
            if name not in self.mfa_views:
                from django.shortcuts import redirect
                return redirect(mfa_route(request))
        return None
