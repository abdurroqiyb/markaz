"""Telegram bot: ota-onaga qarz, davomat va to'lov xabarlari, xodimlarga eslatmalar.

Sozlash: Render'da TELEGRAM_BOT_TOKEN o'zgaruvchisini qo'shing (@BotFather bergan token).
Zaxira uchun BACKUP_TELEGRAM_BOT_TOKEN allaqachon bo'lsa, o'sha bot ham ishlaydi.
Keyin CRM'da "Telegram bot" sahifasida "Botni ulash" tugmasini bosing.

Ota-ona farzandining 6 xonali kodini botga yuboradi (yoki profil sahifasidagi havola orqali kiradi)
va shu chat farzandiga ulanadi. Xodim o'z kabinetidagi havola orqali ulanadi.
"""
import hashlib
import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.request
from datetime import timedelta

from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

log = logging.getLogger(__name__)
ABSENT_LABEL = {"kelmadi": "darsga kelmadi", "sababli": "darsga sababli kelmadi"}


# ---------------------------------------------------------------- sozlama va API
def token():
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BACKUP_TELEGRAM_BOT_TOKEN") or "").strip()


def enabled():
    return bool(token())


def hook_secret():
    return hashlib.sha256(("markaz-tg:" + token()).encode()).hexdigest()[:32]


