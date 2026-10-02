from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from consultas.models import (
    Consulta,
    HorarioDisponivel,
    Exame,
    HorarioExameDisponivel,
    AgendamentoExame,
)

from medicos.models import Medico
from pacientes.models import Paciente

from .forms import DadosPacienteForm


# =========================================================
# PÁGINA INICIAL DO PACIENTE
# =========================================================

@login_required
def dashboard(request):

    if request.user.tipo != "PACIENTE":

        return HttpResponseForbidden(
            "Você não possui permissão para acessar esta página."
        )


    get_object_or_404(
        Paciente,
        usuario=request.user
    )


    return render(
        request,
        "paciente/dashboard.html"
    )


# =========================================================
# PÁGINA DE CONSULTAS
# =========================================================

@login_required
def pagina_consultas(request):

    if request.user.tipo != "PACIENTE":

        return HttpResponseForbidden(
            "Você não possui permissão para acessar esta página."
        )


    paciente = get_object_or_404(
        Paciente,
        usuario=request.user
    )


    agora = timezone.now()


    # =====================================================
    # CONSULTAS FUTURAS
    # =====================================================

    consultas_atuais = Consulta.objects.filter(
        paciente=paciente,
        data_hora__gte=agora
    ).select_related(
        "medico",
        "medico__usuario"
    ).order_by(
        "data_hora"
    )


    # =====================================================
    # CONSULTAS PASSADAS
    # =====================================================

    consultas_passadas = Consulta.objects.filter(
        paciente=paciente,
        data_hora__lt=agora
    ).select_related(
        "medico",
        "medico__usuario"
    ).order_by(
        "-data_hora"
    )


    # =====================================================
    # MÉDICOS
    # =====================================================

    medicos = Medico.objects.select_related(
        "usuario"
    ).all().order_by(
        "usuario__first_name",
        "usuario__last_name"
    )


    contexto = {

        "consultas_atuais":
            consultas_atuais,

        "consultas_passadas":
            consultas_passadas,

        "medicos":
            medicos,

    }


    return render(
        request,
        "paciente/consultas.html",
        contexto
    )


# =========================================================
# PÁGINA DE EXAMES
# =========================================================

@login_required
def pagina_exames(request):

    if request.user.tipo != "PACIENTE":

        return HttpResponseForbidden(
            "Você não possui permissão para acessar esta página."
        )


    paciente = get_object_or_404(
        Paciente,
        usuario=request.user
    )


    agora = timezone.now()


    # =====================================================
    # EXAMES FUTUROS
    # =====================================================

    exames_atuais = AgendamentoExame.objects.filter(
        paciente=paciente,
        data_hora__gte=agora
    ).select_related(
        "exame",
        "medico_responsavel",
        "medico_responsavel__usuario"
    ).order_by(
        "data_hora"
    )


    # =====================================================
    # EXAMES PASSADOS
    # =====================================================

    exames_passados = AgendamentoExame.objects.filter(
        paciente=paciente,
        data_hora__lt=agora
    ).select_related(
        "exame",
        "medico_responsavel",
        "medico_responsavel__usuario"
    ).order_by(
        "-data_hora"
    )


    # =====================================================
    # TIPOS DE EXAMES
    # =====================================================

    exames = Exame.objects.filter(
        ativo=True
    ).order_by(
        "nome"
    )


    contexto = {

        "exames_atuais":
            exames_atuais,

        "exames_passados":
            exames_passados,

        "exames":
            exames,

    }


    return render(
        request,
        "paciente/exames.html",
        contexto
    )


# =========================================================
# HORÁRIOS DISPONÍVEIS PARA CONSULTA
# =========================================================

