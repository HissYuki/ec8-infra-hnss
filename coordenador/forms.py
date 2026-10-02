from datetime import time, datetime, timedelta

from django import forms

from consultas.models import Exame
from medicos.models import Medico


# =========================================================
# HORÁRIO DE FUNCIONAMENTO DO HOSPITAL
# =========================================================

HORARIO_ABERTURA = time(6, 0)
HORARIO_FECHAMENTO = time(20, 0)


# =========================================================
# GERAR OPÇÕES DE HORÁRIO
# =========================================================

def gerar_horarios(hora_inicial, hora_final):

    horarios = []

    atual = datetime.combine(
        datetime.today(),
        hora_inicial
    )

    fim = datetime.combine(
        datetime.today(),
        hora_final
    )


    while atual <= fim:

        valor = atual.strftime("%H:%M")

        horarios.append(
            (
                valor,
                valor
            )
        )

        atual += timedelta(
            minutes=30
        )


    return horarios


# =========================================================
# HORÁRIOS PERMITIDOS
# =========================================================

# Horário inicial:
# 06:00 até 19:30
HORARIOS_INICIO = gerar_horarios(
    time(6, 0),
    time(19, 30)
)


# Horário final:
# 06:30 até 20:00
HORARIOS_FIM = gerar_horarios(
    time(6, 30),
    time(20, 0)
)


# =========================================================
# CAMPO PERSONALIZADO PARA MÉDICOS
# =========================================================

class MedicoChoiceField(forms.ModelChoiceField):

    def label_from_instance(self, medico):

        nome = (
            medico.usuario.get_full_name()
            or medico.usuario.username
        )

        return (
            f"{nome} - "
            f"{medico.especialidade} "
            f"(CRM: {medico.crm})"
        )


# =========================================================
# DISPONIBILIDADE DE EXAME - UM DIA
# =========================================================

class DisponibilidadeExameForm(forms.Form):

    exame = forms.ModelChoiceField(
        label="Exame",
        queryset=Exame.objects.filter(
            ativo=True
        ).order_by(
            "nome"
        ),
        empty_label="Selecione um exame"
    )


    medico_responsavel = MedicoChoiceField(
        label="Médico responsável",
        queryset=Medico.objects.select_related(
            "usuario"
        ).all().order_by(
            "usuario__first_name",
            "usuario__last_name"
        ),
        empty_label="Selecione um médico"
    )


    data = forms.DateField(
        label="Data",
        widget=forms.DateInput(
            attrs={
                "type": "date"
            }
        )
    )


    # =====================================================
    # HORÁRIO INICIAL
    #
    # TypedChoiceField:
    # - exibe um <select>
    # - recebe "06:00", "06:30" etc.
    # - converte automaticamente para datetime.time
    # =====================================================

    hora_inicio = forms.TypedChoiceField(
        label="Horário inicial",
        choices=[
            (
                "",
                "Selecione um horário"
            ),
            *HORARIOS_INICIO,
        ],
        coerce=time.fromisoformat,
        empty_value=None
    )


    # =====================================================
    # HORÁRIO FINAL
    # =====================================================

    hora_fim = forms.TypedChoiceField(
        label="Horário final",
        choices=[
            (
                "",
                "Selecione um horário"
            ),
            *HORARIOS_FIM,
        ],
        coerce=time.fromisoformat,
        empty_value=None
    )


    # =====================================================
    # VALIDAÇÃO
    # =====================================================

    def clean(self):

        dados = super().clean()

        inicio = dados.get(
            "hora_inicio"
        )

        fim = dados.get(
            "hora_fim"
        )


        if inicio and fim:

            # =============================================
            # FINAL PRECISA SER POSTERIOR
            # =============================================

            if inicio >= fim:

                raise forms.ValidationError(
                    "O horário final deve ser posterior ao horário inicial."
                )


            # =============================================
            # SEGURANÇA EXTRA
            # =============================================

            if inicio < HORARIO_ABERTURA:

                raise forms.ValidationError(
                    "O hospital inicia os atendimentos às 06:00."
                )


            if inicio >= HORARIO_FECHAMENTO:

                raise forms.ValidationError(
                    "O último horário de início permitido é 19:30."
                )


            if fim > HORARIO_FECHAMENTO:

                raise forms.ValidationError(
                    "O hospital encerra os atendimentos às 20:00."
                )


        return dados


