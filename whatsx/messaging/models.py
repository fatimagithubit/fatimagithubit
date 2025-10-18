from django.db import models
from django.conf import settings
from accounts.models import Contact

class MessageTemplate(models.Model):
    title = models.CharField(max_length=200, help_text="A unique name for this template.")
    content = models.TextField(help_text="The body of the message. You can use placeholders like {{name}}.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return self.title

class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING = 'PENDING', 'Pending Schedule'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    name = models.CharField(max_length=255, help_text="The name of the campaign for tracking.")
    message_content = models.TextField(help_text="The final message body to be sent.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="If set, campaign starts at this time.")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

class CampaignRecipient(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="recipients")
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True)
    phone_number = models.CharField(max_length=20, help_text="The E.164 formatted phone number.")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('campaign', 'phone_number')
    def __str__(self):
        return f"{self.phone_number} in '{self.campaign.name}'"