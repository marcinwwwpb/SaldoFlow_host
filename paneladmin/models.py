from django.conf import settings
from django.db import models


class UserRole(models.Model):
    ROLE_SUPERADMIN = "SUPERADMIN"
    ROLE_ADMIN = "ADMIN"
    ROLE_KSIEGOWY = "KSIEGOWY"
    ROLE_AUDYTOR = "AUDYTOR"
    ROLE_UZYTKOWNIK = "UZYTKOWNIK"
    ROLE_DEMON = "DEMON"
    ROLE_CHOICES = [
        (ROLE_SUPERADMIN, "Superadministrator"),
        (ROLE_ADMIN, "Administrator"),
        (ROLE_KSIEGOWY, "Księgowy"),
        (ROLE_AUDYTOR, "Audytor"),
        (ROLE_UZYTKOWNIK, "Użytkownik"),
        (ROLE_DEMON, "Konto techniczne demona"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="panel_role")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_UZYTKOWNIK)
    notes = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rola użytkownika"
        verbose_name_plural = "Role użytkowników"
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user} — {self.get_role_display()}"


class AdminAuditLog(models.Model):
    ACTION_CREATE = "CREATE"
    ACTION_UPDATE = "UPDATE"
    ACTION_DELETE = "DELETE"
    ACTION_IMPORT_SKIP = "IMPORT_SKIP"
    ACTION_CHOICES = [
        (ACTION_CREATE, "Utworzenie"),
        (ACTION_UPDATE, "Aktualizacja"),
        (ACTION_DELETE, "Usunięcie"),
        (ACTION_IMPORT_SKIP, "Pominięcie duplikatu"),
    ]

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="admin_audit_logs")
    module = models.CharField(max_length=20)
    entity_type = models.CharField(max_length=100)
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log administracyjny"
        verbose_name_plural = "Logi administracyjne"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["module", "created_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self):
        return f"{self.module} {self.action} {self.entity_type}#{self.entity_id or '-'}"


class SignificantDatabaseChange(models.Model):
    OPERATION_INSERT = "INSERT"
    OPERATION_UPDATE = "UPDATE"
    OPERATION_DELETE = "DELETE"
    OPERATION_CHOICES = [
        (OPERATION_INSERT, "INSERT"),
        (OPERATION_UPDATE, "UPDATE"),
        (OPERATION_DELETE, "DELETE"),
    ]

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="db_change_logs")
    source = models.CharField(max_length=50, default="django")
    app_label = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    object_pk = models.CharField(max_length=64)
    operation = models.CharField(max_length=10, choices=OPERATION_CHOICES)
    owner_user_id = models.PositiveIntegerField(null=True, blank=True)
    tenant_key = models.CharField(max_length=100, default="system:global")
    changed_fields = models.JSONField(default=list, blank=True)
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Istotna zmiana w bazie"
        verbose_name_plural = "Istotne zmiany w bazie"
        ordering = ["-changed_at", "-id"]
        indexes = [
            models.Index(fields=["app_label", "model_name", "changed_at"]),
            models.Index(fields=["owner_user_id", "changed_at"]),
            models.Index(fields=["tenant_key", "changed_at"]),
            models.Index(fields=["operation", "changed_at"]),
        ]

    def __str__(self):
        return f"{self.app_label}.{self.model_name} {self.operation} #{self.object_pk}"


class OperacjaArchiwum(models.Model):
    source_id = models.PositiveIntegerField()
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    deleted_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Archiwum operacji"
        verbose_name_plural = "Archiwum operacji"
        ordering = ["-deleted_at", "-id"]


class FakturaKosztowaArchiwum(models.Model):
    source_id = models.PositiveIntegerField()
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    deleted_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Archiwum faktur kosztowych"
        verbose_name_plural = "Archiwum faktur kosztowych"
        ordering = ["-deleted_at", "-id"]
