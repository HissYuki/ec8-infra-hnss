from datetime import time, date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone

from consultas.models import (
    Consulta,
    HorarioDisponivel,
    HorarioExameDisponivel,
    AgendamentoExame,
)

from pacientes.models import Paciente

from .models import Medico

from .forms import (
    DisponibilidadeForm,
    DisponibilidadeSemanalForm,
)


# =========================================================
# HORÁRIO DE FUNCIONAMENTO DO HOSPITAL
# =========================================================

HORARIO_ABERTURA = time(6, 0)
HORARIO_FECHAMENTO = time(20, 0)


# =========================================================
# DASHBOARD DO MÉDICO
# =========================================================

@login_required
def dashboard(request):

    if request.user.tipo != "MEDICO":

        return HttpResponseForbidden(
            "Você não possui permissão para acessar esta página."
        )

    medico = Medico.objects.filter(
        usuario=request.user
    ).first()

    if medico is None:

        return HttpResponseForbidden(
            "Seu usuário está configurado como médico, "
            "mas ainda não possui um perfil médico cadastrado."
        )

    consultas = Consulta.objects.filter(
        medico=medico
    ).select_related(
        "paciente",
        "paciente__usuario"
    ).order_by(
        "data_hora"
    )

    contexto = {
        "consultas": consultas
    }

    return render(
        request,
        "medico/dashboard.html",
        contexto
    )


# =========================================================
# DADOS DO PACIENTE
# =========================================================

@login_required
def dados_paciente(request, paciente_id):

    if request.user.tipo != "MEDICO":

        return HttpResponseForbidden(
            "Você não possui permissão para acessar esta página."
        )

    medico = get_object_or_404(
        Medico,
        usuario=request.user
    )

    paciente = get_object_or_404(
        Paciente,
        id=paciente_id
    )

    possui_consulta = Consulta.objects.filter(
        medico=medico,
        paciente=paciente
    ).exists()

    if not possui_consulta:

        return HttpResponseForbidden(
            "Você não possui acesso aos dados deste paciente."
        )

    contexto = {
        "paciente": paciente
    }

    return render(
        request,
        "medico/dados_paciente.html",
        contexto
    )


# =========================================================
# CONSULTAS / EXAMES PARA O FULLCALENDAR
# =========================================================

@login_required
def consultas_calendario(request):

    if request.user.tipo != "MEDICO":

        return JsonResponse(
            {
                "erro": "Acesso não autorizado."
            },
            status=403
        )

    medico = get_object_or_404(
        Medico,
        usuario=request.user
    )

    eventos = []


    # =====================================================
    # CONSULTAS
    # =====================================================

    consultas = (
        Consulta.objects
        .filter(
            medico=medico
        )
        .select_related(
            "paciente",
            "paciente__usuario"
        )
        .order_by(
            "data_hora"
        )
    )

    for consulta in consultas:

        paciente_nome = (
            consulta.paciente.usuario.get_full_name()
            or consulta.paciente.usuario.username
        )

        eventos.append(
            {
                "id": f"consulta-{consulta.id}",
                "title": f"Consulta - {paciente_nome}",
                "start": consulta.data_hora.isoformat(),
                "end": (
                    consulta.data_hora
                    + timedelta(minutes=30)
                ).isoformat(),
                "classNames": [
                    "evento-consulta"
                ],
            }
        )


    # =====================================================
    # EXAMES
    # =====================================================

    horarios_exames = (
        HorarioExameDisponivel.objects
        .filter(
            medico_responsavel=medico
        )
        .select_related(
            "exame",
            "coordenador",
            "coordenador__usuario"
        )
        .order_by(
            "data_hora"
        )
    )

    for horario in horarios_exames:

        agendamento = (
            AgendamentoExame.objects
            .filter(
                exame=horario.exame,
                medico_responsavel=medico,
                data_hora=horario.data_hora
            )
            .select_related(
                "paciente",
                "paciente__usuario"
            )
            .first()
        )

        if agendamento:

            paciente_nome = (
                agendamento.paciente.usuario.get_full_name()
                or agendamento.paciente.usuario.username
            )

            titulo = (
                f"Exame - {horario.exame.nome} - "
                f"{paciente_nome}"
            )

        else:

            titulo = (
                f"Exame - {horario.exame.nome} "
                f"(Disponível)"
            )

        eventos.append(
            {
                "id": f"exame-{horario.id}",
                "title": titulo,
                "start": horario.data_hora.isoformat(),
                "end": (
                    horario.data_hora
                    + timedelta(minutes=30)
                ).isoformat(),
                "classNames": [
                    "evento-exame"
                ],
            }
        )

    return JsonResponse(
        eventos,
        safe=False
    )


