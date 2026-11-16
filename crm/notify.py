"""Xodimlar uchun bildirishnomalar: CRM ichidagi qo'ng'iroqcha va Telegram eslatma.

Ikki xil bo'ladi:
  - eslatmalar (har safar hisoblanadi): muddati o'tgan / bugungi vazifalar, bugun qo'ng'iroq qilinadigan
    lidlar, bugungi sinov darslari, qaytadigan muzlatilgan talabalar;
  - xabarlar (Notification): kimdir sizga vazifa berdi, saytdan yangi ariza keldi, kassada farq bor.
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Lead, Notification, Student, Task
from .roles import allowed, is_teacher_scoped


def reminders(user):
    from . import services as sv
    t = sv.today()
    out = []
    tasks = Task.objects.filter(done=False, due__lte=t).filter(Q(assignee=user) | Q(assignee__isnull=True))
    for x in tasks.order_by("due")[:10]:
        late = x.due < t
        label = "Muddati o'tgan" if late else "Bugun"
        out.append({"text": f"{label} vazifa: {x.title}",
                    "url": reverse("vazifalar"), "cls": "bad" if late else "warn"})
    if allowed(user, "lidlar"):
        leads = Lead.objects.exclude(status__in=("yozildi", "rad"))
        b = getattr(user, "active_branch_id", None) or getattr(getattr(user, "staff", None), "filial_id", None)
        if b:
            leads = leads.filter(Q(filial_id=b) | Q(filial=None))
        due = leads.filter(next_contact__lte=t).count()
        if due:
            out.append({"text": f"{due} ta lidga bugun qo'ng'iroq qilish kerak", "url": reverse("bugun"),
                        "cls": "warn"})
        trials = leads.filter(trial_date=t).count()
        if trials:
            out.append({"text": f"Bugun {trials} ta sinov darsi", "url": reverse("bugun"), "cls": "info"})
    if allowed(user, "talabalar") and not is_teacher_scoped(user):
        back = Student.objects.filter(status="muzlatilgan", return_date__lte=t).count()
        if back:
            out.append({"text": f"{back} ta muzlatilgan talabaning qaytish vaqti keldi", "url": reverse("bugun"),
                        "cls": "info"})
    return out


def badge(user):
    """Qo'ng'iroqchadagi son: o'qilmagan xabarlar + eslatmalar."""
    return Notification.objects.filter(user=user, read=False).count() + len(reminders(user))


def notify_users(users, text, url="", exclude=None):
    from . import telegram as tg
    for u in users:
        if exclude is not None and u.pk == exclude.pk:
            continue
        tg.notify_user(u, text, url)


def staff_with(section):
    from django.contrib.auth import get_user_model
    return [u for u in get_user_model().objects.filter(is_active=True).select_related("staff")
            if allowed(u, section)]


@login_required
def bildirishnomalar(request):
    rows = list(Notification.objects.filter(user=request.user)[:50])
    unread = [n.pk for n in rows if not n.read]
    if unread:
        Notification.objects.filter(pk__in=unread).update(read=True)
    for n in rows:
        n.fresh = n.pk in unread
    from . import telegram as tg
    from .models import Staff
    tg_link, linked = "", False
    if tg.enabled():
        st, _ = Staff.objects.get_or_create(user=request.user, defaults={
            "role": "direktor" if request.user.is_superuser else "oqituvchi"})
        linked = bool(st.tg_chat)
        tg_link = "" if linked else tg.deep_link(tg.staff_link_code(st))
    return render(request, "crm/bildirishnomalar.html", {"section": "bildirishnomalar", "rows": rows,
                                                          "rem": reminders(request.user), "tg_on": tg.enabled(),
                                                          "tg_link": tg_link, "tg_linked": linked})


@login_required
@require_POST
def clear(request):
    Notification.objects.filter(user=request.user).delete()
    return redirect("bildirishnomalar")
