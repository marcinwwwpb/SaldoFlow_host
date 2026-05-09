from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.utils import timezone

from accounts.models import EmailVerification
from finanse.models import DemonLog, KontoDomowe, Operacja
from firma.models import FakturaKosztowa, FakturaSprzedazy, ImportDemona, JPKDeklaracja

from .forms import AdminFakturaKosztowaForm, AdminLogFilterForm, AdminOperacjaForm, UserRoleForm
from .models import AdminAuditLog, SignificantDatabaseChange, UserRole
from .utils import read_daemon_statuses


User = get_user_model()


@dataclass(frozen=True)
class UserStatsRow:
    home_accounts_count: int = 0
    operations_count: int = 0
    company_costs_count: int = 0


def serialize_operacja(operacja):
    return {
        'uzytkownik': operacja.uzytkownik_id,
        'konto': operacja.konto_id,
        'tytul': operacja.tytul,
        'kwota': str(operacja.kwota),
        'data': operacja.data.isoformat(),
        'typ_operacji': operacja.typ_operacji_id,
        'kategoria': operacja.kategoria_id,
        'tagi': list(operacja.tagi.values_list('nazwa', flat=True)),
        'opis': operacja.opis,
    }


def serialize_faktura(faktura):
    return {
        'user': faktura.user_id,
        'numer_faktury': faktura.numer_faktury,
        'kontrahent': faktura.kontrahent_id,
        'kontrahent_nazwa': faktura.kontrahent_nazwa,
        'nip_dostawcy': faktura.nip_dostawcy,
        'data_zakupu': faktura.data_zakupu.isoformat(),
        'kwota_netto': str(faktura.kwota_netto),
        'kwota_vat': str(faktura.kwota_vat),
        'kwota_brutto': str(faktura.kwota_brutto),
        'kategoria': faktura.kategoria,
        'rodzaj_zakupu': faktura.rodzaj_zakupu,
        'miesiac_jpk': faktura.miesiac_jpk,
        'opis': faktura.opis,
    }


# --- wspólne selektory -----------------------------------------------------

def build_stats():
    return {
        'users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'staff_users': User.objects.filter(is_staff=True).count(),
        'operacje': Operacja.objects.count(),
        'faktury_kosztowe': FakturaKosztowa.objects.count(),
        'faktury_sprzedazy': FakturaSprzedazy.objects.count(),
        'importy_ok': ImportDemona.objects.filter(status=ImportDemona.STATUS_OK).count(),
        'importy_blad': ImportDemona.objects.filter(status=ImportDemona.STATUS_BLAD).count(),
        'logi': DemonLog.objects.count(),
        'jpk': JPKDeklaracja.objects.count(),
        'audit': AdminAuditLog.objects.count(),
        'db_changes': SignificantDatabaseChange.objects.count(),
        'role': UserRole.objects.count(),
    }


def user_base_queryset():
    return User.objects.annotate(
        email_verified=Exists(
            EmailVerification.objects.filter(
                user_id=OuterRef('pk'),
                verified_at__isnull=False,
            )
        )
    )


def build_role_map():
    return {role.user_id: role for role in UserRole.objects.select_related('user')}


def build_role_counts(role_map):
    role_counts = {code: 0 for code, _ in UserRole.ROLE_CHOICES}
    for role in role_map.values():
        if role and role.role in role_counts:
            role_counts[role.role] += 1
    return role_counts


def build_shortcuts(stats):
    return [
        {
            'title': 'Użytkownicy i dostęp',
            'description': 'Podgląd kont, role, status aktywacji i szybkie przejście do edycji.',
            'url': 'paneladmin_users',
            'meta': f"{stats['users']} kont, {stats['staff_users']} z uprawnieniami pracownika",
        },
        {
            'title': 'Dane operacyjne',
            'description': 'Operacje domowe, koszty firmowe i ręczne korekty rekordów.',
            'url': 'paneladmin_records',
            'meta': f"{stats['operacje']} operacji, {stats['faktury_kosztowe']} kosztów",
        },
        {
            'title': 'Procesy w tle',
            'description': 'Importy, heartbeat demonów i logi błędów.',
            'url': 'paneladmin_demon',
            'meta': f"Importy OK: {stats['importy_ok']}, błędy: {stats['importy_blad']}",
        },
        {
            'title': 'Audyt zmian',
            'description': 'Istotne zmiany danych z porównaniem przed i po zmianie.',
            'url': 'paneladmin_audit',
            'meta': f"Zarejestrowane zmiany: {stats['db_changes']}",
        },
    ]


def base_admin_context():
    stats = build_stats()
    role_map = build_role_map()
    return {
        'stats': stats,
        'role_counts': build_role_counts(role_map),
        'shortcuts': build_shortcuts(stats),
    }