@login_required
def horarios_disponiveis(request, medico_id):

    if request.user.tipo != "PACIENTE":

        return JsonResponse(
            {
                "erro": "Acesso não autorizado."
            },
            status=403
        )


    medico = get_object_or_404(
        Medico,
        id=medico_id
    )


    paciente = get_object_or_404(
        Paciente,
        usuario=request.user
    )


    agora = timezone.now()


    # =====================================================
    # PACIENTE JÁ TEM CONSULTA FUTURA COM ESTE MÉDICO?
    # =====================================================

    consulta_existente = Consulta.objects.filter(
        medico=medico,
        paciente=paciente,
        data_hora__gte=agora
    ).exists()


    if consulta_existente:

        return JsonResponse(
            {
                "bloqueado": True,
                "mensagem":
                    "Você já possui uma consulta marcada com esse médico."
            }
        )


    # =====================================================
    # DISPONIBILIDADE CRIADA PELO MÉDICO
    # =====================================================

    horarios = HorarioDisponivel.objects.filter(
        medico=medico,
        ativo=True,
        data_hora__gte=agora
    ).order_by(
        "data_hora"
    )


    # =====================================================
    # CONSULTAS QUE JÁ OCUPAM A AGENDA DO MÉDICO
    # =====================================================

    horarios_medico_ocupados = Consulta.objects.filter(
        medico=medico,
        data_hora__gte=agora
    ).values_list(
        "data_hora",
        flat=True
    )


    # =====================================================
    # EXAMES PARA OS QUAIS O MÉDICO FOI ESCALADO
    # =====================================================

    horarios_exames_medico = (
        HorarioExameDisponivel.objects.filter(
            medico_responsavel=medico,
            data_hora__gte=agora
        ).values_list(
            "data_hora",
            flat=True
        )
    )


    # =====================================================
    # CONSULTAS JÁ EXISTENTES DO PACIENTE
    # =====================================================

    consultas_paciente = Consulta.objects.filter(
        paciente=paciente,
        data_hora__gte=agora
    ).values_list(
        "data_hora",
        flat=True
    )


    # =====================================================
    # EXAMES JÁ EXISTENTES DO PACIENTE
    # =====================================================

    exames_paciente = AgendamentoExame.objects.filter(
        paciente=paciente,
        data_hora__gte=agora
    ).values_list(
        "data_hora",
        flat=True
    )


    # =====================================================
    # REMOVE TODOS OS CONFLITOS
    # =====================================================

    horarios = horarios.exclude(
        data_hora__in=horarios_medico_ocupados
    ).exclude(
        data_hora__in=horarios_exames_medico
    ).exclude(
        data_hora__in=consultas_paciente
    ).exclude(
        data_hora__in=exames_paciente
    )


    # =====================================================
    # FULLCALENDAR
    # =====================================================

    eventos = []


    for horario in horarios:

        eventos.append(
            {
                "id":
                    horario.id,

                "title":
                    "Disponível",

                "start":
                    horario.data_hora.isoformat(),

                "end":
                    (
                        horario.data_hora
                        + timedelta(minutes=30)
                    ).isoformat(),

                "classNames": [
                    "horario-disponivel"
                ],
            }
        )


    return JsonResponse(
        {
            "bloqueado": False,
            "eventos": eventos,
        }
    )


# =========================================================
# AGENDAR CONSULTA
# =========================================================

