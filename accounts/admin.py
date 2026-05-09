from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User

from .models import EmailVerification


class EmailVerificationInline(admin.TabularInline):
    model = EmailVerification
    extra = 0
    fields = ("email", "purpose", "sent_at", "verified_at", "expires_at")
    readonly_fields = ("sent_at", "verified_at")
    can_delete = False


class CustomUserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_active", "is_staff", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser", "groups")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)
    inlines = [EmailVerificationInline]


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, CustomUserAdmin)


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("email", "purpose", "user", "sent_at", "verified_at", "expires_at")
    search_fields = ("email", "user__username", "user__email")
    list_filter = ("purpose", "verified_at")
