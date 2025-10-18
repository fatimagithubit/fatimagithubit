from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # All application-related URLs will be prefixed with 'app/'
    # This is a clean and scalable way to organize your project.
    path('app/', include('messaging.urls', namespace='messaging')),

    # You can add a root redirect to the dashboard or another page later if needed
    # from django.views.generic import RedirectView
    # path('', RedirectView.as_view(url='/app/connect/', permanent=True)),
]

# This is standard for serving media files in a development environment
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)