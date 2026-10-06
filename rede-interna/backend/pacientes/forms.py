from django import forms

from .models import Paciente


class DadosPacienteForm(forms.ModelForm):

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


    class Meta:

        model = Paciente

        fields = (
            "first_name",
            "last_name",
            "email",
            "telefone",
            "data_nascimento",
        )

        widgets = {

            "data_nascimento":
                forms.DateInput(
                    attrs={
                        "type": "date"
                    }
                ),

        }


    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)


        if self.instance.pk:

            self.fields[
                "first_name"
            ].initial = (
                self.instance.usuario.first_name
            )

            self.fields[
                "last_name"
            ].initial = (
                self.instance.usuario.last_name
            )

            self.fields[
                "email"
            ].initial = (
                self.instance.usuario.email
            )


    def save(self, commit=True):

        paciente = super().save(
            commit=False
        )


        usuario = paciente.usuario


        usuario.first_name = (
            self.cleaned_data["first_name"]
        )

        usuario.last_name = (
            self.cleaned_data["last_name"]
        )

        usuario.email = (
            self.cleaned_data["email"]
        )


        if commit:

            usuario.save()

            paciente.save()


        return paciente