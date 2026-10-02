from django.urls import path

from . import views


app_name = "accounts"


urlpatterns = [

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