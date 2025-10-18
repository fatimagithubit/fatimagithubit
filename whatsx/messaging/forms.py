from django import forms
from .models import MessageCampaign, WhatsAppCredentials

class WhatsAppCredentialsForm(forms.ModelForm):
    """A placeholder form for WhatsApp credentials."""
    class Meta:
        model = WhatsAppCredentials
        fields = ['session_id'] # Simplified for now

class CampaignForm(forms.ModelForm):
    """A placeholder form for creating a message campaign."""
    selected_contacts = forms.MultipleChoiceField(required=False)
    manual_numbers = forms.CharField(required=False, widget=forms.Textarea)
    csv_file = forms.FileField(required=False)

    class Meta:
        model = MessageCampaign
        fields = ['name', 'message_content', 'message_template', 'scheduled_time', 'attachment']

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # In a real scenario, you'd populate choices here
        self.fields['selected_contacts'].choices = []