import os
import django
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freelancer_tracker.settings')

# Выполняем миграции ПЕРЕД запуском приложения
django.setup()
try:
    print("🚀 Running migrations...")
    call_command('migrate', '--noinput')
    call_command('collectstatic', '--noinput', '--clear')
    print("✅ Migrations completed!")
except Exception as e:
    print(f"⚠️ Migration warning: {e}")

application = get_wsgi_application()