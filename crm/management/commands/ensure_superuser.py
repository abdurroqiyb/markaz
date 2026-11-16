"""Muhit o'zgaruvchilari asosida superuser (direktor) yaratadi.

DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_PASSWORD, DJANGO_SUPERUSER_EMAIL
o'rnatilgan bo'lsa va bunday foydalanuvchi bo'lmasa, yaratiladi. Mavjud bo'lsa
tegilmaydi (parol faqat DJANGO_SUPERUSER_RESET_PASSWORD=true bo'lsa yangilanadi).
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from crm.models import Staff


class Command(BaseCommand):
    help = "Muhit o'zgaruvchilaridan superuser yaratadi (bo'lmasa)."

    def handle(self, *args, **opts):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        if not username or not password:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME/PASSWORD berilmagan, o'tkazib yuborildi.")
            return
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user:
            if os.environ.get("DJANGO_SUPERUSER_RESET_PASSWORD", "").lower() in ("1", "true", "yes"):
                user.set_password(password)
                user.save(update_fields=["password"])
                self.stdout.write(self.style.SUCCESS(f"'{username}' paroli yangilandi."))
            else:
                self.stdout.write(f"'{username}' allaqachon mavjud.")
        else:
            user = User.objects.create_superuser(username=username, email=email, password=password,
                                                 first_name=os.environ.get("DJANGO_SUPERUSER_FIRST_NAME", ""))
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' yaratildi."))
        Staff.objects.get_or_create(user=user, defaults={"role": "direktor"})
