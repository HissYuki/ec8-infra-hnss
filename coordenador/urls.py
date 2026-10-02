from django.urls import path

from . import views


app_name = "coordenador"


urlpatterns = [

    path(
        "",
        views.dashboard,
        name="dashboard"
    ),

    path(
        "disponibilidade/",
        views.disponibilidade,
        name="disponibilidade"
    ),

    path(
        "exames-calendario/",
        views.exames_calendario,
        name="exames_calendario"
    ),

    path(
        "disponibilidade/remover/<int:horario_id>/",
        views.remover_horario,
        name="remover_horario"
    ),

]