from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class TipoUsuario(models.TextChoices):

        PACIENTE = "PACIENTE", "Paciente"

        MEDICO = "MEDICO", "Médico"

        COORDENADOR = "COORDENADOR", "Coordenador"


    tipo = models.CharField(
        max_length=20,
        choices=TipoUsuario.choices,
        blank=True,
        null=True
    )