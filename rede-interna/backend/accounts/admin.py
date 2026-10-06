from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

# Segredos e códigos de recuperação não são editáveis pelo painel administrativo.
for otp_model in (StaticDevice, TOTPDevice):
    if admin.site.is_registered(otp_model):
        admin.site.unregister(otp_model)


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    fieldsets = UserAdmin.fieldsets + (
        (
            "Tipo de usuário",
            {
                "fields": ("tipo",)
            }
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Tipo de usuário",
            {
                "fields": ("tipo",)
            }
        ),
    )

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "tipo",
        "is_staff",
    )
