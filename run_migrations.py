import os
import django
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freelancer_tracker.settings')
django.setup()

print("🚀 Starting migrations...")
call_command('migrate')
print("✅ Migrations done!")

call_command('collectstatic', '--noinput')
print("✅ Static collected!")