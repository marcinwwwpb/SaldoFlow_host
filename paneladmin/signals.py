from decimal import Decimal
from datetime import date, datetime
from uuid import UUID

from django.db import connection
from django.db.models import Model
from django.db.models.signals import pre_delete, pre_save, post_save
from django.dispatch import receiver

from .current_actor import get_current_actor, get_current_source
from .models import SignificantDatabaseChange

TRACKED_MODELS = {
    'auth.User',
    'accounts.EmailVerification',
    'finanse.KontoDomowe',
    'finanse.Operacja',
    'finanse.CelOszczednosciowy',
    'finanse.RaportMiesieczny',
    'finanse.DemonLog',
    'firma.UstawieniaFirmy',
    'firma.Kontrahent',
    'firma.FakturaSprzedazy',
    'firma.FakturaKosztowa',
    'firma.JPKDeklaracja',
    'firma.ImportDemona',
    'paneladmin.UserRole',
}

IGNORED_FIELDS = {'last_login'}
VOLATILE_FIELDS = {'updated_at', 'modified_at', 'utworzono_o', 'wygenerowano_o', 'created_at'}


def _audit_table_ready():
    try:
        return SignificantDatabaseChange._meta.db_table in connection.introspection.table_names()
    except Exception:
        return False


def _serialize_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _snapshot(instance: Model):
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in IGNORED_FIELDS:
            continue
        value = getattr(instance, field.attname)
        data[field.name] = _serialize_value(value)
    return data


def _owner_user_id(instance: Model):
    for attr in ('uzytkownik_id', 'user_id', 'actor_id'):
        if hasattr(instance, attr):
            return getattr(instance, attr)
    return None


def _tenant_key(instance: Model):
    owner = _owner_user_id(instance)
    if owner:
        return f'user:{owner}'
    return 'system:global'


def _changed_fields(before, after):
    changed = []
    keys = sorted(set(before) | set(after))
    for key in keys:
        if key in VOLATILE_FIELDS:
            continue
        if before.get(key) != after.get(key):
            changed.append(key)
    return changed


def _is_tracked(sender):
    return f'{sender._meta.app_label}.{sender.__name__}' in TRACKED_MODELS


@receiver(pre_save)
def capture_before_save(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    if not _is_tracked(sender):
        return
    instance._audit_before = None
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._audit_before = _snapshot(old)
        except sender.DoesNotExist:
            instance._audit_before = None


@receiver(post_save)
def record_save(sender, instance, created, **kwargs):
    if kwargs.get('raw'):
        return
    if not _is_tracked(sender) or not _audit_table_ready():
        return
    before = getattr(instance, '_audit_before', None) or {}
    after = _snapshot(instance)
    changed_fields = sorted(after.keys()) if created else _changed_fields(before, after)
    if not changed_fields and not created:
        return
    SignificantDatabaseChange.objects.create(
        actor=get_current_actor(),
        source=get_current_source(),
        app_label=sender._meta.app_label,
        model_name=sender.__name__,
        object_pk=str(instance.pk),
        operation='INSERT' if created else 'UPDATE',
        owner_user_id=_owner_user_id(instance),
        tenant_key=_tenant_key(instance),
        changed_fields=changed_fields,
        before_state=before,
        after_state=after,
    )


@receiver(pre_delete)
def record_delete(sender, instance, **kwargs):
    if not _is_tracked(sender) or not _audit_table_ready():
        return
    before = _snapshot(instance)
    SignificantDatabaseChange.objects.create(
        actor=get_current_actor(),
        source=get_current_source(),
        app_label=sender._meta.app_label,
        model_name=sender.__name__,
        object_pk=str(instance.pk),
        operation='DELETE',
        owner_user_id=_owner_user_id(instance),
        tenant_key=_tenant_key(instance),
        changed_fields=sorted(before.keys()),
        before_state=before,
        after_state={},
    )