def aggregate_user_stats(user_ids):
    if not user_ids:
        return {}

    account_counts = {
        row['uzytkownik_id']: row['cnt']
        for row in KontoDomowe.objects.filter(uzytkownik_id__in=user_ids).values('uzytkownik_id').annotate(cnt=Count('id'))
    }
    operation_counts = {
        row['uzytkownik_id']: row['cnt']
        for row in Operacja.objects.filter(uzytkownik_id__in=user_ids).values('uzytkownik_id').annotate(cnt=Count('id'))
    }
    cost_counts = {
        row['user_id']: row['cnt']
        for row in FakturaKosztowa.objects.filter(user_id__in=user_ids).values('user_id').annotate(cnt=Count('id'))
    }
    return {
        user_id: UserStatsRow(
            home_accounts_count=account_counts.get(user_id, 0),
            operations_count=operation_counts.get(user_id, 0),
            company_costs_count=cost_counts.get(user_id, 0),
        )
        for user_id in user_ids
    }


def attach_user_stats(users, role_map):
    users = list(users)
    stats_map = aggregate_user_stats([user.id for user in users])
    rows = []
    for user in users:
        user_stats = stats_map.get(user.id, UserStatsRow())
        user.home_accounts_count = user_stats.home_accounts_count
        user.operations_count = user_stats.operations_count
        user.company_costs_count = user_stats.company_costs_count
        rows.append({'user': user, 'role': role_map.get(user.id)})
    return rows


def resolve_selected_user(request, *, param_name='selected_user'):
    selected_user = None
    selected_user_id = request.GET.get(param_name) or request.POST.get(param_name)
    if selected_user_id:
        selected_user = User.objects.filter(pk=selected_user_id).first()
    return selected_user


# --- dashboard -------------------------------------------------------------

def dashboard_context(request):
    context = base_admin_context()
    role_map = build_role_map()
    user_queryset = user_base_queryset()

    recent_users = user_queryset.order_by('-last_login', '-date_joined')[:10]
    flagged_users = user_queryset.filter(
        Q(is_active=False) | Q(last_login__isnull=True) | Q(email_verified=False)
    ).order_by('is_active', 'email_verified', 'date_joined')[:8]

    context.update(
        {
            'ostatnie_importy': ImportDemona.objects.select_related('user').order_by('-created_at')[:10],
            'ostatnie_operacje': Operacja.objects.select_related('uzytkownik', 'konto', 'typ_operacji', 'kategoria').order_by('-id')[:8],
            'ostatnie_koszty': FakturaKosztowa.objects.select_related('user', 'kontrahent').order_by('-id')[:8],
            'ostatnie_audyty': AdminAuditLog.objects.select_related('actor').order_by('-created_at')[:10],
            'user_rows': attach_user_stats(recent_users, role_map),
            'flagged_user_rows': attach_user_stats(flagged_users, role_map),
            'system_health': {
                'home_balance_sum': Operacja.objects.aggregate(suma=Sum('kwota'))['suma'] or Decimal('0.00'),
                'company_costs_sum': FakturaKosztowa.objects.aggregate(suma=Sum('kwota_brutto'))['suma'] or Decimal('0.00'),
                'company_sales_sum': FakturaSprzedazy.objects.aggregate(suma=Sum('kwota_brutto'))['suma'] or Decimal('0.00'),
                'verified_emails': EmailVerification.objects.filter(verified_at__isnull=False).values('user_id').distinct().count(),
                'never_logged_in': User.objects.filter(last_login__isnull=True).count(),
                'inactive_users': User.objects.filter(is_active=False).count(),
                'unverified_users': user_base_queryset().filter(email_verified=False).count(),
            },
        }
    )
    return context


# --- users -----------------------------------------------------------------

def users_context(request, *, role_instance=None):
    context = base_admin_context()
    role_map = build_role_map()

    user_query = (request.GET.get('q') or '').strip()
    user_status = (request.GET.get('status') or 'all').strip()
    user_role_filter = (request.GET.get('role') or 'all').strip()
    page_number = request.GET.get('page') or 1

    filtered_queryset = user_base_queryset().order_by('-date_joined', 'username')
    if user_query:
        filtered_queryset = filtered_queryset.filter(
            Q(username__icontains=user_query)
            | Q(email__icontains=user_query)
            | Q(first_name__icontains=user_query)
            | Q(last_name__icontains=user_query)
        )
    if user_status == 'active':
        filtered_queryset = filtered_queryset.filter(is_active=True)
    elif user_status == 'inactive':
        filtered_queryset = filtered_queryset.filter(is_active=False)
    elif user_status == 'staff':
        filtered_queryset = filtered_queryset.filter(is_staff=True)
    elif user_status == 'unverified':
        filtered_queryset = filtered_queryset.filter(email_verified=False)
    elif user_status == 'new':
        filtered_queryset = filtered_queryset.filter(last_login__isnull=True)

    if user_role_filter != 'all':
        matching_user_ids = [user_id for user_id, role in role_map.items() if role and role.role == user_role_filter]
        filtered_queryset = filtered_queryset.filter(pk__in=matching_user_ids)

    paginator = Paginator(filtered_queryset, 25)
    page_obj = paginator.get_page(page_number)
    all_user_rows = attach_user_stats(page_obj.object_list, role_map)

    context.update(
        {
            'role_form': UserRoleForm(instance=role_instance),
            'role_edit_instance': role_instance,
            'all_user_rows': all_user_rows,
            'page_obj': page_obj,
            'user_filters': {
                'q': user_query,
                'status': user_status,
                'role': user_role_filter,
            },
            'system_health': {
                'inactive_users': User.objects.filter(is_active=False).count(),
                'never_logged_in': User.objects.filter(last_login__isnull=True).count(),
                'unverified_users': user_base_queryset().filter(email_verified=False).count(),
            },
        }
    )
    return context


