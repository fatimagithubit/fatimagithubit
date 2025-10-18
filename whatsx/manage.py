#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import pathlib

def main():
    """Run administrative tasks."""
    # **THE DEFINITIVE FIX IS HERE:**
    # This adds the directory that CONTAINS the 'whatsx' folder
    # to the Python path. This is the standard and correct way to fix this.
    # It allows Python to find 'whatsx' as a package, and therefore find
    # 'accounts' and 'messaging' inside it.

    # Get the directory of the current file (manage.py)
    current_dir = pathlib.Path(__file__).resolve().parent
    # Add this directory to the system path
    sys.path.insert(0, str(current_dir))
    # Also add the PARENT directory to the path, which is often necessary
    # for tools like Celery to work correctly from the root.
    sys.path.insert(0, str(current_dir.parent))

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()