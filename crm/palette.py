"""Tezkor qidiruv oynasi (Ctrl+K): talaba, lid va guruhlarni nomi yoki telefoni bo'yicha topadi."""
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse

from . import services as sv
from .roles import allowed, can_money


def _digits(x):
    return re.sub(r"\D", "", str(x or ""))


@login_required
def palette(request):
    q = request.GET.get("q", "").strip().lower()
    if len(q) < 2:
        return JsonResponse({"items": []})
    u = request.user
    d = sv.Data(u)
    ph = _digits(q)
    out = []

    def hit(*parts):
        txt = " ".join(str(p or "") for p in parts).lower()
        return q in txt or (len(ph) >= 3 and any(ph in _digits(p) for p in parts))

    if allowed(u, "talabalar"):
        for s in d.students:
            if hit(s.name, s.phone, s.parent):
                g = d.group_of(s)
                sub = " · ".join(x for x in [g.name if g else "Guruhsiz", s.get_status_display()] if x)
                if can_money(u) and s.status == "faol":
                    debt = d.debt_for(s, d.NOW)
                    if debt:
                        sub += f" · qarz {sv.fmt(debt)}"
                out.append({"t": s.name, "sub": sub, "url": reverse("student_profile", args=[s.pk]), "k": "Talaba"})
                if len(out) >= 8:
                    break
    if allowed(u, "lidlar"):
        n = 0
        for l in d.leads:
            if hit(l.name, l.phone, l.course):
                out.append({"t": l.name, "sub": f"{l.get_status_display()} · {l.course or l.source}",
                            "url": reverse("lead_log", args=[l.pk]), "k": "Lid"})
                n += 1
                if n >= 5:
                    break
    if allowed(u, "guruhlar"):
        for g in d.groups:
            if hit(g.name, g.course, g.teacher):
                out.append({"t": g.name, "sub": f"{g.teacher or ''} · {d.active_in(g)} talaba".strip(" ·"),
                            "url": reverse("group_edit", args=[g.pk]), "k": "Guruh"})
    return JsonResponse({"items": out[:16]})
