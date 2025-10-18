from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model

# Your other imports
from .models import Contact, ContactUs
from .forms import UserProfileUpdateForm, ContactForm, CustomUserCreationForm
from datetime import timedelta
from django.utils import timezone
import csv
import io

# This try/except block is a good defensive measure
try:
    from messaging.models import MessageCampaign, MessageLog, WhatsAppCredentials
except ImportError:
    class MessageCampaign: objects = None
    class MessageLog: objects = None
    class WhatsAppCredentials: DoesNotExist = Exception; objects = None

User = get_user_model()

# --- Authentication Views (Corrected and Final) ---

def register_view(request):
    """Handles user registration."""
    if request.user.is_authenticated:
        return redirect('accounts:user_dashboard')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully! Welcome.')
            return redirect('accounts:user_dashboard')
        else:
            for field, errors in form.errors.items():
                messages.error(request, f"{field.capitalize()}: {list(errors)[0]}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """Handles user login."""
    if request.user.is_authenticated:
        return redirect('accounts:user_dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")

                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                if user.is_staff or user.is_superuser:
                    return redirect(reverse('admin:index'))
                return redirect('accounts:user_dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    """Logs out the user and redirects to the login page."""
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('accounts:login_view')


# --- Dashboard and Other Views ---
# The rest of your views are correct and do not need changes.

@login_required
def user_dashboard(request):
    user = request.user
    days = int(request.GET.get('days', 7))
    time_threshold = timezone.now() - timedelta(days=days)
    sent_messages, scheduled_messages, total_contacts = 0, 0, 0
    if hasattr(MessageCampaign.objects, 'filter'):
        user_campaign_ids = MessageCampaign.objects.filter(user=user).values_list('id', flat=True)
        sent_messages = MessageLog.objects.filter(campaign_id__in=user_campaign_ids, status='Sent', timestamp__gte=time_threshold).count()
        scheduled_messages = MessageLog.objects.filter(campaign_id__in=user_campaign_ids, status='Scheduled').count()
    total_contacts = Contact.objects.filter(user=user).count()
    whatsapp_connected, whatsapp_status = False, 'DISCONNECTED'
    try:
        if hasattr(user, 'whatsappcredentials'):
            credentials = user.whatsappcredentials
            whatsapp_status = credentials.status
            whatsapp_connected = (whatsapp_status == 'CONNECTED')
    except (WhatsAppCredentials.DoesNotExist, Exception):
        pass
    context = {'sent_messages': sent_messages, 'scheduled_messages': scheduled_messages, 'total_contacts': total_contacts, 'whatsapp_connected': whatsapp_connected, 'whatsapp_status': whatsapp_status, 'days': days}
    return render(request, 'accounts/user_dashboard.html', context)

@login_required
def edit_profile_view(request):
    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:edit_profile')
    else:
        form = UserProfileUpdateForm(instance=request.user)
    return render(request, 'accounts/edit_profile.html', {'form': form})

edit_profile = edit_profile_view

@login_required
def contacts_list_view(request):
    contacts = Contact.objects.filter(user=request.user).order_by('name')
    return render(request, 'accounts/contacts_list.html', {'contacts': contacts})

@login_required
def contacts_add_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.user = request.user
            contact.save()
            messages.success(request, f'Contact "{contact.name}" added successfully.')
            return redirect('accounts:contacts_list')
    else:
        form = ContactForm(user=request.user)
    return render(request, 'accounts/contacts_add.html', {'form': form, 'title': 'Add New Contact'})

@login_required
def contacts_edit_view(request, pk):
    contact = get_object_or_404(Contact, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ContactForm(request.POST, request.FILES, instance=contact, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Contact "{contact.name}" updated successfully.')
            return redirect('accounts:contacts_list')
    else:
        form = ContactForm(instance=contact, user=request.user)
    return render(request, 'accounts/contacts_edit.html', {'form': form, 'title': f'Edit Contact: {contact.name}'})

@login_required
def contacts_delete_view(request, pk):
    contact = get_object_or_404(Contact, pk=pk, user=request.user)
    if request.method == 'POST':
        name = contact.name
        contact.delete()
        messages.success(request, f'Contact "{name}" deleted successfully.')
        return redirect('accounts:contacts_list')
    return render(request, 'accounts/contacts_confirm_delete.html', {'contact': contact})

@login_required
def contacts_export_csv_view(request):
    response = redirect('accounts:contacts_list')
    response['Content-Type'] = 'text/csv'
    response['Content-Disposition'] = 'attachment; filename="contacts_export.csv"'
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Name', 'Phone', 'Created At'])
    contacts = Contact.objects.filter(user=request.user).order_by('name')
    for contact in contacts:
        writer.writerow([contact.name, contact.phone, 'N/A'])
    response.content = buffer.getvalue().encode('utf-8')
    return response

def goodbye_comments_view(request):
    return render(request, 'accounts/goodbye_comments.html')

def help_view(request):
    return render(request, 'accounts/help.html')

def privacy_policy_view(request):
    return render(request, 'accounts/privacy_policy.html')

def contact_us_view(request):
    if request.method == 'POST':
        user = request.user if request.user.is_authenticated else None
        name = request.POST.get('name', '')
        email = request.POST.get('email', '')
        message_content = request.POST.get('message', '')
        if name and email and message_content:
            ContactUs.objects.create(user=user, name=name, email=email, message=message_content)
            messages.success(request, "Your message has been sent successfully! We will get back to you soon.")
            return redirect('accounts:contact_us')
    return render(request, 'accounts/contact_us.html')