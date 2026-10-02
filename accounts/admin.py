from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


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