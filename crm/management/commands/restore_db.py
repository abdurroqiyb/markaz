"""Zaxira fayldan tiklash: python manage.py restore_db yo'l.json.gz --yes"""
from django.core.management.base import BaseCommand, CommandError

from crm.backup import RestoreError, load_bytes, restore


class Command(BaseCommand):
    help = "CRM ma'lumotlarini zaxira fayldan tiklaydi (joriy ma'lumotlar almashtiriladi)"

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--yes", action="store_true", help="Tasdiqlash")

    def handle(self, *args, **opts):
        if not opts["yes"]:
            raise CommandError("Joriy ma'lumotlar almashtiriladi. Tasdiqlash uchun --yes qo'shing.")
        with open(opts["file"], "rb") as fh:
            raw = fh.read()
        try:
            n, pre = restore(load_bytes(raw))
        except RestoreError as e:
            raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS(f"Tiklandi: {n} yozuv. Oldingi holat zaxirasi: #{pre.pk}"))
