"""Zaxira nusxa olish (cron yoki qo'lda): python manage.py backup_db [--file yo'l.json.gz]"""
from django.core.management.base import BaseCommand

from crm.backup import dump, make_backup, to_bytes


class Command(BaseCommand):
    help = "Bazaning zaxira nusxasini oladi va bazada saqlaydi (ixtiyoriy: faylga ham yozadi)"

    def add_arguments(self, parser):
        parser.add_argument("--file", help="Nusxani shu faylga ham yozish (.json.gz)")
        parser.add_argument("--only-file", action="store_true", help="Bazaga yozmasdan faqat faylga")

    def handle(self, *args, **opts):
        if opts["only_file"] and not opts["file"]:
            self.stderr.write("--only-file uchun --file kerak")
            return
        if opts["file"]:
            with open(opts["file"], "wb") as fh:
                fh.write(to_bytes(dump()))
            self.stdout.write(self.style.SUCCESS(f"Faylga yozildi: {opts['file']}"))
        if not opts["only_file"]:
            b = make_backup("auto")
            self.stdout.write(self.style.SUCCESS(f"Zaxira olindi: #{b.pk}, {b.objects_count} yozuv, {b.size} bayt"))