@login_required
def agendar_consulta(request, horario_id):

    if request.user.tipo != "PACIENTE":

        return HttpResponseForbidden(
            "Acesso não autorizado."
        )


    if request.method != "POST":

        return HttpResponseForbidden(
            "Método inválido."
        )


    try:

        with transaction.atomic():

            paciente = (
                Paciente.objects
                .select_for_update()
                .get(
                    usuario=request.user
                )
            )


            horario = (
                HorarioDisponivel.objects
                .select_for_update()
                .get(
                    id=horario_id,
                    ativo=True
                )
            )


            # =================================================
            # HORÁRIO JÁ PASSOU?
            # =================================================

            if horario.data_hora <= timezone.now():

                return HttpResponseForbidden(
                    "Esse horário já passou."
                )


            # =================================================
            # JÁ POSSUI CONSULTA FUTURA COM ESTE MÉDICO?
            # =================================================

            if Consulta.objects.filter(
                paciente=paciente,
                medico=horario.medico,
                data_hora__gte=timezone.now()
            ).exists():

                return HttpResponseForbidden(
                    "Você já possui uma consulta marcada com esse médico."
                )


            # =================================================
            # MÉDICO JÁ POSSUI CONSULTA NESTE HORÁRIO?
            # =================================================

            if Consulta.objects.filter(
                medico=horario.medico,
                data_hora=horario.data_hora
            ).exists():

                return HttpResponseForbidden(
                    "Esse horário já foi reservado."
                )


            # =================================================
            # MÉDICO ESTÁ ESCALADO PARA EXAME?
            # =================================================

            if HorarioExameDisponivel.objects.filter(
                medico_responsavel=horario.medico,
                data_hora=horario.data_hora
            ).exists():

                return HttpResponseForbidden(
                    "O médico não está disponível para consulta neste horário."
                )


            # =================================================
            # PACIENTE JÁ TEM CONSULTA NO HORÁRIO?
            # =================================================

            if Consulta.objects.filter(
                paciente=paciente,
                data_hora=horario.data_hora
            ).exists():

                return HttpResponseForbidden(
                    "Você já possui outra consulta nesse horário."
                )


            # =================================================
            # PACIENTE JÁ TEM EXAME NO HORÁRIO?
            # =================================================

            if AgendamentoExame.objects.filter(
                paciente=paciente,
                data_hora=horario.data_hora
            ).exists():

                return HttpResponseForbidden(
                    "Você já possui um exame nesse horário."
                )


            # =================================================
            # CRIA CONSULTA
            # =================================================

            Consulta.objects.create(
                medico=horario.medico,
                paciente=paciente,
                data_hora=horario.data_hora,
            )


            horario.ativo = False


            horario.save(
                update_fields=[
                    "ativo"
                ]
            )


    except Paciente.DoesNotExist:

        return HttpResponseForbidden(
            "Perfil de paciente não encontrado."
        )


    except HorarioDisponivel.DoesNotExist:

        return HttpResponseForbidden(
            "Horário indisponível."
        )


    return redirect(
        "pacientes:consultas"
    )


# =========================================================
# CANCELAR CONSULTA
# =========================================================

@login_required
def cancelar_consulta(request, consulta_id):

    if request.user.tipo != "PACIENTE":

        return HttpResponseForbidden(
            "Acesso não autorizado."
        )


    if request.method != "POST":

        return HttpResponseForbidden(
            "Método inválido."
        )


    paciente = get_object_or_404(
        Paciente,
        usuario=request.user
    )


    with transaction.atomic():

        consulta = get_object_or_404(
            Consulta.objects.select_for_update(),
            id=consulta_id,
            paciente=paciente
        )


        if consulta.data_hora <= timezone.now():

            return HttpResponseForbidden(
                "Não é possível cancelar uma consulta que já ocorreu."
            )


        horario = (
            HorarioDisponivel.objects
            .select_for_update()
            .filter(
                medico=consulta.medico,
                data_hora=consulta.data_hora
            )
            .first()
        )


        consulta.delete()


        if horario:

            horario.ativo = True


            horario.save(
                update_fields=[
                    "ativo"
                ]
            )


    return redirect(
        "pacientes:consultas"
    )


# =========================================================
# HORÁRIOS DISPONÍVEIS PARA EXAME
# =========================================================