# =========================================================
# DISPONIBILIDADE DO MÉDICO
# =========================================================

@login_required
def disponibilidade(request):

    if request.user.tipo != "MEDICO":

        return HttpResponseForbidden(
            "Você não possui permissão para acessar esta página."
        )


    medico = Medico.objects.filter(
        usuario=request.user
    ).first()


    if medico is None:

        return HttpResponseForbidden(
            "Seu usuário está configurado como médico, "
            "mas ainda não possui um perfil médico cadastrado. "
            "Solicite ao administrador que configure CRM e especialidade."
        )


    # =====================================================
    # FORMULÁRIOS
    # =====================================================

    form_diario = DisponibilidadeForm()

    form_semanal = DisponibilidadeSemanalForm()

    aba_ativa = "diaria"


    # =====================================================
    # POST
    # =====================================================

    if request.method == "POST":

        tipo = request.POST.get(
            "tipo_disponibilidade"
        )


        # =================================================
        # DISPONIBILIDADE DIÁRIA
        # =================================================

        if tipo == "diaria":

            aba_ativa = "diaria"

            form_diario = DisponibilidadeForm(
                request.POST
            )


            if form_diario.is_valid():

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
                # PROTEÇÃO DO HORÁRIO DO HOSPITAL
                # =========================================

                if (
                    hora_inicio < HORARIO_ABERTURA
                    or hora_fim > HORARIO_FECHAMENTO
                ):

                    form_diario.add_error(
                        None,
                        "Os horários devem estar entre "
                        "06:00 e 20:00."
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

                    horario_atual = inicio


                    # =====================================
                    # CONTADOR DE HORÁRIOS CRIADOS
                    # =====================================

                    horarios_criados = 0


                    while horario_atual < fim:


                        # =================================
                        # HORÁRIO DO HOSPITAL
                        # =================================

                        if not (
                            HORARIO_ABERTURA
                            <= horario_atual.time()
                            < HORARIO_FECHAMENTO
                        ):

                            horario_atual += timedelta(
                                minutes=30
                            )

                            continue


                        # =================================
                        # NÃO CRIA HORÁRIO NO PASSADO
                        # =================================

                        if horario_atual > timezone.now():


                            # =============================
                            # MÉDICO ESTÁ ESCALADO
                            # PARA ALGUM EXAME?
                            # =============================

                            possui_exame = (
                                HorarioExameDisponivel.objects
                                .filter(
                                    medico_responsavel=medico,
                                    data_hora=horario_atual
                                )
                                .exists()
                            )


                            if not possui_exame:

                                horario, criado = (
                                    HorarioDisponivel.objects
                                    .get_or_create(
                                        medico=medico,
                                        data_hora=horario_atual,
                                        defaults={
                                            "ativo": True
                                        }
                                    )
                                )


                                # =========================
                                # SOMENTE CONTA SE REALMENTE
                                # FOI CRIADO
                                # =========================

                                if criado:

                                    horarios_criados += 1


                    # IMPORTANTE:
                    # avança para o próximo horário
                        horario_atual += timedelta(
                            minutes=30
                        )


                    # =====================================
                    # MENSAGEM DE RETORNO
                    # =====================================

                    if horarios_criados > 0:

                        messages.success(
                            request,
                            (
                                f"{horarios_criados} "
                                "horário(s) disponibilizado(s) "
                                "com sucesso."
                            )
                        )

                    else:

                        messages.warning(
                            request,
                            (
                                "Nenhum novo horário foi "
                                "disponibilizado. Os horários "
                                "podem já estar cadastrados, "
                                "ocupados por exames ou estar "
                                "no passado."
                            )
                        )


                    return redirect(
                        "medicos:disponibilidade"
                    )


        # =================================================
        # DISPONIBILIDADE SEMANAL / MENSAL
        # =================================================

        elif tipo == "semanal":

            aba_ativa = "semanal"

            form_semanal = DisponibilidadeSemanalForm(
                request.POST
            )


            if form_semanal.is_valid():

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
                # PROTEÇÃO DO HORÁRIO DO HOSPITAL
                # =========================================

                if (
                    hora_inicio < HORARIO_ABERTURA
                    or hora_fim > HORARIO_FECHAMENTO
                ):

                    form_semanal.add_error(
                        None,
                        "Os horários devem estar entre "
                        "06:00 e 20:00."
                    )

                else:

                    data_atual = data_inicio

                    horarios_criados = 0


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

                            horario_atual = inicio


                            while horario_atual < fim:


                                # =========================
                                # HORÁRIO DO HOSPITAL
                                # =========================

                                if not (
                                    HORARIO_ABERTURA
                                    <= horario_atual.time()
                                    < HORARIO_FECHAMENTO
                                ):

                                    horario_atual += timedelta(
                                        minutes=30
                                    )

                                    continue


                                # =========================
                                # NÃO CRIA NO PASSADO
                                # =========================

                                if (
                                    horario_atual
                                    > timezone.now()
                                ):

                                    possui_exame = (
                                        HorarioExameDisponivel.objects
                                        .filter(
                                            medico_responsavel=medico,
                                            data_hora=horario_atual
                                        )
                                        .exists()
                                    )


                                    if not possui_exame:

                                        horario, criado = (
                                            HorarioDisponivel.objects
                                            .get_or_create(
                                                medico=medico,
                                                data_hora=horario_atual,
                                                defaults={
                                                    "ativo": True
                                                }
                                            )
                                        )


                                        if criado:

                                            horarios_criados += 1


                                horario_atual += timedelta(
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
                                f"{horarios_criados} "
                                "horário(s) disponibilizado(s) "
                                "com sucesso."
                            )
                        )

                    else:

                        messages.warning(
                            request,
                            (
                                "Nenhum novo horário foi "
                                "disponibilizado. Verifique se "
                                "os horários já existem ou se "
                                "há conflitos com exames."
                            )
                        )


                    return redirect(
                        "medicos:disponibilidade"
                    )


    # =====================================================
    # HORÁRIOS FUTUROS DO MÉDICO
    # =====================================================

    horarios_base = HorarioDisponivel.objects.filter(
        medico=medico,
        data_hora__gte=timezone.now()
    ).order_by(
        "data_hora"
    )


    # =====================================================
    # DATAS QUE POSSUEM HORÁRIOS CADASTRADOS
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
    # HORÁRIOS DO DIA
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
        "medico/disponibilidade.html",
        contexto
    )


