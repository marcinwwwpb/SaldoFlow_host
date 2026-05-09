from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from finanse.models import Operacja
from firma.models import FakturaKosztowa
from .forms import AdminFakturaKosztowaForm, AdminOperacjaForm, UserRoleForm
from .models import AdminAuditLog, UserRole
from .permissions import admin_panel_required, admin_write_required, can_manage_admin_panel
from .selectors import audit_context, daemon_context, dashboard_context, records_context, users_context
from .services import delete_company_cost, delete_dom_operation, save_company_cost, save_dom_operation, save_user_role
from .utils import audit_log, control_daemon


class PanelAdminLoginView(LoginView):
    template_name = 'paneladmin/login.html'
    redirect_authenticated_user = True

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['username'].widget.attrs.setdefault('class', 'form-control')
        form.fields['password'].widget.attrs.setdefault('class', 'form-control')
        form.fields['username'].label = 'E-mail lub login'
        form.fields['username'].widget.attrs.setdefault('placeholder', 'E-mail lub login')
        form.fields['password'].widget.attrs.setdefault('placeholder', 'Hasło')
        return form

    def get_success_url(self):
        return self.get_redirect_url() or reverse('paneladmin_dashboard')


class PanelAdminLogoutView(LogoutView):
    next_page = 'paneladmin_dashboard'


@admin_panel_required
def dashboard(request):
    return render(request, 'paneladmin/dashboard.html', dashboard_context(request))


@admin_panel_required
def users_view(request):
    role_instance = UserRole.objects.filter(pk=request.GET.get('edit_role')).first() if request.GET.get('edit_role') else None
    context = users_context(request, role_instance=role_instance)
    context['can_manage_admin_panel'] = can_manage_admin_panel(request.user)
    return render(request, 'paneladmin/users.html', context)


@admin_panel_required
def records_view(request):
    dom_instance = Operacja.objects.filter(pk=request.GET.get('edit_dom')).first() if request.GET.get('edit_dom') else None
    firma_instance = FakturaKosztowa.objects.filter(pk=request.GET.get('edit_firma')).first() if request.GET.get('edit_firma') else None
    context = records_context(request, dom_instance=dom_instance, firma_instance=firma_instance)
    context['can_manage_admin_panel'] = can_manage_admin_panel(request.user)
    return render(request, 'paneladmin/records.html', context)


@admin_panel_required
def audit_view(request):
    return render(request, 'paneladmin/audit.html', audit_context(request))


@admin_panel_required
def daemon_view(request):
    context = daemon_context(request)
    context['can_manage_admin_panel'] = can_manage_admin_panel(request.user)
    return render(request, 'paneladmin/daemon.html', context)


@admin_write_required
@require_POST
def daemon_action(request, module, action):
    try:
        result = control_daemon(module, action)
    except KeyError:
        messages.error(request, 'Nieznany demon.')
        return redirect('paneladmin_demon')
    except ValueError:
        messages.error(request, 'Nieznana akcja dla demona.')
        return redirect('paneladmin_demon')

    audit_log(
        actor=request.user,
        module='SYSTEM',
        entity_type='Daemon',
        entity_id=None,
        action=AdminAuditLog.ACTION_UPDATE,
        payload={
            'daemon': module,
            'action': action,
            'service_name': result.get('service_name'),
            'system_ok': result.get('system_ok'),
            'message': result.get('message'),
        },
    )

    labels = {'enable': 'włączony', 'disable': 'wyłączony', 'reset': 'zresetowany'}
    if result.get('system_ok'):
        messages.success(request, f"Demon {module.upper()} został {labels[action]}.")
    else:
        messages.warning(
            request,
            f"Zapisano polecenie dla demona {module.upper()}, ale usługa systemowa nie potwierdziła wykonania: {result.get('message')}",
        )
    return redirect('paneladmin_demon')


@admin_write_required
def zapisz_operacje_dom(request):
    if request.method != 'POST':
        return redirect('paneladmin_records')
    instance = Operacja.objects.filter(pk=request.POST.get('operacja_id')).first() if request.POST.get('operacja_id') else None
    form = AdminOperacjaForm(request.POST, instance=instance)
    if form.is_valid():
        operation = save_dom_operation(form, request.user, is_update=bool(instance))
        messages.success(request, f"{'Zaktualizowano' if instance else 'Dodano'} pozycję budżetu domowego: {operation.tytul}.")
        return redirect('paneladmin_records')
    messages.error(request, 'Nie udało się zapisać pozycji budżetu domowego.')
    context = records_context(request, dom_instance=instance, dom_form=form)
    context['can_manage_admin_panel'] = can_manage_admin_panel(request.user)
    return render(request, 'paneladmin/records.html', context)


@admin_write_required
def usun_operacje_dom(request, pk):
    operation = get_object_or_404(Operacja, pk=pk)
    title = delete_dom_operation(operation, request.user)
    messages.success(request, f'Usunięto operację: {title}. Rekord trafił do archiwum.')
    return redirect('paneladmin_records')


@admin_write_required
def zapisz_pozycje_firmowa(request):
    if request.method != 'POST':
        return redirect('paneladmin_records')
    instance = FakturaKosztowa.objects.filter(pk=request.POST.get('faktura_id')).first() if request.POST.get('faktura_id') else None
    form = AdminFakturaKosztowaForm(request.POST, instance=instance)
    if form.is_valid():
        invoice = save_company_cost(form, request.user, is_update=bool(instance))
        messages.success(request, f"{'Zaktualizowano' if instance else 'Dodano'} pozycję budżetu firmowego: {invoice.numer_faktury}.")
        return redirect('paneladmin_records')
    messages.error(request, 'Nie udało się zapisać pozycji budżetu firmowego.')
    context = records_context(request, firma_instance=instance, firma_form=form)
    context['can_manage_admin_panel'] = can_manage_admin_panel(request.user)
    return render(request, 'paneladmin/records.html', context)


@admin_write_required
def usun_pozycje_firmowa(request, pk):
    invoice = get_object_or_404(FakturaKosztowa, pk=pk)
    number = delete_company_cost(invoice, request.user)
    messages.success(request, f'Usunięto koszt firmowy: {number}. Rekord trafił do archiwum.')
    return redirect('paneladmin_records')


@admin_write_required
def zapisz_role(request):
    if request.method != 'POST':
        return redirect('paneladmin_users')
    instance = None
    if request.POST.get('role_id'):
        instance = UserRole.objects.filter(pk=request.POST.get('role_id')).first()
    elif request.POST.get('user'):
        instance = UserRole.objects.filter(user_id=request.POST.get('user')).first()
    form = UserRoleForm(request.POST, instance=instance)
    if form.is_valid():
        role = save_user_role(form, request.user, is_update=bool(instance))
        messages.success(request, f'Zapisano rolę dla użytkownika {role.user}.')
        return redirect('paneladmin_users')
    messages.error(request, 'Nie udało się zapisać roli użytkownika.')
    context = users_context(request, role_instance=instance) | {'role_form': form}
    context['can_manage_admin_panel'] = can_manage_admin_panel(request.user)
    return render(request, 'paneladmin/users.html', context)
