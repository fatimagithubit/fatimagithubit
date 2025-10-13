import csv
from io import TextIOWrapper
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Template, Contact, Message
from .forms import CustomUserCreationForm

class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login')
    template_name = 'registration/signup.html'

class TemplateListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Template
    template_name = 'messaging/template_list.html'

    def test_func(self):
        return self.request.user.user_type == 'admin'

class MessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'messaging/message_list.html'

    def get_queryset(self):
        if self.request.user.user_type == 'admin':
            return Message.objects.all()
        return Message.objects.filter(user=self.request.user)

class BulkMessageView(LoginRequiredMixin, FormView):
    template_name = 'messaging/bulk_message_form.html'
    form_class = None  # We will create this form next
    success_url = reverse_lazy('bulk_message')

    def get_form_class(self):
        from .forms import BulkMessageForm
        return BulkMessageForm

    def form_valid(self, form):
        from .tasks import send_scheduled_message
        message_body = form.cleaned_data['message_body']
        contacts_manual = form.cleaned_data['contacts_manual']
        csv_file = form.cleaned_data['csv_file']
        scheduled_at = form.cleaned_data['scheduled_at']

        contacts = []
        if contacts_manual:
            for line in contacts_manual.splitlines():
                parts = line.split(',')
                if len(parts) == 2:
                    name, phone_number = parts
                    contacts.append({'name': name.strip(), 'phone_number': phone_number.strip()})

        if csv_file:
            csv_file.seek(0)
            reader = csv.reader(TextIOWrapper(csv_file, encoding='utf-8'))
            for row in reader:
                if len(row) == 2:
                    name, phone_number = row
                    contacts.append({'name': name.strip(), 'phone_number': phone_number.strip()})

        unique_contacts = {c['phone_number']: c for c in contacts}.values()

        for contact_data in unique_contacts:
            contact, created = Contact.objects.get_or_create(
                phone_number=contact_data['phone_number'],
                defaults={'name': contact_data['name'], 'user': self.request.user}
            )
            message = Message.objects.create(
                user=self.request.user,
                contact=contact,
                message_body=message_body,
                scheduled_at=scheduled_at,
                status='scheduled' if scheduled_at else 'sent'
            )
            if scheduled_at:
                send_scheduled_message.apply_async((message.id,), eta=scheduled_at)

        return super().form_valid(form)

class TemplateCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Template
    fields = ['name', 'body']
    template_name = 'messaging/template_form.html'
    success_url = reverse_lazy('template_list')

    def test_func(self):
        return self.request.user.user_type == 'admin'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

class TemplateUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Template
    fields = ['name', 'body']
    template_name = 'messaging/template_form.html'
    success_url = reverse_lazy('template_list')

    def test_func(self):
        return self.request.user.user_type == 'admin'

class TemplateDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Template
    template_name = 'messaging/template_confirm_delete.html'
    success_url = reverse_lazy('template_list')

    def test_func(self):
        return self.request.user.user_type == 'admin'