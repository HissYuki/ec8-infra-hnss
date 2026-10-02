from datetime import time, datetime, timedelta

from django import forms


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

# O último atendimento pode começar às 19:30
# e terminar às 20:00.
HORARIOS_INICIO = gerar_horarios(
    time(6, 0),
    time(19, 30)
)


HORARIOS_FIM = gerar_horarios(
    time(6, 30),
    time(20, 0)
)


# =========================================================
# DISPONIBILIDADE DE UM ÚNICO DIA
# =========================================================

class DisponibilidadeForm(forms.Form):

    data = forms.DateField(
        label="Data",
        widget=forms.DateInput(
            attrs={
                "type": "date"
            }
        )
    )


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


    def clean(self):

        dados = super().clean()

        hora_inicio = dados.get(
            "hora_inicio"
        )

        hora_fim = dados.get(
            "hora_fim"
        )


        if hora_inicio and hora_fim:

            # =============================================
            # HORÁRIO FINAL PRECISA SER POSTERIOR
            # =============================================

            if hora_inicio >= hora_fim:

                raise forms.ValidationError(
                    "O horário final deve ser posterior ao horário inicial."
                )


            # =============================================
            # PROTEÇÕES ADICIONAIS
            # =============================================

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


# =========================================================
# DISPONIBILIDADE SEMANAL / MENSAL
# =========================================================

class DisponibilidadeSemanalForm(forms.Form):

    DIAS_SEMANA = [
        ("0", "Segunda-feira"),
        ("1", "Terça-feira"),
        ("2", "Quarta-feira"),
        ("3", "Quinta-feira"),
        ("4", "Sexta-feira"),
        ("5", "Sábado"),
        ("6", "Domingo"),
    ]


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
        # PERÍODO
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