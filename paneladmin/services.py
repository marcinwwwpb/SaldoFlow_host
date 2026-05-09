from __future__ import annotations

from .models import AdminAuditLog, FakturaKosztowaArchiwum, OperacjaArchiwum
from .selectors import serialize_faktura, serialize_operacja
from .utils import audit_log


def save_dom_operation(form, actor, *, is_update=False):
    operation = form.save()
    audit_log(
        actor=actor,
        module='DOM',
        entity_type='Operacja',
        entity_id=operation.id,
        action=AdminAuditLog.ACTION_UPDATE if is_update else AdminAuditLog.ACTION_CREATE,
        payload=serialize_operacja(operation),
    )
    return operation


def delete_dom_operation(operation, actor):
    payload = serialize_operacja(operation)
    OperacjaArchiwum.objects.create(source_id=operation.id, deleted_by=actor, data=payload)
    audit_log(
        actor=actor,
        module='DOM',
        entity_type='Operacja',
        entity_id=operation.id,
        action=AdminAuditLog.ACTION_DELETE,
        payload=payload,
    )
    title = operation.tytul
    operation.delete()
    return title


def save_company_cost(form, actor, *, is_update=False):
    invoice = form.save()
    audit_log(
        actor=actor,
        module='FIRMA',
        entity_type='FakturaKosztowa',
        entity_id=invoice.id,
        action=AdminAuditLog.ACTION_UPDATE if is_update else AdminAuditLog.ACTION_CREATE,
        payload=serialize_faktura(invoice),
    )
    return invoice


def delete_company_cost(invoice, actor):
    payload = serialize_faktura(invoice)
    FakturaKosztowaArchiwum.objects.create(source_id=invoice.id, deleted_by=actor, data=payload)
    audit_log(
        actor=actor,
        module='FIRMA',
        entity_type='FakturaKosztowa',
        entity_id=invoice.id,
        action=AdminAuditLog.ACTION_DELETE,
        payload=payload,
    )
    number = invoice.numer_faktury
    invoice.delete()
    return number


def save_user_role(form, actor, *, is_update=False):
    role = form.save()
    audit_log(
        actor=actor,
        module='SYSTEM',
        entity_type='UserRole',
        entity_id=role.id,
        action=AdminAuditLog.ACTION_UPDATE if is_update else AdminAuditLog.ACTION_CREATE,
        payload={'user': role.user.username, 'role': role.role, 'notes': role.notes},
    )
    return role
