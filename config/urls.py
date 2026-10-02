from django.contrib import admin
from django.urls import path, include

from accounts import views as accounts_views


urlpatterns = [

    # =====================================================
    # ADMIN
    # =====================================================

    path(
        "admin/",
        admin.site.urls
    ),


    # =====================================================
    # PÁGINA INICIAL PÚBLICA
    # =====================================================

    path(
        "",
        accounts_views.inicio,
        name="inicio"
    ),


    # =====================================================
    # LOGIN / CADASTRO / LOGOUT
    # =====================================================

    path(
        "conta/",
        include("accounts.urls")
    ),


    # =====================================================
    # ÁREAS INTERNAS
    # =====================================================

    path(
        "paciente/",
        include("pacientes.urls")
    ),

    path(
        "medico/",
        include("medicos.urls")
    ),

    path(
        "coordenador/",
        include("coordenador.urls")
    ),

]