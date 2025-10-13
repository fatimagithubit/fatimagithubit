from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Template

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('user_type', 'email',)

class BulkMessageForm(forms.Form):
    message_body = forms.CharField(widget=forms.Textarea)
    contacts_manual = forms.CharField(widget=forms.Textarea, required=False, help_text="Enter one contact per line, in the format 'Name, Phone Number'")
    csv_file = forms.FileField(required=False, help_text="Upload a CSV file with 'Name' and 'Phone Number' columns.")
    template = forms.ModelChoiceField(queryset=Template.objects.all(), required=False)
    scheduled_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))