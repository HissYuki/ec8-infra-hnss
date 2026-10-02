from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .forms import CadastroPacienteForm


# =========================================================
# LOGIN DO PACIENTE
# =========================================================

def login_paciente(request):

    # ==========================================
    # USUÁRIO JÁ AUTENTICADO
    # ==========================================

    if request.user.is_authenticated:

        # Administrador
        if request.user.is_superuser:

            return redirect(
                "/admin/"
            )


        # Paciente
        if request.user.tipo == "PACIENTE":

            return redirect(
                "pacientes:dashboard"
            )


        # Médico
        if request.user.tipo == "MEDICO":

            return redirect(
                "medicos:dashboard"
            )


        # Coordenador
        if request.user.tipo == "COORDENADOR":

            return redirect(
                "coordenador:dashboard"
            )


    # ==========================================
    # FORMULÁRIO DE LOGIN
    # ==========================================

    form = AuthenticationForm(
        request,
        data=request.POST or None
    )


    if request.method == "POST" and form.is_valid():

        user = form.get_user()


        # Esta página é exclusiva para pacientes
        if user.tipo != "PACIENTE":

            form.add_error(
                None,
                "Esta conta não pertence a um paciente."
            )


        else:

            login(
                request,
                user
            )


            return redirect(
                "pacientes:dashboard"
            )


    return render(
        request,
        "registration/login_paciente.html",
        {
            "form": form
        }
    )


# =========================================================
# LOGIN DOS PROFISSIONAIS DE SAÚDE
# MÉDICO + COORDENADOR
# =========================================================

def login_medico(request):

    # ==========================================
    # USUÁRIO JÁ AUTENTICADO
    # ==========================================

    if request.user.is_authenticated:

        # Administrador
        if request.user.is_superuser:

            return redirect(
                "/admin/"
            )


        # Médico
        if request.user.tipo == "MEDICO":

            return redirect(
                "medicos:dashboard"
            )


        # Coordenador
        if request.user.tipo == "COORDENADOR":

            return redirect(
                "coordenador:dashboard"
            )


        # Paciente
        if request.user.tipo == "PACIENTE":

            return redirect(
                "pacientes:dashboard"
            )


    # ==========================================
    # FORMULÁRIO DE LOGIN
    # ==========================================

    form = AuthenticationForm(
        request,
        data=request.POST or None
    )


    if request.method == "POST" and form.is_valid():

        user = form.get_user()


        # ======================================
        # SOMENTE MÉDICOS E COORDENADOR
        # ======================================

        if user.tipo not in [
            "MEDICO",
            "COORDENADOR",
        ]:

            form.add_error(
                None,
                "Esta conta não pertence a um médico ou coordenador."
            )


        else:

            login(
                request,
                user
            )


            # ==================================
            # MÉDICO
            # ==================================

            if user.tipo == "MEDICO":

                return redirect(
                    "medicos:dashboard"
                )


            # ==================================
            # COORDENADOR
            # ==================================

            if user.tipo == "COORDENADOR":

                return redirect(
                    "coordenador:dashboard"
                )


    return render(
        request,
        "registration/login_medico.html",
        {
            "form": form
        }
    )


# =========================================================
# CADASTRO DO PACIENTE
# =========================================================

def registrar_paciente(request):

    # Se já estiver autenticado,
    # redireciona para sua própria área.
    if request.user.is_authenticated:

        if request.user.is_superuser:

            return redirect(
                "/admin/"
            )


        if request.user.tipo == "PACIENTE":

            return redirect(
                "pacientes:dashboard"
            )


        if request.user.tipo == "MEDICO":

            return redirect(
                "medicos:dashboard"
            )


        if request.user.tipo == "COORDENADOR":

            return redirect(
                "coordenador:dashboard"
            )


    # ==========================================
    # CADASTRO
    # ==========================================

    if request.method == "POST":

        form = CadastroPacienteForm(
            request.POST
        )


        if form.is_valid():

            user = form.save()


            login(
                request,
                user
            )


            return redirect(
                "pacientes:dashboard"
            )


    else:

        form = CadastroPacienteForm()


    return render(
        request,
        "registration/registrar_paciente.html",
        {
            "form": form
        }
    )


# =========================================================
# LOGOUT
# =========================================================

@require_POST
def logout_usuario(request):

    # ==========================================
    # GUARDA O TIPO ANTES DE ENCERRAR A SESSÃO
    # ==========================================

    if request.user.is_authenticated:

        if request.user.is_superuser:

            tipo_usuario = "ADMIN"

        else:

            tipo_usuario = request.user.tipo


    else:

        tipo_usuario = None


    # ==========================================
    # ENCERRA A SESSÃO
    # ==========================================

    logout(
        request
    )


    # ==========================================
    # MÉDICO E COORDENADOR
    # ==========================================

    if tipo_usuario in [
        "MEDICO",
        "COORDENADOR",
    ]:

        return redirect(
            "accounts:login_medico"
        )


    # ==========================================
    # ADMINISTRADOR
    # ==========================================

    if tipo_usuario == "ADMIN":

        return redirect(
            "/admin/"
        )


    # ==========================================
    # PACIENTE / OUTROS CASOS
    # ==========================================

    return redirect(
        "accounts:login_paciente"
    )

def inicio(request):

    return render(
        request,
        "inicio.html"
    )