from django.contrib import admin

from .models import (
    Consulta,
    HorarioDisponivel,
    Exame,
    HorarioExameDisponivel,
    AgendamentoExame,
)


@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    # A edição clínica fica na view restrita ao médico responsável.
    readonly_fields = ('observacoes',)

    list_display = (
        "paciente",
        "medico",
        "data_hora",
    )

    list_filter = (
        "medico",
        "data_hora",
    )


@admin.register(HorarioDisponivel)
class HorarioDisponivelAdmin(admin.ModelAdmin):

    list_display = (
        "medico",
        "data_hora",
        "ativo",
    )

    list_filter = (
        "medico",
        "ativo",
    )


@admin.register(Exame)
class ExameAdmin(admin.ModelAdmin):

    list_display = (
        "nome",
        "ativo",
    )

    list_filter = (
        "ativo",
    )

    search_fields = (
        "nome",
    )


@admin.register(HorarioExameDisponivel)
class HorarioExameDisponivelAdmin(admin.ModelAdmin):

    list_display = (
        "exame",
        "data_hora",
        "ativo",
    )

    list_filter = (
        "exame",
        "ativo",
    )


@admin.register(AgendamentoExame)
class AgendamentoExameAdmin(admin.ModelAdmin):

    list_display = (
        "paciente",
        "exame",
        "data_hora",
    )

    list_filter = (
        "exame",
        "data_hora",
    )
