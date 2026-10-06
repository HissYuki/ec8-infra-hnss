from datetime import time, date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST


# =========================================================
# HORÁRIO DE FUNCIONAMENTO DO HOSPITAL
# =========================================================

HORARIO_ABERTURA = time(6, 0)
HORARIO_FECHAMENTO = time(20, 0)


from consultas.models import (
    Consulta,
    HorarioExameDisponivel,
    AgendamentoExame,
)

from .models import Coordenador

from .forms import (
    DisponibilidadeExameForm,
    DisponibilidadeExameSemanalForm,
)


# =========================================================
# DASHBOARD DO COORDENADOR
# =========================================================

@login_required
def dashboard(request):

    if request.user.tipo != "COORDENADOR":

        return HttpResponseForbidden(
            "Você não possui permissão para acessar esta página."
        )

    get_object_or_404(
        Coordenador,
        usuario=request.user
    )

    return render(
        request,
        "coordenador/dashboard.html"
    )


# =========================================================
# CALENDÁRIO DO COORDENADOR
# =========================================================

@login_required
def exames_calendario(request):

    if request.user.tipo != "COORDENADOR":

        return JsonResponse(
            {
                "erro": "Acesso não autorizado."
            },
            status=403
        )


    coordenador = get_object_or_404(
        Coordenador,
        usuario=request.user
    )


    horarios = (
        HorarioExameDisponivel.objects
        .filter(
            coordenador=coordenador
        )
        .select_related(
            "exame",
            "medico_responsavel",
            "medico_responsavel__usuario"
        )
        .order_by(
            "data_hora"
        )
    )


    eventos = []


    for horario in horarios:

        agendamento = (
            AgendamentoExame.objects
            .filter(
                exame=horario.exame,
                medico_responsavel=horario.medico_responsavel,
                data_hora=horario.data_hora
            )
            .select_related(
                "paciente",
                "paciente__usuario"
            )
            .first()
        )


        medico_nome = (
            horario.medico_responsavel.usuario.get_full_name()
            or horario.medico_responsavel.usuario.username
        )


        # =================================================
        # EXAME JÁ AGENDADO
        # =================================================

        if agendamento:

            paciente_nome = (
                agendamento.paciente.usuario.get_full_name()
                or agendamento.paciente.usuario.username
            )

            titulo = (
                f"{horario.exame.nome} - "
                f"{medico_nome} - "
                f"{paciente_nome}"
            )

            classe_evento = (
                "evento-exame-agendado"
            )


        # =================================================
        # HORÁRIO AINDA DISPONÍVEL
        # =================================================

        else:

            titulo = (
                f"{horario.exame.nome} - "
                f"{medico_nome} - Disponível"
            )

            classe_evento = (
                "evento-exame-disponivel"
            )


        eventos.append(
            {
                "id": horario.id,
                "title": titulo,
                "start": horario.data_hora.isoformat(),
                "end": (
                    horario.data_hora
                    + timedelta(minutes=30)
                ).isoformat(),
                "classNames": [
                    classe_evento
                ],
            }
        )


    return JsonResponse(
        eventos,
        safe=False
    )


# =========================================================
# DISPONIBILIDADE DOS EXAMES
# =========================================================

