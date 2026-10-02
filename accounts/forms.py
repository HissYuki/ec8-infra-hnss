from django import forms
from django.contrib.auth.forms import UserCreationForm

from accounts.models import User
from pacientes.models import Paciente


class CadastroPacienteForm(UserCreationForm):

    first_name = forms.CharField(
        label="Nome",
        max_length=150
    )

    last_name = forms.CharField(
        label="Sobrenome",
        max_length=150
    )

    email = forms.EmailField(
        label="E-mail"
    )

    telefone = forms.CharField(
        label="Telefone",
        max_length=20
    )

    data_nascimento = forms.DateField(
        label="Data de nascimento",
        widget=forms.DateInput(
            attrs={"type": "date"}
        )
    )

    class Meta:
        model = User

        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "telefone",
            "data_nascimento",
            "password1",
            "password2",
        )

    def save(self, commit=True):

        user = super().save(commit=False)

        user.tipo = "PACIENTE"

        if commit:
            user.save()

            Paciente.objects.create(
                usuario=user,
                telefone=self.cleaned_data["telefone"],
                data_nascimento=self.cleaned_data["data_nascimento"]
            )

        return user