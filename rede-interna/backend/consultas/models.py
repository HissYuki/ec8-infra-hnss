from django.db import models

from medicos.models import Medico
from pacientes.models import Paciente
from coordenador.models import Coordenador


# =========================================================
# CONSULTAS
# =========================================================

class HorarioDisponivel(models.Model):

    medico = models.ForeignKey(
        Medico,
        on_delete=models.CASCADE,
        related_name="horarios_disponiveis"
    )

    data_hora = models.DateTimeField()

    ativo = models.BooleanField(
        default=True
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=["medico", "data_hora"],
                name="horario_unico_medico_data_hora"
            )
        ]

        ordering = [
            "data_hora"
        ]

    def __str__(self):

        return (
            f"{self.medico} - "
            f"{self.data_hora.strftime('%d/%m/%Y %H:%M')}"
        )


class Consulta(models.Model):

    medico = models.ForeignKey(
        Medico,
        on_delete=models.PROTECT,
        related_name="consultas"
    )

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.PROTECT,
        related_name="consultas"
    )

    data_hora = models.DateTimeField()

    observacoes = models.TextField(
        blank=True
    )

    class Meta:

        constraints = [

            models.UniqueConstraint(
                fields=["medico", "data_hora"],
                name="consulta_unica_medico_horario"
            ),

            models.UniqueConstraint(
                fields=["paciente", "data_hora"],
                name="consulta_unica_paciente_horario"
            ),

        ]

        ordering = [
            "data_hora"
        ]

    def __str__(self):

        return (
            f"{self.paciente} - "
            f"{self.medico} - "
            f"{self.data_hora}"
        )


# =========================================================
# EXAMES
# =========================================================

class Exame(models.Model):

    nome = models.CharField(
        max_length=120,
        unique=True
    )

    descricao = models.TextField(
        blank=True
    )

    especialidade_responsavel = models.CharField(
        max_length=100,
        blank=True
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:

        ordering = [
            "nome"
        ]

    def __str__(self):

        return self.nome


# =========================================================
# HORÁRIOS DOS EXAMES
# =========================================================

class HorarioExameDisponivel(models.Model):

    exame = models.ForeignKey(
        Exame,
        on_delete=models.CASCADE,
        related_name="horarios_disponiveis"
    )

    coordenador = models.ForeignKey(
        Coordenador,
        on_delete=models.PROTECT,
        related_name="horarios_criados",
        null=True,
        blank=True
    )

    medico_responsavel = models.ForeignKey(
        Medico,
        on_delete=models.PROTECT,
        related_name="horarios_exames",
        null=True,
        blank=True
    )

    data_hora = models.DateTimeField()

    ativo = models.BooleanField(
        default=True
    )


    class Meta:

        constraints = [

            # Um médico não pode estar responsável por
            # dois exames no mesmo horário.
            models.UniqueConstraint(
                fields=[
                    "medico_responsavel",
                    "data_hora"
                ],
                name="horario_exame_unico_medico"
            ),

        ]

        ordering = [
            "data_hora"
        ]


    def __str__(self):

        return (
            f"{self.exame.nome} - "
            f"{self.medico_responsavel} - "
            f"{self.data_hora.strftime('%d/%m/%Y %H:%M')}"
        )


# =========================================================
# AGENDAMENTOS DOS EXAMES
# =========================================================

class AgendamentoExame(models.Model):

    exame = models.ForeignKey(
        Exame,
        on_delete=models.PROTECT,
        related_name="agendamentos"
    )

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.PROTECT,
        related_name="exames_agendados"
    )

    medico_responsavel = models.ForeignKey(
        Medico,
        on_delete=models.PROTECT,
        related_name="exames_agendados",
        null=True,
        blank=True
    )

    coordenador = models.ForeignKey(
        Coordenador,
        on_delete=models.PROTECT,
        related_name="agendamentos_exames",
        null=True,
        blank=True
    )

    data_hora = models.DateTimeField()


    class Meta:

        constraints = [

            # Médico não pode ter dois exames no mesmo horário.
            models.UniqueConstraint(
                fields=[
                    "medico_responsavel",
                    "data_hora"
                ],
                name="agendamento_exame_unico_medico"
            ),

            # Paciente não pode ter dois exames no mesmo horário.
            models.UniqueConstraint(
                fields=[
                    "paciente",
                    "data_hora"
                ],
                name="agendamento_exame_paciente_horario"
            ),

        ]

        ordering = [
            "data_hora"
        ]


    def __str__(self):

        return (
            f"{self.paciente} - "
            f"{self.exame.nome} - "
            f"{self.medico_responsavel} - "
            f"{self.data_hora}"
        )