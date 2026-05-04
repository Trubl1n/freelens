from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from core.models import Profile

User = get_user_model()


def profile_defaults():
    return {
        "start_date": timezone.localdate(),
        "target_monthly_income": Decimal("0.00"),
    }


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(
            user=instance,
            defaults=profile_defaults(),
        )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    profile, _ = Profile.objects.get_or_create(
        user=instance,
        defaults=profile_defaults(),
    )
    profile.save()
