"""Zaxira nusxa: butun bazani siqilgan JSON ko'rinishida saqlash va qayta tiklash.

- `make_backup()` barcha CRM jadvallari va foydalanuvchilarni bitta gzip JSON'ga yozadi
  va `Backup` jadvalida saqlaydi (oxirgi KEEP ta nusxa qoladi).
- `ensure_daily_backup()` oxirgi avtomatik nusxa 24 soatdan eski bo'lsa yangisini oladi.
  U har so'rovda emas, jarayon ichida eng ko'pi bilan CHECK_EVERY soniyada bir marta tekshiriladi.
- `restore()` faylni tekshiradi, avval joriy holatning nusxasini oladi, keyin CRM
  ma'lumotlarini fayldagisi bilan almashtiradi. Hammasi bitta tranzaksiyada.
"""
import gzip
import json
import logging
import threading
import time
from datetime import timedelta

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.management.color import no_style
from django.db import connection, transaction
from django.utils import timezone

log = logging.getLogger(__name__)

KEEP = 30
CHECK_EVERY = 600
FORMAT = "markaz-crm-backup"
VERSION = 1

# Saqlash tartibi: bog'liqliklar oldin keladi. Backup jadvalining o'zi kirmaydi.
CRM_MODELS = ["Center", "Staff", "Group", "Lead", "LeadCall", "Student", "Payment", "Charge", "Lesson",
              "Attendance", "Grade", "Expense", "AdSpend", "Promo", "Script", "Task", "ActivityLog"]


def _models():
    return [get_user_model()] + [apps.get_model("crm", n) for n in CRM_MODELS]


def dump():
    """Barcha ma'lumotlar: dict (meta + obyektlar ro'yxati)."""
    objects, summary = [], {}
    for m in _models():
        qs = m._default_manager.order_by("pk")
        rows = json.loads(serializers.serialize("json", qs))
        summary[m._meta.label] = len(rows)
        objects.extend(rows)
    return {"format": FORMAT, "version": VERSION, "created": timezone.now().isoformat(),
            "summary": summary, "objects": objects}


def to_bytes(payload):
    return gzip.compress(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def make_backup(kind="manual"):
    from .models import Backup
    payload = dump()
    blob = to_bytes(payload)
    b = Backup.objects.create(kind=kind, size=len(blob), data=blob, summary=payload["summary"],
                              objects_count=len(payload["objects"]))
    old = list(Backup.objects.order_by("-created_at").values_list("pk", flat=True)[KEEP:])
    if old:
        Backup.objects.filter(pk__in=old).delete()
    return b


_last_check = 0.0
_lock = threading.Lock()


def ensure_daily_backup(force_check=False):
    """Oxirgi 24 soatda avtomatik nusxa bo'lmasa, oladi. Xatoda ilovani to'xtatmaydi."""
    global _last_check
    from .models import Backup
    now = time.monotonic()
    if not force_check and now - _last_check < CHECK_EVERY:
        return None
    if not _lock.acquire(blocking=False):
        return None
    try:
        _last_check = now
        since = timezone.now() - timedelta(hours=24)
        if Backup.objects.filter(kind="auto", created_at__gte=since).exists():
            return None
        b = make_backup("auto")
        log.info("Avtomatik zaxira olindi: %s bayt, %s yozuv", b.size, b.objects_count)
        return b
    except Exception:  # zaxira xatosi foydalanuvchi ishini to'xtatmasligi kerak
        log.exception("Avtomatik zaxira olinmadi")
        return None
    finally:
        _lock.release()


class RestoreError(Exception):
    pass


def load_bytes(raw):
    """Fayl baytlari (gzip yoki oddiy JSON) -> payload dict. Noto'g'ri bo'lsa RestoreError."""
    try:
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise RestoreError("Fayl o'qilmadi: bu Markaz CRM zaxira fayli emas.")
    if not isinstance(payload, dict) or payload.get("format") != FORMAT or not isinstance(payload.get("objects"), list):
        raise RestoreError("Fayl formati noto'g'ri: bu Markaz CRM zaxira fayli emas.")
    allowed = {m._meta.label_lower for m in _models()}
    bad = {o.get("model") for o in payload["objects"] if o.get("model") not in allowed}
    if bad:
        raise RestoreError(f"Faylda noma'lum jadvallar bor: {', '.join(sorted(map(str, bad)))}")
    return payload


def restore(payload):
    """CRM ma'lumotlarini payload bilan almashtiradi. Foydalanuvchilar o'chirilmaydi, yangilanadi."""
    pre = make_backup("pre_restore")
    crm_models = [apps.get_model("crm", n) for n in CRM_MODELS]
    with transaction.atomic():
        with connection.constraint_checks_disabled():
            for m in reversed(crm_models):
                m._default_manager.all().delete()
            n = 0
            for obj in serializers.deserialize("json", json.dumps(payload["objects"])):
                obj.save()
                n += 1
        connection.check_constraints()
        sql = connection.ops.sequence_reset_sql(no_style(), _models())
        if sql:
            with connection.cursor() as c:
                for q in sql:
                    c.execute(q)
    return n, pre
