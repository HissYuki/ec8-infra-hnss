from django.contrib import admin

from .models import Coordenador


@admin.register(Coordenador)
class CoordenadorAdmin(admin.ModelAdmin):

    list_display = (
        "usuario",
        "matricula",
        "setor",
    )

    search_fields = (
        "usuario__first_name",
        "usuario__last_name",
        "usuario__username",
        "matricula",
    )

    list_filter = (
        "setor",
    )