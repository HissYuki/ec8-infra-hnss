from django.conf import settings
from django.db import models


class Coordenador(models.Model):

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    matricula = models.CharField(
        max_length=30,
        unique=True
    )

    setor = models.CharField(
        max_length=100,
        default="Exames"
    )

    def __str__(self):

        return (
            f"{self.usuario.get_full_name()} "
            f"- {self.matricula}"
        )