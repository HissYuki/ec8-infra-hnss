from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, UserCreationForm

from accounts.models import User
from pacientes.models import Paciente
from .authentication import is_patient


class PatientAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not is_patient(user):
            raise forms.ValidationError('Esta conta não pertence a um paciente.', code='invalid_role')


class ProfessionalAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.tipo not in ('MEDICO', 'COORDENADOR') or user.is_staff or user.is_superuser:
            raise forms.ValidationError('Esta conta não pertence a um médico ou coordenador.', code='invalid_role')


class PatientPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        return (user for user in super().get_users(email) if is_patient(user))


class TOTPForm(forms.Form):
    token = forms.RegexField(
        regex=r'^\d{6}$', label='Código do autenticador',
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code', 'maxlength': '6'}),
        error_messages={'invalid': 'Digite um código de 6 dígitos.'},
    )


class PasswordResetCodeForm(forms.Form):
    code = forms.RegexField(
        regex=r'^[0-9]{6}$', label='Código recebido por e-mail',
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code', 'maxlength': '6'}),
        error_messages={'invalid': 'Digite o código de 6 dígitos.'},
    )


class RecoveryCodeForm(forms.Form):
    token = forms.CharField(
        label='Código de recuperação', max_length=32,
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
    )

    def clean_token(self):
        return self.cleaned_data['token'].replace('-', '').replace(' ', '').lower()


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
