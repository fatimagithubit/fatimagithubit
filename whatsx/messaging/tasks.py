import requests, json, logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from .models import Campaign, CampaignRecipient

logger = logging.getLogger(__name__)
NODE_SERVICE_URL = getattr(settings, 'NODE_SERVICE_URL', 'http://127.0.0.1:3001')

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_campaign_messages(self, campaign_id):
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        logger.error(f"Campaign {campaign_id} not found."); return
    if campaign.status not in [Campaign.Status.IN_PROGRESS, Campaign.Status.PENDING]:
        logger.warning(f"Task for campaign {campaign_id} triggered with wrong status: {campaign.status}."); return
    if campaign.status == Campaign.Status.PENDING:
        campaign.status = Campaign.Status.IN_PROGRESS; campaign.started_at = timezone.now()
        campaign.save(update_fields=['status', 'started_at'])

    pending_recipients = campaign.recipients.filter(status=CampaignRecipient.Status.PENDING)
    if not pending_recipients.exists():
        campaign.status = Campaign.Status.COMPLETED; campaign.completed_at = timezone.now()
        campaign.save(update_fields=['status', 'completed_at']); return

    logger.info(f"Processing {pending_recipients.count()} messages for campaign '{campaign.name}'.")
    for recipient in pending_recipients:
        try:
            payload = {'number': recipient.phone_number, 'message': campaign.message_content}
            response = requests.post(f"{NODE_SERVICE_URL}/api/v1/whatsapp/send", json=payload, timeout=20)
            if response.status_code == 200 and response.json().get('success'):
                recipient.status = CampaignRecipient.Status.SENT
                recipient.sent_at = timezone.now(); recipient.error_message = None
            else:
                recipient.status = CampaignRecipient.Status.FAILED
                recipient.error_message = f"API Error ({response.status_code}): {response.json().get('message', 'N/A')}"
        except requests.exceptions.RequestException as e:
            recipient.status = CampaignRecipient.Status.FAILED
            recipient.error_message = f"Network Error: {e}"
        finally: recipient.save()

    if campaign.recipients.filter(status=CampaignRecipient.Status.FAILED, error_message__icontains="Network").exists():
        self.retry()
    elif not campaign.recipients.filter(status=CampaignRecipient.Status.PENDING).exists():
        campaign.status = Campaign.Status.COMPLETED; campaign.completed_at = timezone.now()
        campaign.save(update_fields=['status', 'completed_at'])