# =========================================================
# REMOVER HORÁRIO
# =========================================================

@login_required
def remover_horario(request, horario_id):

    if request.user.tipo != "MEDICO":

        return HttpResponseForbidden(
            "Acesso não autorizado."
        )


    if request.method != "POST":

        return HttpResponseForbidden(
            "Método inválido."
        )


    medico = get_object_or_404(
        Medico,
        usuario=request.user
    )


    horario = get_object_or_404(
        HorarioDisponivel,
        id=horario_id,
        medico=medico
    )


    # =====================================================
    # NÃO REMOVE SE JÁ POSSUI CONSULTA
    # =====================================================

    possui_consulta = Consulta.objects.filter(
        medico=medico,
        data_hora=horario.data_hora
    ).exists()


    if possui_consulta:

        return HttpResponseForbidden(
            "Esse horário já possui uma consulta agendada."
        )


    horario.delete()


    messages.success(
        request,
        "Horário removido com sucesso."
    )


    return redirect(
        "medicos:disponibilidade"
    )


# =========================================================
# REMOVER TODOS OS HORÁRIOS DISPONÍVEIS DE UM DIA
# =========================================================

@login_required
@require_POST
def remover_todos_horarios(request):

    if request.user.tipo != "MEDICO":

        return HttpResponseForbidden(
            "Acesso não autorizado."
        )


    medico = get_object_or_404(
        Medico,
        usuario=request.user
    )


    data_recebida = request.POST.get(
        "data"
    )


    try:

        data_selecionada = date.fromisoformat(
            data_recebida
        )

    except (ValueError, TypeError):

        return HttpResponseForbidden(
            "Data inválida."
        )


    # =====================================================
    # REMOVE SOMENTE HORÁRIOS DISPONÍVEIS
    # =====================================================

    quantidade, _ = (
        HorarioDisponivel.objects
        .filter(
            medico=medico,
            data_hora__date=data_selecionada,
            ativo=True
        )
        .delete()
    )


    if quantidade > 0:

        messages.success(
            request,
            (
                f"{quantidade} horário(s) disponível(is) "
                "removido(s) com sucesso."
            )
        )

    else:

        messages.warning(
            request,
            (
                "Não havia horários disponíveis "
                "para remover neste dia."
            )
        )


    url = reverse(
        "medicos:disponibilidade"
    )


    return redirect(
        f"{url}?data={data_selecionada.isoformat()}"
    )