def api(method, **params):
    """Telegram Bot API chaqiruvi. Xatoda None qaytaradi (ilova to'xtamasligi kerak)."""
    if not enabled():
        return None
    req = urllib.request.Request(f"https://api.telegram.org/bot{token()}/{method}",
                                 data=json.dumps(params).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
            return data.get("result") if data.get("ok") else None
    except Exception as e:  # tarmoq xatosi
        log.warning("Telegram %s xatosi: %s", method, e.__class__.__name__)
        return None


def send(chat_id, text):
    return api("sendMessage", chat_id=chat_id, text=text[:4000], disable_web_page_preview=True)


def send_many(pairs):
    """[(chat_id, matn)] ni fonda yuboradi (so'rovni kutib qolmaslik uchun). Navbatdagi soni qaytadi."""
    pairs = [(c, t) for c, t in pairs if c and t]
    if not pairs or not enabled():
        return 0

    def run():
        for c, t in pairs:
            send(c, t)
            time.sleep(0.05)  # Telegram cheklovi: sekundiga ~30 xabar
    if os.environ.get("TG_SYNC"):
        run()
    else:
        threading.Thread(target=run, daemon=True).start()
    return len(pairs)


def bot_username():
    u = cache.get("tg:username")
    if u is None and enabled():
        me = api("getMe") or {}
        u = me.get("username", "")
        cache.set("tg:username", u, 3600 if u else 60)
    return u or ""


def deep_link(payload):
    u = bot_username()
    return f"https://t.me/{u}?start={payload}" if u else ""


def connect_webhook(base_url):
    url = base_url.rstrip("/") + f"/tg/hook/{hook_secret()}/"
    ok = api("setWebhook", url=url, secret_token=hook_secret(), allowed_updates=["message"])
    cache.delete("tg:username")
    return ok is not None


# ---------------------------------------------------------------- matnlar
def _center():
    from .models import Center
    return Center.get()


def _chats_of(student_ids):
    from .models import ParentChat
    out = {}
    for sid, chat in ParentChat.objects.filter(student_id__in=list(student_ids)).values_list("student_id", "chat_id"):
        out.setdefault(sid, []).append(chat)
    return out


def student_status_text(s):
    """Ota-onaga farzandi haqida qisqa ma'lumot (/holat)."""
    from . import services as sv
    d = sv.Data()
    s = d.student_map.get(s.pk, s)
    g = d.group_of(s)
    marks = [st for _, st in d.student_marks(s, since=d.TODAY - timedelta(days=30))]
    came = marks.count("keldi")
    debt = d.total_debt(s)
    lines = [f"👤 {s.name}", f"Guruh: {g.name if g else '-'}"]
    if g and (g.days or g.time):
        lines.append(f"Dars: {' '.join(x for x in [g.days, sv.time_range(g)] if x)}")
    lines.append(f"Davomat (30 kun): {came}/{len(marks)}" if marks else "Davomat (30 kun): hali belgilanmagan")
    lessons = [l for l in d.lessons if g and l.group_id == g.id and l.homework]
    if lessons:
        lines.append(f"Oxirgi uy vazifasi: {lessons[-1].homework}")
    lines.append(f"Qarz: {sv.fmt(debt)} so'm" if debt else "Qarz yo'q ✅")
    return "\n".join(lines)


def notify_absent(lesson, marks):
    """Davomatda kelmagan deb belgilangan talabalar ota-onasiga xabar. marks: {student: status}."""
    c = _center()
    if not c.tg_absent or not enabled():
        return 0
    bad = {s: st for s, st in marks.items() if st in ABSENT_LABEL}
    chats = _chats_of(s.pk for s in bad)
    pairs = []
    for s, st in bad.items():
        txt = (f"{c.name}: {s.name} bugun ({lesson.date:%d.%m.%Y}) {lesson.group.name} "
               f"{ABSENT_LABEL[st]}." + (f" Savollar bo'lsa: {c.phone}" if c.phone else ""))
        pairs += [(ch, txt) for ch in chats.get(s.pk, [])]
    return send_many(pairs)


def notify_payment(payments):
    from . import services as sv
    c = _center()
    if not payments or not c.tg_payment or not enabled():
        return 0
    s = payments[0].student
    total = sum(p.amount for p in payments)
    months = ", ".join(sv.mlabel(p.month) for p in payments)
    txt = f"{c.name}: {s.name} uchun {sv.fmt(total)} so'm to'lov qabul qilindi ({months}). Rahmat!"
    return send_many([(ch, txt) for ch in _chats_of([s.pk]).get(s.pk, [])])


def send_debt_reminders(rows):
    """rows: services.with_reminders natijasi. Ulangan ota-onalarga yuboriladi."""
    chats = _chats_of(r["s"].pk for r in rows)
    return send_many([(ch, r["msg"]) for r in rows for ch in chats.get(r["s"].pk, [])])


# ---------------------------------------------------------------- xodimlar
def notify_user(user, text, url=""):
    """Xodimga CRM ichida bildirishnoma va (ulangan bo'lsa) Telegram xabar."""
    from .models import Notification
    if user is None or not user.is_active:
        return
    Notification.objects.create(user=user, text=text[:300], url=url[:300])
    staff = getattr(user, "staff", None)
    if staff and staff.tg_chat:
        send_many([(staff.tg_chat, text)])


def staff_digest(user):
    """Xodim uchun bugungi eslatmalar matni (bo'sh bo'lsa "")."""
    from . import notify
    items = notify.reminders(user)
    if not items:
        return ""
    return "Bugungi eslatmalar:\n" + "\n".join(f"• {x['text']}" for x in items[:15])


_digest_check = 0.0
_digest_lock = threading.Lock()


def ensure_daily_digest():
    """Har kuni soat 8 dan keyin birinchi so'rovda ulangan xodimlarga eslatma yuboradi."""
    global _digest_check
    from .models import ActivityLog, Staff
    now = time.monotonic()
    if now - _digest_check < 600 or not enabled():
        return
    if not _digest_lock.acquire(blocking=False):
        return
    try:
        _digest_check = now
        local = timezone.localtime()
        if local.hour < 8 or not _center().tg_staff_digest:
            return
        mark = f"Telegram: kunlik eslatma {local.date()}"
        if ActivityLog.objects.filter(text=mark).exists():
            return
        ActivityLog.objects.create(user=None, text=mark)
        pairs = []
        for st in Staff.objects.exclude(tg_chat="").select_related("user"):
            if st.user.is_active:
                txt = staff_digest(st.user)
                if txt:
                    pairs.append((st.tg_chat, txt))
        send_many(pairs)
    except Exception:
        log.exception("Kunlik eslatma yuborilmadi")
    finally:
        _digest_lock.release()


def staff_link_code(staff):
    if not staff.tg_code:
        staff.tg_code = secrets.token_hex(5)
        staff.save(update_fields=["tg_code"])
    return "x" + staff.tg_code


# ---------------------------------------------------------------- webhook
HELP = ("Assalomu alaykum! Bu {markaz} boti.\n\n"
        "Farzandingizni ulash uchun markaz bergan 6 xonali kodni yuboring.\n"
        "/holat - farzandingiz davomati, uy vazifasi va qarzi\n/stop - xabarlarni o'chirish")


def handle(update):
    from .models import ParentChat, Staff, Student
    msg = update.get("message") or {}
    chat = str((msg.get("chat") or {}).get("id") or "")
    text = (msg.get("text") or "").strip()
    if not chat or not text:
        return
    who = " ".join(x for x in [(msg.get("from") or {}).get("first_name"), (msg.get("from") or {}).get("last_name")]
                   if x)[:200]
    c = _center()
    arg = text.split(maxsplit=1)[1].strip() if text.startswith("/start") and " " in text else text
    if arg.startswith("x") and len(arg) > 4:
        st = Staff.objects.filter(tg_code=arg[1:]).select_related("user").first()
        if st:
            st.tg_chat = chat
            st.save(update_fields=["tg_chat"])
            send(chat, f"✅ {st.user.get_full_name() or st.user.username}, CRM eslatmalari shu yerga keladi.")
            return
    if text.startswith("/stop"):
        n = ParentChat.objects.filter(chat_id=chat).delete()[0]
        Staff.objects.filter(tg_chat=chat).update(tg_chat="")
        send(chat, "Xabarlar o'chirildi." if n else "Bu chat hech kimga ulanmagan.")
        return
    if text.startswith("/holat"):
        links = ParentChat.objects.filter(chat_id=chat).select_related("student")
        if not links:
            send(chat, "Avval farzandingiz kodini yuboring.")
        for l in links:
            send(chat, student_status_text(l.student))
        return
    code = re.sub(r"\D", "", arg)
    if len(code) == 6:
        # kodni taxmin qilishdan himoya: bir chatdan soatiga 10 urinish
        key = f"tg:try:{chat}"
        n = cache.get(key, 0)
        if n >= 10:
            send(chat, "Juda ko'p urinish. Birozdan keyin qayta yuboring.")
            return
        s = Student.objects.filter(code=code).first()
        if not s:
            cache.set(key, n + 1, 3600)
            send(chat, "Kod topilmadi. Markazdan kodni tekshirib oling.")
            return
        ParentChat.objects.get_or_create(chat_id=chat, student=s, defaults={"name": who})
        send(chat, f"✅ {s.name} ulandi. Endi darsga kelmasa, to'lov va qarz haqida xabar shu yerga keladi.\n\n"
                   + student_status_text(s))
        return
    send(chat, HELP.format(markaz=c.name))


@csrf_exempt
@require_POST
def webhook(request, secret):
    if not enabled() or secret != hook_secret() or \
            request.headers.get("X-Telegram-Bot-Api-Secret-Token") != hook_secret():
        return HttpResponseForbidden()
    try:
        handle(json.loads(request.body.decode() or "{}"))
    except Exception:
        log.exception("Telegram xabarini qayta ishlashda xato")
    return HttpResponse("ok")


# ---------------------------------------------------------------- sozlash sahifasi (direktor)
def _settings_form(data=None, instance=None):
    from django import forms as f
    from .forms import StyledModelForm
    from .models import Center

    class TgForm(StyledModelForm):
        class Meta:
            model = Center
            fields = ["tg_absent", "tg_payment", "tg_staff_digest"]
    return TgForm(data, instance=instance)


def settings_page(request):
    from django.contrib import messages
    from django.shortcuts import redirect, render
    from .models import ParentChat, Staff, Student
    from .roles import is_director
    if not is_director(request.user):
        messages.error(request, "Bu bo'lim faqat direktor uchun.")
        return redirect("home")
    c = _center()
    form = _settings_form(request.POST or None, instance=c)
    if request.method == "POST":
        if request.POST.get("action") == "connect":
            if connect_webhook(request.build_absolute_uri("/")):
                messages.success(request, "Bot ulandi. Endi ota-onalar kod yuborib ulanishi mumkin.")
            else:
                messages.error(request, "Bot ulanmadi. Token to'g'riligini va sayt https orqali ochilishini tekshiring.")
            return redirect("tg_settings")
        if form.is_valid():
            form.save()
            messages.success(request, "Saqlandi")
            return redirect("tg_settings")
    total = Student.objects.filter(status="faol").count()
    linked = ParentChat.objects.filter(student__status="faol").values("student").distinct().count()
    hook = api("getWebhookInfo") if enabled() else None
    return render(request, "crm/telegram.html", {
        "section": "tg_settings", "on": enabled(), "bot": bot_username(), "form": form,
        "hooked": bool(hook and hook.get("url", "").endswith(f"/tg/hook/{hook_secret()}/")),
        "hook_error": (hook or {}).get("last_error_message", ""),
        "linked": linked, "total": total, "staff_linked": Staff.objects.exclude(tg_chat="").count(),
        "chats": ParentChat.objects.select_related("student").order_by("-created_at")[:30],
    })