@login_required
def horarios_exame_disponiveis(request, exame_id):

    if request.user.tipo != "PACIENTE":

        return JsonResponse(
            {
                "erro": "Acesso não autorizado."
            },
            status=403
        )


    exame = get_object_or_404(
        Exame,
        id=exame_id,
        ativo=True
    )


    paciente = get_object_or_404(
        Paciente,
        usuario=request.user
    )


    agora = timezone.now()


    # =====================================================
    # PACIENTE JÁ POSSUI ESTE EXAME FUTURO?
    # =====================================================

    exame_existente = AgendamentoExame.objects.filter(
        exame=exame,
        paciente=paciente,
        data_hora__gte=agora
    ).exists()


    if exame_existente:

        return JsonResponse(
            {
                "bloqueado": True,
                "mensagem":
                    "Você já possui este exame agendado."
            }
        )


    # =====================================================
    # HORÁRIOS CRIADOS PELO COORDENADOR
    #
    # O paciente não escolhe o médico.
    # Cada horário já possui um médico responsável.
    # =====================================================

    horarios = (
        HorarioExameDisponivel.objects.filter(
            exame=exame,
            ativo=True,
            medico_responsavel__isnull=False,
            coordenador__isnull=False,
            data_hora__gte=agora
        )
        .select_related(
            "medico_responsavel",
            "medico_responsavel__usuario",
            "coordenador",
            "coordenador__usuario"
        )
        .order_by(
            "data_hora",
            "id"
        )
    )


    # =====================================================
    # HORÁRIOS EM QUE O PACIENTE JÁ TEM CONSULTA
    # =====================================================

    consultas_paciente = Consulta.objects.filter(
        paciente=paciente,
        data_hora__gte=agora
    ).values_list(
        "data_hora",
        flat=True
    )


    # =====================================================
    # HORÁRIOS EM QUE O PACIENTE JÁ TEM OUTRO EXAME
    # =====================================================

    exames_paciente = AgendamentoExame.objects.filter(
        paciente=paciente,
        data_hora__gte=agora
    ).values_list(
        "data_hora",
        flat=True
    )


    horarios = horarios.exclude(
        data_hora__in=consultas_paciente
    ).exclude(
        data_hora__in=exames_paciente
    )


    eventos = []

    horarios_vistos = set()


    for horario in horarios:

        # =================================================
        # PROTEÇÃO:
        # MÉDICO NÃO PODE ESTAR EM CONSULTA
        # =================================================

        medico_em_consulta = Consulta.objects.filter(
            medico=horario.medico_responsavel,
            data_hora=horario.data_hora
        ).exists()


        if medico_em_consulta:

            continue


        # =================================================
        # PROTEÇÃO:
        # MÉDICO NÃO PODE ESTAR EM OUTRO EXAME
        # =================================================

        medico_em_outro_exame = (
            AgendamentoExame.objects.filter(
                medico_responsavel=horario.medico_responsavel,
                data_hora=horario.data_hora
            ).exists()
        )


        if medico_em_outro_exame:

            continue


        # =================================================
        # SE EXISTIREM DOIS MÉDICOS DISPONÍVEIS
        # NO MESMO HORÁRIO, O PACIENTE VÊ
        # APENAS UM BLOCO "DISPONÍVEL"
        # =================================================

        if horario.data_hora in horarios_vistos:

            continue


        horarios_vistos.add(
            horario.data_hora
        )


        eventos.append(
            {
                "id":
                    horario.id,

                "title":
                    "Disponível",

                "start":
                    horario.data_hora.isoformat(),

                "end":
                    (
                        horario.data_hora
                        + timedelta(minutes=30)
                    ).isoformat(),

                "classNames": [
                    "horario-disponivel"
                ],
            }
        )


    return JsonResponse(
        {
            "bloqueado": False,
            "eventos": eventos,
        }
    )


# =========================================================
# AGENDAR EXAME
# =========================================================

