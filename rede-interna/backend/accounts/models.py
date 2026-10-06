from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
import uuid


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


class PatientPasswordResetCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=128)
    state_token = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    last_sent_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
