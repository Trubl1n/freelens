import os

import django
from django.contrib.auth import get_user_model
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freelancer_tracker.settings")
django.setup()

print("🚀 Starting migrations...")
call_command("migrate")
print("✅ Migrations done!")

call_command("collectstatic", "--noinput")
print("✅ Static collected!")

User = get_user_model()
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "admin@local.ru", "admin123")
    print("✅ Admin: admin / admin123")
