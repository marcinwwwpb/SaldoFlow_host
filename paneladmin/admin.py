from django.contrib import admin
from .models import AdminAuditLog, FakturaKosztowaArchiwum, OperacjaArchiwum, SignificantDatabaseChange, UserRole


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "updated_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "notes")


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "module", "entity_type", "entity_id", "action", "actor")
    list_filter = ("module", "action")
    search_fields = ("entity_type", "payload")
    readonly_fields = ("created_at",)


@admin.register(SignificantDatabaseChange)
class SignificantDatabaseChangeAdmin(admin.ModelAdmin):
    list_display = ("changed_at", "app_label", "model_name", "object_pk", "operation", "actor", "tenant_key")
    list_filter = ("app_label", "model_name", "operation")
    search_fields = ("object_pk", "tenant_key", "actor__username")
    readonly_fields = ("changed_at",)


admin.site.register(OperacjaArchiwum)
admin.site.register(FakturaKosztowaArchiwum)
