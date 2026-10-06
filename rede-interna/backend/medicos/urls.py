from django.urls import path

from . import views


app_name = "medicos"


urlpatterns = [
    path('consulta/<int:consulta_id>/', views.detalhe_consulta, name='detalhe_consulta'),

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
        "disponibilidade/remover/<int:horario_id>/",
        views.remover_horario,
        name="remover_horario"
    ),

    path(
        "paciente/<int:paciente_id>/",
        views.dados_paciente,
        name="dados_paciente"
    ),

    path(
        "consultas-calendario/",
        views.consultas_calendario,
        name="consultas_calendario"
    ),

    path(
    "disponibilidade/remover-todos/",
    views.remover_todos_horarios,
    name="remover_todos_horarios"
    ),
]