# --- records ---------------------------------------------------------------

def records_context(request, *, dom_instance=None, firma_instance=None, dom_form=None, firma_form=None):
    context = base_admin_context()
    selected_user = dom_instance.uzytkownik if dom_instance else (firma_instance.user if firma_instance else resolve_selected_user(request))
    if selected_user is None and dom_form is not None and getattr(dom_form, 'is_bound', False):
        selected_user = User.objects.filter(pk=dom_form.data.get('uzytkownik')).first()
    if selected_user is None and firma_form is not None and getattr(firma_form, 'is_bound', False):
        selected_user = User.objects.filter(pk=firma_form.data.get('user')).first()
    active_users = User.objects.filter(is_active=True).order_by('username')

    if dom_form is None:
        dom_form = AdminOperacjaForm(instance=dom_instance, target_user=selected_user, user_queryset=active_users)
    if firma_form is None:
        firma_form = AdminFakturaKosztowaForm(instance=firma_instance, target_user=selected_user, user_queryset=active_users)

    operations = Operacja.objects.select_related('uzytkownik', 'konto', 'typ_operacji', 'kategoria').order_by('-id')
    invoices = FakturaKosztowa.objects.select_related('user', 'kontrahent').order_by('-id')
    if selected_user:
        operations = operations.filter(uzytkownik=selected_user)
        invoices = invoices.filter(user=selected_user)

    context.update(
        {
            'dom_form': dom_form,
            'firma_form': firma_form,
            'dom_edit_instance': dom_instance,
            'firma_edit_instance': firma_instance,
            'selected_user': selected_user,
            'record_user_options': active_users,
            'record_filters': {'selected_user': selected_user.id if selected_user else ''},
            'ostatnie_operacje': operations[:12],
            'ostatnie_koszty': invoices[:12],
        }
    )
    return context


# --- daemon ----------------------------------------------------------------

def daemon_context(request):
    context = base_admin_context()
    log_form = AdminLogFilterForm(request.GET or None)
    logs_queryset = DemonLog.objects.order_by('-utworzono_o')
    if log_form.is_valid():
        data = log_form.cleaned_data
        if data.get('modul'):
            logs_queryset = logs_queryset.filter(modul=data['modul'])
        if data.get('poziom'):
            logs_queryset = logs_queryset.filter(poziom=data['poziom'])
        if data.get('q'):
            logs_queryset = logs_queryset.filter(
                Q(wiadomosc__icontains=data['q'])
                | Q(nazwa_pliku__icontains=data['q'])
                | Q(sciezka__icontains=data['q'])
            )
        if data.get('date_from'):
            logs_queryset = logs_queryset.filter(utworzono_o__date__gte=data['date_from'])
        if data.get('date_to'):
            logs_queryset = logs_queryset.filter(utworzono_o__date__lte=data['date_to'])

    daemon_statuses = []
    for status in read_daemon_statuses():
        last_seen = None
        if status.get('last_seen'):
            try:
                last_seen = timezone.datetime.fromisoformat(status['last_seen'])
                if timezone.is_naive(last_seen):
                    last_seen = timezone.make_aware(last_seen)
            except Exception:
                last_seen = None
        is_fresh = bool(last_seen and (timezone.now() - last_seen).total_seconds() <= (int(status.get('sleep_seconds') or 300) * 2 + 60))
        status['is_fresh'] = is_fresh and bool(status.get('running', True))
        daemon_statuses.append(status)

    context.update(
        {
            'daemon_statuses': daemon_statuses,
            'ostatnie_logi': logs_queryset[:50],
            'ostatnie_importy': ImportDemona.objects.select_related('user').order_by('-created_at')[:10],
            'log_form': log_form,
        }
    )
    return context


# --- audit -----------------------------------------------------------------

def audit_context(request):
    context = base_admin_context()
    context.update(
        {
            'db_changes': SignificantDatabaseChange.objects.select_related('actor').order_by('-changed_at')[:120],
        }
    )
    return context
