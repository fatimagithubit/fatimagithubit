import csv, io, re, json, requests
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction, models
from django.http import JsonResponse
from .models import Campaign, CampaignRecipient, MessageTemplate
from accounts.models import Contact
from .tasks import send_campaign_messages

@login_required
def whatsapp_connect_view(request):
    return render(request, 'messaging/whatsapp_connect.html')

def make_node_request(method, endpoint):
    node_url = f"http://127.0.0.1:3001/{endpoint}"
    try:
        if method.lower() == 'post': response = requests.post(node_url, timeout=20)
        else: response = requests.get(node_url, timeout=10)
        response.raise_for_status()
        return JsonResponse(response.json())
    except requests.exceptions.RequestException as e:
        return JsonResponse({'status': 'ERROR', 'message': f'WhatsApp service connection failed: {e}'}, status=503)

@login_required
def start_session_api(request): return make_node_request('post', 'start')
@login_required
def status_api(request): return make_node_request('get', 'status')
@login_required
def disconnect_api(request): return make_node_request('post', 'disconnect')

@login_required
def template_list_view(request):
    templates = MessageTemplate.objects.filter(models.Q(created_by=request.user) | models.Q(created_by__is_superuser=True)).distinct().order_by('title')
    return render(request, 'messaging/template_list.html', {'templates': templates})

@login_required
def campaign_list_view(request):
    campaigns = Campaign.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'messaging/campaign_list.html', {'campaigns': campaigns})

@login_required
@transaction.atomic
def campaign_create_view(request):
    if request.method == 'POST':
        campaign_name = request.POST.get('campaign_name')
        message_content = request.POST.get('message_content')
        scheduled_at_str = request.POST.get('scheduled_at')
        if not all([campaign_name, message_content]):
            messages.error(request, "Campaign Name and Message Content are required.")
            return redirect('messaging:campaign_create')
        try:
            recipients = _process_recipients(request)
            if not recipients: raise ValueError("No valid recipients found. Please add contacts from at least one source.")
        except ValueError as e:
            messages.error(request, str(e)); return redirect('messaging:campaign_create')

        campaign = Campaign.objects.create(name=campaign_name, message_content=message_content, created_by=request.user)
        recipient_objects = [CampaignRecipient(campaign=campaign, phone_number=phone, contact=contact) for phone, contact in recipients.items()]
        CampaignRecipient.objects.bulk_create(recipient_objects)

        if scheduled_at_str:
            try:
                scheduled_at = timezone.datetime.strptime(scheduled_at_str, '%Y-%m-%dT%H:%M')
                if timezone.is_naive(scheduled_at): scheduled_at = timezone.make_aware(scheduled_at)
                if scheduled_at <= timezone.now(): raise ValueError("Scheduled time must be in the future.")
                campaign.scheduled_at = scheduled_at
                campaign.status = Campaign.Status.PENDING
                send_campaign_messages.apply_async(args=[campaign.id], eta=scheduled_at)
                messages.success(request, f"Campaign '{campaign.name}' scheduled for {scheduled_at.strftime('%b %d, %Y at %I:%M %p')}.")
            except ValueError as e:
                messages.error(request, str(e)); campaign.delete(); return redirect('messaging:campaign_create')
        else:
            campaign.status = Campaign.Status.IN_PROGRESS
            campaign.started_at = timezone.now()
            send_campaign_messages.delay(campaign.id)
            messages.success(request, f"Campaign '{campaign.name}' has started immediately.")
        campaign.save()
        return redirect('messaging:campaign_list')

    user_templates = MessageTemplate.objects.filter(models.Q(created_by=request.user) | models.Q(created_by__is_superuser=True)).distinct()
    user_contacts = Contact.objects.filter(user=request.user)
    templates_json = json.dumps({t.id: t.content for t in user_templates})
    return render(request, 'messaging/campaign_form.html', {'templates': user_templates, 'contacts': user_contacts, 'templates_json': templates_json})

def _process_recipients(request):
    recipients = {}
    contact_ids = request.POST.getlist('contacts')
    if contact_ids:
        for contact in Contact.objects.filter(id__in=contact_ids, user=request.user):
            if phone := _normalize_phone(contact.phone): recipients[phone] = contact
    manual_numbers = request.POST.get('manual_numbers', '')
    if manual_numbers:
        for number in manual_numbers.splitlines():
            if number.strip() and (phone := _normalize_phone(number)) and phone not in recipients: recipients[phone] = None
    csv_file = request.FILES.get('csv_file')
    if csv_file:
        if not csv_file.name.endswith('.csv'): raise ValueError("Please upload a valid CSV file.")
        if csv_file.size > 5 * 1024 * 1024: raise ValueError("CSV file size exceeds 5MB.")
        reader = csv.DictReader(io.StringIO(csv_file.read().decode('utf-8')))
        phone_col = next((col for col in reader.fieldnames if 'phone' in col.lower()), None)
        if not phone_col: raise ValueError("CSV must have a column named 'Phone' or 'Phone Number'.")
        for row in reader:
            if row.get(phone_col) and (phone := _normalize_phone(row[phone_col])) and phone not in recipients: recipients[phone] = None
    return recipients

def _normalize_phone(number):
    number = re.sub(r'\D', '', str(number))
    if len(number) == 10 and not number.startswith('92'): number = '92' + number
    if len(number) == 12 and number.startswith('92'): return '+' + number
    return None