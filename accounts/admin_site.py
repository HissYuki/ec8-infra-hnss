from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig
from django.urls import path, reverse
from django.views.decorators.csrf import csrf_protect


class HospitalAdminConfig(AdminConfig):
    default_site = 'accounts.admin_site.HospitalAdminSite'


class HospitalAdminSite(AdminSite):
    def has_permission(self, request):
        from .authentication import verified
        return super().has_permission(request) and verified(request.user) and not request.session.get('mfa_reenroll')

    def login(self, request, extra_context=None):
        from .authentication import begin_mfa, verified
        response = super().login(request, extra_context)
        if response.status_code == 302 and request.user.is_authenticated and not verified(request.user):
            destination = request.POST.get('next') or reverse('admin:index')
            return begin_mfa(request, destination)
        return response

    def get_urls(self):
        from .views import logout_usuario
        # O logout deve funcionar também na sessão que ainda está aguardando MFA.
        return [path('logout/', csrf_protect(logout_usuario), name='logout')] + [
            url for url in super().get_urls() if getattr(url, 'name', None) != 'logout'
        ]
