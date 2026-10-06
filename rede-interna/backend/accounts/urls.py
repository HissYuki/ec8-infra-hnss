from django.urls import path

from . import views
from . import mfa_views, password_views


app_name = "accounts"


urlpatterns = [
    path('mfa/configurar/', mfa_views.setup, name='mfa_setup'),
    path('mfa/qr/', mfa_views.qr, name='mfa_qr'),
    path('mfa/verificar/', mfa_views.verify, name='mfa_verify'),
    path('mfa/recuperar/', mfa_views.recover, name='mfa_recover'),
    path('mfa/concluir/', mfa_views.finish, name='mfa_finish'),
    path('paciente/senha/', password_views.PatientPasswordResetView.as_view(), name='password_reset'),
    path('paciente/senha/enviada/', password_views.PatientPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('paciente/senha/redefinir/', password_views.PatientPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('paciente/senha/concluida/', password_views.PatientPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    path(
        "paciente/login/",
        views.login_paciente,
        name="login_paciente"
    ),

    path(
        "paciente/registrar/",
        views.registrar_paciente,
        name="registrar_paciente"
    ),

    path(
        "medico/login/",
        views.login_medico,
        name="login_medico"
    ),

    path(
        "logout/",
        views.logout_usuario,
        name="logout"
    ),
]
