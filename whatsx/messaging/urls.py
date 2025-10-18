from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # --- Main User-Facing Pages ---
    path('connect/', views.whatsapp_connect_view, name='whatsapp_connect'),
    path('templates/', views.template_list_view, name='template_list'),
    path('campaigns/', views.campaign_list_view, name='campaign_list'),
    path('campaigns/create/', views.campaign_create_view, name='campaign_create'),

    # --- Internal API Endpoints for the Connection Page ---
    path('api/whatsapp/start/', views.start_session_api, name='whatsapp_start_api'),
    path('api/whatsapp/status/', views.status_api, name='whatsapp_status_api'),
    path('api/whatsapp/disconnect/', views.disconnect_api, name='whatsapp_disconnect_api'),
]