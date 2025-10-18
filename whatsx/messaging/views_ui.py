import csv
import io
import json
import logging
import re
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse

# Forms aur Models jise humne banaya hai
from .forms import CampaignForm, WhatsAppCredentialsForm
# FIX: 'Recipient' ki jagah 'CampaignRecipient' ka upyog
from .models import MessageCampaign, MessageTemplate, WhatsAppCredentials, CampaignRecipient
# accounts app se Contact model
from accounts.models import Contact
@login_required
def template_list_view(request):
    # Logic to fetch and display message templates
    # templates = MessageCampaign.objects.filter(user=request.user)
    context = {} # Pass necessary data to the template
    return render(request, 'messaging/template_list.html', context)
from celery import shared_task
import requests

# This should be in your settings.py, but is here for clarity.
NODE_SEND_API_URL = "http://127.0.0.1:3001/api/v1/whatsapp/send"

@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_campaign_task(self, campaign_pk):
    """
    This is the main Celery task that processes a message campaign.
    It iterates through all pending recipients and calls the Node.js service to send the message.
    """
    try:
        campaign = MessageCampaign.objects.get(pk=campaign_pk)
    except MessageCampaign.DoesNotExist:
        logger.error(f"Campaign with PK {campaign_pk} not found. Task cannot proceed.")
        return

    # Mark as in progress if it was pending
    if campaign.status == 'PENDING':
        campaign.status = 'IN_PROGRESS'
        campaign.started_at = timezone.now()
        campaign.save(update_fields=['status', 'started_at'])

    pending_recipients = campaign.recipients.filter(status='PENDING')
    logger.info(f"Starting task for campaign '{campaign.name}'. Processing {pending_recipients.count()} recipients.")

    for recipient in pending_recipients:
        try:
            payload = {'number': recipient.phone_number, 'message': campaign.message_content}
            headers = {'Content-Type': 'application/json'}

            response = requests.post(NODE_SEND_API_URL, data=json.dumps(payload), headers=headers, timeout=30)

            if response.status_code == 200:
                recipient.status = 'SENT'
                recipient.sent_at = timezone.now()
                recipient.error_message = None
            else:
                recipient.status = 'FAILED'
                error_info = response.json().get('message', 'No error message from service.')
                recipient.error_message = f"API Error (HTTP {response.status_code}): {error_info}"

        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error sending to {recipient.phone_number} for campaign {campaign_pk}. Retrying task. Error: {e}")
            # Retry the entire task if the Node service is down.
            raise self.retry(exc=e)

        finally:
            recipient.save()

    # Check if the campaign is complete
    if not campaign.recipients.filter(status='PENDING').exists():
        campaign.status = 'COMPLETED'
        campaign.completed_at = timezone.now()
        campaign.save(update_fields=['status', 'completed_at'])
        logger.info(f"Campaign '{campaign.name}' has been completed.")

    return f"Processed recipients for campaign {campaign_pk}."

logger = logging.getLogger(__name__)

# Utility function for phone number validation and normalization
def normalize_and_validate_phone(number):
    """Normalize phone number to E.164 format (+92XXXXXXXXXX) and check validity."""

    # 1. Remove all non-digit characters except leading +
    cleaned = re.sub(r'[^\d+]', '', number)

    # 2. Ensure leading '+' exists
    if not cleaned.startswith('+'):
        # Assuming Pakistani context, add +92 if number looks like 3001234567 or 03001234567
        if cleaned.startswith('0'):
            cleaned = cleaned[1:] # Remove leading 0

        if cleaned.startswith('92'):
            cleaned = '+' + cleaned
        elif len(cleaned) == 10: # e.g., 3001234567
            cleaned = '+92' + cleaned
        else:
            # If still not starting with '+', it's likely an invalid international number
            return None

    # 3. Final E.164 check (simple length check: 12-15 digits usually)
    # +923001234567 -> 13 chars
    if len(cleaned) < 11 or len(cleaned) > 16:
        return None

    return cleaned

