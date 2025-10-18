from django.urls import path
from . import views_ui

app_name = 'accounts'

urlpatterns = [
    path('login/', views_ui.login_view, name='login_view'),
    path('register/', views_ui.register_view, name='register_view'),
    path('logout/', views_ui.logout_view, name='logout_view'),
    path('dashboard/', views_ui.user_dashboard, name='user_dashboard'),
    path('contacts/', views_ui.contacts_list_view, name='contacts_list'),
]