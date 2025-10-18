import os
import sys
import pathlib

# This adds the project's parent directory ('full project') to the Python path.
# This is the most robust way to ensure all modules are found.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# This tells Celery and Django which settings file to use.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'whatsx.core.settings')

# This imports and defines the Celery application instance.
from whatsx.core.celery import app as celery_app

# This makes the app available for the command line.
app = celery_app