# =========================================================================
# I. WHATSAPP CONNECTION VIEWS (UI & API) - Revised
# =========================================================================

@login_required
def whatsapp_connect_view(request):
    """Handles configuration and displays connection status/QR."""

    try:
        credentials = WhatsAppCredentials.objects.get(user=request.user)
    except WhatsAppCredentials.DoesNotExist:
        credentials = None

    if request.method == 'POST':
        form = WhatsAppCredentialsForm(request.POST, instance=credentials)
        if form.is_valid():
            new_credentials = form.save(commit=False)
            new_credentials.user = request.user
            new_credentials.status = 'DISCONNECTED' # Force re-login/QR process
            new_credentials.save()
            messages.success(request, "WhatsApp credentials saved. Please check the status below to connect.")
            return redirect(reverse('messaging:whatsapp_connect'))
        else:
            messages.error(request, "Error saving credentials. Please check the form data.")
    else:
        form = WhatsAppCredentialsForm(instance=credentials)

    context = {
        'form': form,
        'credentials': credentials,
    }
    return render(request, 'messaging/whatsapp_connect.html', context)


@login_required
@require_http_methods(["GET"])
def whatsapp_status_api(request):
    """API endpoint to get the current WhatsApp connection status."""
    try:
        credentials = WhatsAppCredentials.objects.get(user=request.user)

        status_data = {
            'status': credentials.status,
            'status_display': credentials.get_status_display(),
            'phone_number': credentials.whatsapp_phone_number,
            # Yahan asal mein aapki external API se QR URL aayega
            'qr_code_url': credentials.qr_code_url or None,
        }

        # Agar koi QR URL nahi hai toh ek placeholder URL de dein agar zaruri ho
        if status_data['status'] != 'CONNECTED' and not status_data['qr_code_url']:
             status_data['qr_code_url'] = f"https://placehold.co/200x200/F0F0F0/000?text=Awaiting+QR"

        return JsonResponse(status_data)

    except WhatsAppCredentials.DoesNotExist:
        return JsonResponse({
            'status': 'NOT_CONFIGURED',
            'status_display': 'Not Configured',
            'phone_number': None,
            'qr_code_url': None,
        }, status=404)

# =========================================================================
# II. MESSAGE TEMPLATE VIEWS
# =========================================================================

@login_required
def template_list_view(request):
    """Displays a list of all available message templates."""
    # Filter templates to include user's own and Admin/Superuser templates
    templates = MessageTemplate.objects.filter(
        models.Q(created_by=request.user) | models.Q(created_by__is_superuser=True)
    ).distinct().order_by('title')

    context = {'templates': templates}
    return render(request, 'messaging/template_list.html', context)


# =========================================================================
# III. MESSAGE CAMPAIGN VIEWS (CRUD UI)
# =========================================================================

@login_required
def campaign_list_view(request):
    """Displays a list of the user's message campaigns."""
    campaigns = MessageCampaign.objects.filter(created_by=request.user).order_by('-created_at')
    context = {'campaigns': campaigns}
    return render(request, 'messaging/campaign_list.html', context)