@login_required
def disponibilidade(request):

    if request.user.tipo != "COORDENADOR":

        return HttpResponseForbidden(
            "Você não possui permissão para acessar esta página."
        )


    coordenador = get_object_or_404(
        Coordenador,
        usuario=request.user
    )


    # =====================================================
    # FORMULÁRIOS
    # =====================================================

    form_diario = DisponibilidadeExameForm()

    form_semanal = DisponibilidadeExameSemanalForm()


    aba_ativa = request.GET.get(
        "aba",
        "diaria"
    )


    # =====================================================
    # POST
    # =====================================================

    if request.method == "POST":

        tipo_formulario = request.POST.get(
            "tipo_formulario"
        )


        # =================================================
        # DISPONIBILIDADE DE UM DIA
        # =================================================

        if tipo_formulario == "diaria":

            aba_ativa = "diaria"


            form_diario = DisponibilidadeExameForm(
                request.POST
            )


            if form_diario.is_valid():

                exame = form_diario.cleaned_data[
                    "exame"
                ]

                medico = form_diario.cleaned_data[
                    "medico_responsavel"
                ]

                data = form_diario.cleaned_data[
                    "data"
                ]

                hora_inicio = form_diario.cleaned_data[
                    "hora_inicio"
                ]

                hora_fim = form_diario.cleaned_data[
                    "hora_fim"
                ]


                # =========================================
                # HORÁRIO DO HOSPITAL
                # =========================================

                if (
                    hora_inicio < HORARIO_ABERTURA
                    or hora_fim > HORARIO_FECHAMENTO
                ):

                    form_diario.add_error(
                        None,
                        (
                            "Os exames somente podem ser "
                            "disponibilizados entre "
                            "06:00 e 20:00."
                        )
                    )


                else:

                    inicio = timezone.make_aware(
                        datetime.combine(
                            data,
                            hora_inicio
                        )
                    )

                    fim = timezone.make_aware(
                        datetime.combine(
                            data,
                            hora_fim
                        )
                    )


                    momento = inicio


                    # =====================================
                    # CONTADOR
                    # =====================================

                    horarios_criados = 0


                    with transaction.atomic():

                        while momento < fim:


                            # =============================
                            # HORÁRIO DO HOSPITAL
                            # =============================

                            if not (
                                HORARIO_ABERTURA
                                <= momento.time()
                                < HORARIO_FECHAMENTO
                            ):

                                momento += timedelta(
                                    minutes=30
                                )

                                continue


                            # =============================
                            # NÃO CRIA NO PASSADO
                            # =============================

                            if momento <= timezone.now():

                                momento += timedelta(
                                    minutes=30
                                )

                                continue


                            # =============================
                            # MÉDICO POSSUI CONSULTA?
                            # =============================

                            possui_consulta = (
                                Consulta.objects
                                .filter(
                                    medico=medico,
                                    data_hora=momento
                                )
                                .exists()
                            )


                            # =============================
                            # MÉDICO POSSUI OUTRO EXAME?
                            # =============================

                            possui_exame = (
                                HorarioExameDisponivel.objects
                                .filter(
                                    medico_responsavel=medico,
                                    data_hora=momento
                                )
                                .exists()
                            )


                            # =============================
                            # CRIA O HORÁRIO
                            # =============================

                            if (
                                not possui_consulta
                                and not possui_exame
                            ):

                                HorarioExameDisponivel.objects.create(
                                    exame=exame,
                                    coordenador=coordenador,
                                    medico_responsavel=medico,
                                    data_hora=momento,
                                    ativo=True,
                                )


                                horarios_criados += 1


                            momento += timedelta(
                                minutes=30
                            )


                    # =====================================
                    # MENSAGEM DE RETORNO
                    # =====================================

                    if horarios_criados > 0:

                        messages.success(
                            request,
                            (
                                f"{horarios_criados} horário(s) "
                                "de exame disponibilizado(s) "
                                "com sucesso."
                            )
                        )

                    else:

                        messages.warning(
                            request,
                            (
                                "Nenhum novo horário de exame "
                                "foi disponibilizado. Verifique "
                                "se o médico já possui consulta "
                                "ou outro exame nesses horários."
                            )
                        )


                    return redirect(
                        "coordenador:disponibilidade"
                    )


        # =================================================
        # DISPONIBILIDADE SEMANAL / MENSAL
        # =================================================

        elif tipo_formulario == "semanal":

            aba_ativa = "semanal"


            form_semanal = (
                DisponibilidadeExameSemanalForm(
                    request.POST
                )
            )


            if form_semanal.is_valid():

                exame = form_semanal.cleaned_data[
                    "exame"
                ]

                medico = form_semanal.cleaned_data[
                    "medico_responsavel"
                ]

                data_inicio = form_semanal.cleaned_data[
                    "data_inicio"
                ]

                data_fim = form_semanal.cleaned_data[
                    "data_fim"
                ]

                dias_semana = {
                    int(dia)
                    for dia
                    in form_semanal.cleaned_data[
                        "dias_semana"
                    ]
                }

                hora_inicio = form_semanal.cleaned_data[
                    "hora_inicio"
                ]

                hora_fim = form_semanal.cleaned_data[
                    "hora_fim"
                ]


                # =========================================
                # HORÁRIO DO HOSPITAL
                # =========================================

                if (
                    hora_inicio < HORARIO_ABERTURA
                    or hora_fim > HORARIO_FECHAMENTO
                ):

                    form_semanal.add_error(
                        None,
                        (
                            "Os exames somente podem ser "
                            "disponibilizados entre "
                            "06:00 e 20:00."
                        )
                    )


                else:

                    data_atual = data_inicio


                    # =====================================
                    # CONTADOR
                    # =====================================

                    horarios_criados = 0


                    with transaction.atomic():

                        while data_atual <= data_fim:


                            if (
                                data_atual.weekday()
                                in dias_semana
                            ):


                                inicio = timezone.make_aware(
                                    datetime.combine(
                                        data_atual,
                                        hora_inicio
                                    )
                                )


                                fim = timezone.make_aware(
                                    datetime.combine(
                                        data_atual,
                                        hora_fim
                                    )
                                )


                                momento = inicio


                                while momento < fim:


                                    # =====================
                                    # HORÁRIO DO HOSPITAL
                                    # =====================

                                    if not (
                                        HORARIO_ABERTURA
                                        <= momento.time()
                                        < HORARIO_FECHAMENTO
                                    ):

                                        momento += timedelta(
                                            minutes=30
                                        )

                                        continue


                                    # =====================
                                    # NÃO CRIA NO PASSADO
                                    # =====================

                                    if momento <= timezone.now():

                                        momento += timedelta(
                                            minutes=30
                                        )

                                        continue


                                    # =====================
                                    # MÉDICO POSSUI CONSULTA?
                                    # =====================

                                    possui_consulta = (
                                        Consulta.objects
                                        .filter(
                                            medico=medico,
                                            data_hora=momento
                                        )
                                        .exists()
                                    )


                                    # =====================
                                    # MÉDICO POSSUI OUTRO EXAME?
                                    # =====================

                                    possui_exame = (
                                        HorarioExameDisponivel.objects
                                        .filter(
                                            medico_responsavel=medico,
                                            data_hora=momento
                                        )
                                        .exists()
                                    )


                                    # =====================
                                    # CRIA O HORÁRIO
                                    # =====================

                                    if (
                                        not possui_consulta
                                        and not possui_exame
                                    ):

                                        HorarioExameDisponivel.objects.create(
                                            exame=exame,
                                            coordenador=coordenador,
                                            medico_responsavel=medico,
                                            data_hora=momento,
                                            ativo=True,
                                        )


                                        horarios_criados += 1


                                    momento += timedelta(
                                        minutes=30
                                    )


                            data_atual += timedelta(
                                days=1
                            )


                    # =====================================
                    # MENSAGEM DE RETORNO
                    # =====================================

                    if horarios_criados > 0:

                        messages.success(
                            request,
                            (
                                f"{horarios_criados} horário(s) "
                                "de exame disponibilizado(s) "
                                "com sucesso."
                            )
                        )

                    else:

                        messages.warning(
                            request,
                            (
                                "Nenhum novo horário de exame "
                                "foi disponibilizado. Verifique "
                                "os conflitos na agenda do médico."
                            )
                        )


                    return redirect(
                        "coordenador:disponibilidade"
                    )


    # =====================================================
    # HORÁRIOS CADASTRADOS
    # =====================================================

    horarios_base = (
        HorarioExameDisponivel.objects
        .filter(
            coordenador=coordenador,
            data_hora__gte=timezone.now()
        )
        .select_related(
            "exame",
            "medico_responsavel",
            "medico_responsavel__usuario"
        )
        .order_by(
            "data_hora"
        )
    )


    # =====================================================
    # DATAS DISPONÍVEIS
    # =====================================================

    datas_disponiveis = list(
        horarios_base.dates(
            "data_hora",
            "day",
            order="ASC"
        )
    )


    # =====================================================
    # DATA SELECIONADA
    # =====================================================

    data_parametro = request.GET.get(
        "data"
    )


    data_selecionada = None


    if data_parametro:

        try:

            data_selecionada = date.fromisoformat(
                data_parametro
            )

        except ValueError:

            data_selecionada = None


    if (
        data_selecionada is None
        and datas_disponiveis
    ):

        data_selecionada = (
            datas_disponiveis[0]
        )


    # =====================================================
    # HORÁRIOS DA DATA SELECIONADA
    # =====================================================

    if data_selecionada:

        horarios = horarios_base.filter(
            data_hora__date=data_selecionada
        )

    else:

        horarios = horarios_base.none()


    contexto = {

        "form_diario":
            form_diario,

        "form_semanal":
            form_semanal,

        "horarios":
            horarios,

        "datas_disponiveis":
            datas_disponiveis,

        "data_selecionada":
            data_selecionada,

        "aba_ativa":
            aba_ativa,

    }


    return render(
        request,
        "coordenador/disponibilidade.html",
        contexto
    )


# =========================================================
# REMOVER HORÁRIO
# =========================================================

@login_required
@require_POST
def remover_horario(request, horario_id):

    if request.user.tipo != "COORDENADOR":

        return HttpResponseForbidden(
            "Acesso não autorizado."
        )


    coordenador = get_object_or_404(
        Coordenador,
        usuario=request.user
    )


    horario = get_object_or_404(
        HorarioExameDisponivel,
        id=horario_id,
        coordenador=coordenador
    )


    # =====================================================
    # NÃO DEIXA REMOVER SE JÁ POSSUI PACIENTE
    # =====================================================

    possui_agendamento = (
        AgendamentoExame.objects
        .filter(
            exame=horario.exame,
            medico_responsavel=horario.medico_responsavel,
            data_hora=horario.data_hora
        )
        .exists()
    )


    if possui_agendamento:

        return HttpResponseForbidden(
            "Não é possível remover este horário porque "
            "já existe um paciente agendado."
        )


    horario.delete()


    # =====================================================
    # MENSAGEM
    # =====================================================

    messages.success(
        request,
        "Horário de exame removido com sucesso."
    )


    return redirect(
        "coordenador:disponibilidade"
    )