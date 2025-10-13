from django.urls import path
from .views import (
    SignUpView,
    TemplateListView,
    TemplateCreateView,
    TemplateUpdateView,
    TemplateDeleteView,
    BulkMessageView,
    MessageListView,
)

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('templates/', TemplateListView.as_view(), name='template_list'),
    path('templates/create/', TemplateCreateView.as_view(), name='template_create'),
    path('templates/<int:pk>/update/', TemplateUpdateView.as_view(), name='template_update'),
    path('templates/<int:pk>/delete/', TemplateDeleteView.as_view(), name='template_delete'),
    path('bulk-message/', BulkMessageView.as_view(), name='bulk_message'),
    path('messages/', MessageListView.as_view(), name='message_list'),
]