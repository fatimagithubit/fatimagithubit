from __future__ import absolute_import, unicode_literals
import os
import sys
import pathlib
from celery import Celery

# --- THE DEFINITIVE FIX ---
# This block of code adds your project's root directory and its parent
# to the Python path. This is a robust way to ensure that all modules,
# including 'accounts' and 'messaging', are always found by Celery.
try:
    # Get the directory of the current file (celery.py)
    CORE_DIR = pathlib.Path(__file__).resolve().parent
    # Get the directory of the project ('whatsx')
    WHATSX_DIR = CORE_DIR.parent
    # Add both the project directory and its parent to the path
    sys.path.insert(0, str(WHATSX_DIR))
    sys.path.insert(0, str(WHATSX_DIR.parent))
except IndexError:
    pass
# --- END OF FIX ---

# This line tells Django where to find the settings.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Create the Celery app instance.
app = Celery('whatsx')

# Load the configuration from your Django settings.py file.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover all tasks in your installed apps (e.g., tasks.py).
app.autodiscover_tasks()