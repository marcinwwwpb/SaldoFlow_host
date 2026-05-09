from django.conf import settings
from django.db import connection

from .current_actor import reset_current_actor, set_current_actor


class CurrentActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
        token_user, token_source = set_current_actor(user, 'django-request')
        self._set_oracle_security_context(user)
        try:
            response = self.get_response(request)
        finally:
            reset_current_actor(token_user, token_source)
        return response

    def _set_oracle_security_context(self, user):
        if getattr(settings, 'DB_ENGINE', '').lower() not in {'oracle', 'ora'}:
            return
        user_id = str(user.id) if user else '0'
        role_code = getattr(getattr(user, 'panel_role', None), 'role', 'ANON') if user else 'ANON'
        try:
            with connection.cursor() as cursor:
                cursor.execute("BEGIN SF_SECURITY_PKG.SET_CONTEXT(:user_id, :role_code); END;", {
                    'user_id': user_id,
                    'role_code': role_code,
                })
        except Exception:
            return