@login_required
@transaction.atomic
def campaign_create_view(request):
    """Handles creating a new campaign."""

    templates = MessageTemplate.objects.filter(
        models.Q(created_by=request.user) | models.Q(created_by__is_superuser=True)
    ).distinct().order_by('title')
    contacts = Contact.objects.filter(user=request.user)
    # Template content ko JS mein load karne ke liye
    templates_json = json.dumps(list(templates.values('id', 'content')))

    if request.method == 'POST':
        form = CampaignForm(request.user, request.POST, request.FILES)

        if form.is_valid():
            try:
                # 1. Campaign object ko save karein
                campaign = form.save(commit=False)
                campaign.created_by = request.user

                # Agar template select hua hai, lekin content nahi dala, toh template content use karein
                if campaign.message_template and not campaign.message_content:
                    campaign.message_content = campaign.message_template.content

                # 2. Recipients ko process karein aur save karein
                recipients_data_set = process_recipients_data(request)
                total_recipients = len(recipients_data_set)

                if total_recipients == 0:
                    messages.error(request, "No valid recipients were found from the selected sources.")
                    # Fallback to re-render form if no recipients
                    raise ValueError("No recipients")

                campaign.total_recipients = total_recipients

                # 3. Scheduled time aur initial status set karein
                scheduled_time = campaign.scheduled_time
                is_scheduled = bool(scheduled_time) and scheduled_time > timezone.now()

                if is_scheduled:
                    campaign.status = 'PENDING'
                else:
                    campaign.status = 'IN_PROGRESS' # Immediate start
                    campaign.started_at = timezone.now()
                    campaign.scheduled_time = None # Clear scheduled time if starting immediately

                campaign.save()

                # 4. CampaignRecipient objects bulk create karein
                recipient_objects = []
                for phone, name in recipients_data_set:
                    # FIX: Correctly using CampaignRecipient model
                    recipient_objects.append(CampaignRecipient(
                        campaign=campaign,
                        name=name,
                        phone_number=phone,
                        status='PENDING',
                    ))

                CampaignRecipient.objects.bulk_create(recipient_objects, ignore_conflicts=True)


                # 5. Task Scheduling
                if campaign.status == 'PENDING':
                    # Task ko future mein run karne ke liye schedule karein
                    send_campaign_task.apply_async(
                        args=[campaign.pk],
                        eta=scheduled_time
                    )
                    messages.success(request, f"Campaign '{campaign.name}' scheduled successfully for {scheduled_time.strftime('%Y-%m-%d %H:%M')}.")
                elif campaign.status == 'IN_PROGRESS':
                    # Task ko turant run karein
                    send_campaign_task.delay(campaign.pk)
                    messages.success(request, f"Campaign '{campaign.name}' started immediately. Check Campaign Status for progress.")

                return redirect(reverse('messaging:campaign_list'))

            except ValueError as ve:
                 # Recipient error ki wajah se re-render
                messages.error(request, f"Campaign could not be created: {ve}")
            except Exception as e:
                messages.error(request, f"An unexpected error occurred during campaign creation: {e}")
                logger.error(f"Campaign creation failed: {e}")

        # Agar form invalid hai ya exception aayi hai toh form ko errors ke saath render karein
        return render(request, 'messaging/campaign_form.html', {
            'form': form,
            'templates': templates,
            'contacts': contacts,
            'templates_json': templates_json,
            'page_title': 'Create New Campaign',
            'is_edit': False,
        })

    else:
        form = CampaignForm(request.user)
        return render(request, 'messaging/campaign_form.html', {
            'form': form,
            'templates': templates,
            'contacts': contacts,
            'templates_json': templates_json,
            'page_title': 'Create New Campaign',
            'is_edit': False,
        })

# =========================================================================
# IV. RECIPIENT PROCESSING LOGIC (UTILITY)
# =========================================================================

