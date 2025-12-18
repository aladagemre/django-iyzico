"""
URL configuration for ecommerce_site project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Home page
    path('', TemplateView.as_view(template_name='home.html'), name='home'),

    # Shop app (regular Django views)
    path('shop/', include('shop.urls')),

    # API endpoints (Django REST Framework)
    path('api/', include('shop.api_urls')),

    # Iyzico payment gateway URLs (webhooks, 3DS callbacks)
    path('payments/', include('django_iyzico.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin site
admin.site.site_header = "E-commerce Administration"
admin.site.site_title = "E-commerce Admin"
admin.site.index_title = "Welcome to E-commerce Admin"
