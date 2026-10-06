from django.conf import settings
from django.db import models


class Medico(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    crm = models.CharField(max_length=20, unique=True)
    especialidade = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.usuario.get_full_name()} - {self.crm}"