# =========================================================
# DISPONIBILIDADE DE EXAME - SEMANAL / PERÍODO
# =========================================================

class DisponibilidadeExameSemanalForm(forms.Form):

    DIAS_SEMANA = [
        ("0", "Segunda-feira"),
        ("1", "Terça-feira"),
        ("2", "Quarta-feira"),
        ("3", "Quinta-feira"),
        ("4", "Sexta-feira"),
        ("5", "Sábado"),
        ("6", "Domingo"),
    ]


    exame = forms.ModelChoiceField(
        label="Exame",
        queryset=Exame.objects.filter(
            ativo=True
        ).order_by(
            "nome"
        ),
        empty_label="Selecione um exame"
    )


    medico_responsavel = MedicoChoiceField(
        label="Médico responsável",
        queryset=Medico.objects.select_related(
            "usuario"
        ).all().order_by(
            "usuario__first_name",
            "usuario__last_name"
        ),
        empty_label="Selecione um médico"
    )


    data_inicio = forms.DateField(
        label="Data inicial",
        widget=forms.DateInput(
            attrs={
                "type": "date"
            }
        )
    )


    data_fim = forms.DateField(
        label="Data final",
        widget=forms.DateInput(
            attrs={
                "type": "date"
            }
        )
    )


    dias_semana = forms.MultipleChoiceField(
        label="Dias da semana",
        choices=DIAS_SEMANA,
        widget=forms.CheckboxSelectMultiple
    )


    # =====================================================
    # HORÁRIO INICIAL
    # =====================================================

    hora_inicio = forms.TypedChoiceField(
        label="Horário inicial",
        choices=[
            (
                "",
                "Selecione um horário"
            ),
            *HORARIOS_INICIO,
        ],
        coerce=time.fromisoformat,
        empty_value=None
    )


    # =====================================================
    # HORÁRIO FINAL
    # =====================================================

    hora_fim = forms.TypedChoiceField(
        label="Horário final",
        choices=[
            (
                "",
                "Selecione um horário"
            ),
            *HORARIOS_FIM,
        ],
        coerce=time.fromisoformat,
        empty_value=None
    )


    # =====================================================
    # VALIDAÇÃO
    # =====================================================

    def clean(self):

        dados = super().clean()

        data_inicio = dados.get(
            "data_inicio"
        )

        data_fim = dados.get(
            "data_fim"
        )

        hora_inicio = dados.get(
            "hora_inicio"
        )

        hora_fim = dados.get(
            "hora_fim"
        )


        # =============================================
        # DATAS
        # =============================================

        if (
            data_inicio
            and data_fim
            and data_inicio > data_fim
        ):

            raise forms.ValidationError(
                "A data final deve ser posterior ou igual à data inicial."
            )


        # =============================================
        # HORÁRIOS
        # =============================================

        if hora_inicio and hora_fim:

            if hora_inicio >= hora_fim:

                raise forms.ValidationError(
                    "O horário final deve ser posterior ao horário inicial."
                )


            if hora_inicio < HORARIO_ABERTURA:

                raise forms.ValidationError(
                    "O hospital inicia os atendimentos às 06:00."
                )


            if hora_inicio >= HORARIO_FECHAMENTO:

                raise forms.ValidationError(
                    "O último horário de início permitido é 19:30."
                )


            if hora_fim > HORARIO_FECHAMENTO:

                raise forms.ValidationError(
                    "O hospital encerra os atendimentos às 20:00."
                )


        return dados