def process_recipients_data(request):
    """Processes selected contacts, manual numbers, and CSV file to create a set of (phone_number, name) tuples."""

    # Ek set rakhein taki duplicate numbers na aayein: (phone_number, name)
    recipient_data = set()

    # 1. Selected Contacts (from CheckboxSelectMultiple)
    selected_contact_ids = request.POST.getlist('selected_contacts')
    if selected_contact_ids:
        # User ke contacts ko filter karein
        contacts = Contact.objects.filter(user=request.user, id__in=selected_contact_ids)
        for contact in contacts:
            phone = normalize_and_validate_phone(contact.phone_number)
            if phone:
                # (phone_number, name) tuple set mein daal dein
                recipient_data.add((phone, contact.name or 'Database Contact'))

    # 2. Manual Numbers (from Textarea)
    manual_numbers = request.POST.get('manual_numbers', '')
    if manual_numbers:
        for line in manual_numbers.splitlines():
            line_stripped = line.strip()
            phone = normalize_and_validate_phone(line_stripped)
            if phone:
                # Name ko phone number ka last part ya generic rakh dein
                name = line_stripped.split()[-1] if line_stripped.split()[-1] != phone else 'Manual Contact'
                recipient_data.add((phone, name))
            else:
                logger.warning(f"Invalid manual number skipped: {line.strip()}")

    # 3. CSV File Upload
    csv_file = request.FILES.get('csv_file')
    if csv_file:
        try:
            # File ko read karein (utf-8 encoding assume kiya gaya hai)
            csv_data = csv_file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(csv_data))

            # Case-insensitive column name handling
            fieldnames = [f.lower().replace('_', '').replace(' ', '') for f in reader.fieldnames]

            phone_col = None
            name_col = None

            if 'phonenumber' in fieldnames:
                 phone_col = reader.fieldnames[fieldnames.index('phonenumber')]
            elif 'phone' in fieldnames:
                 phone_col = reader.fieldnames[fieldnames.index('phone')]

            if 'name' in fieldnames:
                name_col = reader.fieldnames[fieldnames.index('name')]

            if phone_col:
                for row in reader:
                    name = row.get(name_col, 'CSV Contact').strip()
                    phone_number_input = row.get(phone_col, '').strip()
                    phone = normalize_and_validate_phone(phone_number_input)

                    if phone:
                        recipient_data.add((phone, name))
                    else:
                        logger.warning(f"Invalid CSV number skipped: {phone_number_input}")
            else:
                 messages.error(request, "CSV file must contain a 'Phone' or 'Phone Number' column.")

        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            messages.error(request, "Error processing CSV file. Please check format.")


    return recipient_data # Total unique recipients ka set return karein


# =========================================================================
# V. CAMPAIGN ACTION APIS
# =========================================================================

@login_required
@require_http_methods(["GET"])
def get_campaign_status_api(request, pk):
    """
    API to fetch the live status and progress of a single campaign.
    """
    campaign = get_object_or_404(MessageCampaign, pk=pk, created_by=request.user)

    total = campaign.total_recipients
    # FIX: Correctly using CampaignRecipient model for filtering
    sent = CampaignRecipient.objects.filter(campaign=campaign, status='SENT').count()
    failed = CampaignRecipient.objects.filter(campaign=campaign, status='FAILED').count()

    processed_count = sent + failed

    progress = 0
    if total > 0:
        progress = int((processed_count / total) * 100)

    # Check agar saare messages processed ho gaye hain
    if processed_count == total and campaign.status == 'IN_PROGRESS':
        campaign.status = 'COMPLETED'
        campaign.completed_at = timezone.now()
        # Save must happen outside this view or be wrapped in transaction/save_fields
        campaign.save(update_fields=['status', 'completed_at'])

    status_data = {
        'status': campaign.status,
        'status_display': campaign.get_status_display(),
        'total_recipients': total,
        'sent_count': sent,
        'failed_count': failed,
        'progress': progress,
    }
    return JsonResponse(status_data)


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def campaign_run_api(request, pk):
    """
    API to manually start a PENDING campaign.
    """
    campaign = get_object_or_404(MessageCampaign, pk=pk, created_by=request.user)

    if campaign.status != 'PENDING':
        return JsonResponse({
            'success': False,
            'message': f"Campaign status is {campaign.get_status_display()}, only PENDING campaigns can be started.",
        }, status=400)

    campaign.scheduled_time = None
    campaign.status = 'IN_PROGRESS'
    campaign.started_at = timezone.now()
    campaign.save(update_fields=['scheduled_time', 'status', 'started_at'])

    # Task ko turant run karein
    send_campaign_task.delay(campaign.pk)

    return JsonResponse({
        'success': True,
        'message': "Campaign started successfully. Messages will begin sending shortly.",
    })

@login_required
@require_http_methods(["POST"])
@transaction.atomic
def campaign_delete_view(request, pk):
    """Deletes a campaign."""
    campaign = get_object_or_404(MessageCampaign, pk=pk, created_by=request.user)
    campaign_name = campaign.name
    campaign.delete()
    messages.success(request, f"Campaign '{campaign_name}' deleted successfully.")
    return redirect(reverse('messaging:campaign_list'))