from django.conf import settings

from paneladmin.permissions import can_access_admin_panel, can_manage_admin_panel, can_manage_finance_data, can_view_audit, get_role_code, is_read_only_role


def _navbar_section(request):
    match = getattr(request, 'resolver_match', None)
    if not match:
        return ''
    namespace = match.namespace or ''
    url_name = match.url_name or ''
    path = request.path or ''

    if path == '/':
        return ''
    if path.startswith('/panel-admina') or path.startswith('/admin') or namespace == 'paneladmin':
        return 'Admin'
    if path.startswith('/firma') or namespace == 'firma':
        return 'Budżet firmowy'
    if path.startswith('/dom') or namespace == 'finanse':
        return 'Budżet domowy'
    if url_name == 'module_selector':
        return settings.APP_NAME
    return ''


def app_shell(request):
    user = getattr(request, 'user', None)
    return {
        'APP_NAME': settings.APP_NAME,
        'APP_TAGLINE': settings.APP_TAGLINE,
        'APP_MARKETING_LINE': settings.APP_MARKETING_LINE,
        'NAVBAR_SECTION': _navbar_section(request),
        'CEIDG_ENABLED': bool(getattr(settings, 'CEIDG_AUTH_TOKEN', '')) or getattr(settings, 'CEIDG_DEMO_MODE', False),
        'CEIDG_DEMO_MODE': getattr(settings, 'CEIDG_DEMO_MODE', False),
        'USER_ROLE_CODE': get_role_code(user),
        'USER_CAN_ACCESS_ADMIN_PANEL': can_access_admin_panel(user),
        'USER_CAN_MANAGE_ADMIN_PANEL': can_manage_admin_panel(user),
        'USER_CAN_MANAGE_FINANCE_DATA': can_manage_finance_data(user),
        'USER_CAN_VIEW_AUDIT': can_view_audit(user),
        'USER_IS_READ_ONLY': is_read_only_role(user),
    }
