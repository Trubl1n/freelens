import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freelancer_tracker.settings')
django.setup()

from django.core.management import call_command

print("Running migrations...")
call_command('migrate')

print("Collecting static files...")
call_command('collectstatic', '--noinput')

print("✅ Done! You can now create superuser via Django admin.")