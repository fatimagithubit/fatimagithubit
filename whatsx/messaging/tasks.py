from celery import shared_task
from .models import Message

@shared_task
def send_scheduled_message(message_id):
    try:
        message = Message.objects.get(id=message_id)
        # In a real application, you would integrate with a WhatsApp API here
        # For now, we'll just mark the message as sent
        message.status = 'sent'
        message.save()
    except Message.DoesNotExist:
        pass