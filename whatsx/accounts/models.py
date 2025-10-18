from django.db import models
from django.conf import settings

class Contact(models.Model):
    """A simple placeholder model for a user's contact."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=30)

    def __str__(self):
        return self.name