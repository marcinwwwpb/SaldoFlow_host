from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from core.views import landing_page, module_selector

admin.site.site_header = f"{settings.APP_NAME} — Django admin"
admin.site.site_title = settings.APP_NAME
admin.site.index_title = "Administracja systemu"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing_page, name='home'),
    path('moduly/', module_selector, name='module_selector'),
    path('konto/', include('accounts.urls')),
    path('panel-admina/', include('paneladmin.urls')),
    path('dom/', include('finanse.urls')),
    path('firma/', include('firma.urls')),
]