@login_required
def agendar_exame(request, horario_id):

    if request.user.tipo != "PACIENTE":

        return HttpResponseForbidden(
            "Acesso não autorizado."
        )


    if request.method != "POST":

        return HttpResponseForbidden(
            "Método inválido."
        )


    try:

        with transaction.atomic():

            paciente = (
                Paciente.objects
                .select_for_update()
                .get(
                    usuario=request.user
                )
            )


            horario = (
                HorarioExameDisponivel.objects
                .select_for_update()
                .select_related(
                    "exame",
                    "medico_responsavel",
                    "coordenador"
                )
                .get(
                    id=horario_id,
                    ativo=True
                )
            )


            # =================================================
            # HORÁRIO PRECISA TER MÉDICO E COORDENADOR
            # =================================================

            if horario.medico_responsavel is None:

                return HttpResponseForbidden(
                    "Este horário não possui médico responsável."
                )


            if horario.coordenador is None:

                return HttpResponseForbidden(
                    "Este horário não possui coordenador responsável."
                )


            # =================================================
            # HORÁRIO JÁ PASSOU?
            # =================================================

            if horario.data_hora <= timezone.now():

                return HttpResponseForbidden(
                    "Esse horário já passou."
                )


            # =================================================
            # JÁ POSSUI ESTE EXAME FUTURAMENTE?
            # =================================================

            if AgendamentoExame.objects.filter(
                paciente=paciente,
                exame=horario.exame,
                data_hora__gte=timezone.now()
            ).exists():

                return HttpResponseForbidden(
                    "Você já possui este exame agendado."
                )


            # =================================================
            # PACIENTE JÁ POSSUI CONSULTA NESTE HORÁRIO?
            # =================================================

            if Consulta.objects.filter(
                paciente=paciente,
                data_hora=horario.data_hora
            ).exists():

                return HttpResponseForbidden(
                    "Você já possui uma consulta nesse horário."
                )


            # =================================================
            # PACIENTE JÁ POSSUI OUTRO EXAME NESTE HORÁRIO?
            # =================================================

            if AgendamentoExame.objects.filter(
                paciente=paciente,
                data_hora=horario.data_hora
            ).exists():

                return HttpResponseForbidden(
                    "Você já possui outro exame nesse horário."
                )


            # =================================================
            # MÉDICO POSSUI CONSULTA NESTE HORÁRIO?
            # =================================================

            if Consulta.objects.filter(
                medico=horario.medico_responsavel,
                data_hora=horario.data_hora
            ).exists():

                return HttpResponseForbidden(
                    "O médico responsável não está disponível nesse horário."
                )


            # =================================================
            # MÉDICO JÁ POSSUI OUTRO EXAME?
            # =================================================

            if AgendamentoExame.objects.filter(
                medico_responsavel=horario.medico_responsavel,
                data_hora=horario.data_hora
            ).exists():

                return HttpResponseForbidden(
                    "O médico responsável já possui outro exame nesse horário."
                )


            # =================================================
            # CRIA O AGENDAMENTO
            #
            # Médico e coordenador são herdados do horário
            # definido pelo coordenador.
            # =================================================

            AgendamentoExame.objects.create(

                exame=
                    horario.exame,

                paciente=
                    paciente,

                medico_responsavel=
                    horario.medico_responsavel,

                coordenador=
                    horario.coordenador,

                data_hora=
                    horario.data_hora,

            )


            # =================================================
            # HORÁRIO DEIXA DE ESTAR DISPONÍVEL
            # =================================================

            horario.ativo = False


            horario.save(
                update_fields=[
                    "ativo"
                ]
            )


    except Paciente.DoesNotExist:

        return HttpResponseForbidden(
            "Perfil de paciente não encontrado."
        )


    except HorarioExameDisponivel.DoesNotExist:

        return HttpResponseForbidden(
            "Horário indisponível."
        )


    return redirect(
        "pacientes:exames"
    )


# =========================================================
# CANCELAR EXAME
# =========================================================

@login_required
def cancelar_exame(request, agendamento_id):

    if request.user.tipo != "PACIENTE":

        return HttpResponseForbidden(
            "Acesso não autorizado."
        )


    if request.method != "POST":

        return HttpResponseForbidden(
            "Método inválido."
        )


    paciente = get_object_or_404(
        Paciente,
        usuario=request.user
    )


    with transaction.atomic():

        agendamento = get_object_or_404(
            AgendamentoExame.objects.select_for_update(),
            id=agendamento_id,
            paciente=paciente
        )


        if agendamento.data_hora <= timezone.now():

            return HttpResponseForbidden(
                "Não é possível cancelar um exame que já ocorreu."
            )


        # =================================================
        # PROCURA EXATAMENTE O HORÁRIO
        # QUE ORIGINOU O AGENDAMENTO
        # =================================================

        horario = (
            HorarioExameDisponivel.objects
            .select_for_update()
            .filter(
                exame=agendamento.exame,
                medico_responsavel=
                    agendamento.medico_responsavel,
                data_hora=
                    agendamento.data_hora
            )
            .first()
        )


        agendamento.delete()


        # =================================================
        # LIBERA NOVAMENTE O HORÁRIO
        # =================================================

        if horario:

            horario.ativo = True


            horario.save(
                update_fields=[
                    "ativo"
                ]
            )


    return redirect(
        "pacientes:exames"
    )


# =========================================================
# MEUS DADOS
# =========================================================

@login_required
def meus_dados(request):

    if request.user.tipo != "PACIENTE":

        return HttpResponseForbidden(
            "Você não possui permissão para acessar esta página."
        )


    paciente = get_object_or_404(
        Paciente,
        usuario=request.user
    )


    if request.method == "POST":

        form = DadosPacienteForm(
            request.POST,
            instance=paciente
        )


        if form.is_valid():

            form.save()


            return redirect(
                "pacientes:meus_dados"
            )


    else:

        form = DadosPacienteForm(
            instance=paciente
        )


    contexto = {
        "form": form
    }


    return render(
        request,
        "paciente/meus_dados.html",
        contexto
    )