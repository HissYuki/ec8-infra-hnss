from django.urls import path

from . import views


app_name = "pacientes"


urlpatterns = [

    # =====================================================
    # ÁREA DO PACIENTE
    # =====================================================

    path(
        "",
        views.dashboard,
        name="dashboard"
    ),

    path(
        "dados/",
        views.meus_dados,
        name="meus_dados"
    ),


    # =====================================================
    # CONSULTAS
    # =====================================================

    path(
        "consultas/",
        views.pagina_consultas,
        name="consultas"
    ),

    path(
        "horarios/<int:medico_id>/",
        views.horarios_disponiveis,
        name="horarios_disponiveis"
    ),

    path(
        "agendar/<int:horario_id>/",
        views.agendar_consulta,
        name="agendar_consulta"
    ),

    path(
        "consulta/<int:consulta_id>/cancelar/",
        views.cancelar_consulta,
        name="cancelar_consulta"
    ),


    # =====================================================
    # EXAMES
    # =====================================================

    path(
        "exames/",
        views.pagina_exames,
        name="exames"
    ),

    path(
        "exames/<int:exame_id>/horarios/",
        views.horarios_exame_disponiveis,
        name="horarios_exame_disponiveis"
    ),

    path(
        "exames/agendar/<int:horario_id>/",
        views.agendar_exame,
        name="agendar_exame"
    ),

    path(
        "exames/<int:agendamento_id>/cancelar/",
        views.cancelar_exame,
        name="cancelar_exame"
    ),

]