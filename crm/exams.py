"""Imtihon va test natijalari: guruh bo'yicha bir yo'la ball kiritish, reyting va o'sish grafigi."""
from collections import defaultdict
from datetime import date

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from urllib.parse import urlencode

from . import services as sv
from .models import ActivityLog, Grade, Student
from .roles import section_required


def _exams(group):
    """Guruhdagi imtihonlar: (nom, sana) bo'yicha guruhlangan."""
    rows = defaultdict(list)
    for gr in Grade.objects.filter(group=group).select_related("student"):
        rows[(gr.title, gr.date)].append(gr)
    out = []
    for (title, d), items in rows.items():
        pcts = [x.pct for x in items]
        best = max(items, key=lambda x: x.pct)
        out.append({"title": title, "date": d, "n": len(items), "avg": round(sum(pcts) / len(pcts)),
                    "best": best.student.name, "best_pct": best.pct,
                    "q": urlencode({"g": group.pk, "t": title, "d": d.isoformat()})})
    return sorted(out, key=lambda r: r["date"], reverse=True)


@section_required("imtihon")
def imtihon(request):
    groups = sv.Data(request.user).groups
    if not groups:
        return render(request, "crm/imtihon.html", {"section": "imtihon", "no_groups": True})
    src = request.POST if request.method == "POST" else request.GET
    g = next((x for x in groups if str(x.pk) == src.get("g")), groups[0])
    studs = list(Student.objects.filter(group=g, status="faol").order_by("name"))
    if request.method == "POST":
        title = request.POST.get("title", "").strip()[:200]
        try:
            day = date.fromisoformat(request.POST.get("date", ""))
            mx = max(1, int(request.POST.get("max_score") or 100))
        except ValueError:
            day, mx = None, 100
        if not title or not day:
            messages.error(request, "Imtihon nomi va sanasini kiriting")
            return redirect(f"{reverse('imtihon')}?g={g.pk}")
        n = 0
        with transaction.atomic():
            for s in studs:
                raw = request.POST.get(f"s{s.pk}", "").strip().replace(",", ".")
                if raw == "":
                    continue
                try:
                    sc = max(0, min(mx, round(float(raw))))
                except ValueError:
                    continue
                Grade.objects.update_or_create(student=s, group=g, title=title, date=day,
                                               defaults={"score": sc, "max_score": mx})
                n += 1
        ActivityLog.objects.create(user=request.user, text=f"Imtihon natijalari: {g.name} · {title} ({n} ta)"[:300])
        messages.success(request, f"{n} ta natija saqlandi")
        return redirect(f"{reverse('imtihon')}?" + urlencode({"g": g.pk, "t": title, "d": day.isoformat()}))

    exams = _exams(g)
    sel, ranking, grow = None, [], []
    t, d = request.GET.get("t"), request.GET.get("d")
    if t and d:
        try:
            dd = date.fromisoformat(d)
        except ValueError:
            dd = None
        items = sorted(Grade.objects.filter(group=g, title=t, date=dd).select_related("student"),
                       key=lambda x: -x.pct) if dd else []
        if items:
            sel = {"title": t, "date": dd, "max": items[0].max_score,
                   "avg": round(sum(x.pct for x in items) / len(items))}
            ranking = [{"place": i + 1, "s": x.student, "score": x.score, "pct": x.pct} for i, x in enumerate(items)]
    for e in reversed(exams[:8]):
        grow.append({"label": f"{e['title']} ({e['date']:%d.%m})", "short": e["date"].strftime("%d.%m"),
                     "avg": e["avg"]})
    prefill = {r["s"].pk: r["score"] for r in ranking}
    return render(request, "crm/imtihon.html", {
        "section": "imtihon", "groups": groups, "g": g, "studs": [{"s": s, "v": prefill.get(s.pk, "")} for s in studs],
        "exams": exams, "sel": sel, "ranking": ranking, "today": sv.today(),
        "rank_bars": [{"label": f"{r['place']}. {r['s'].name}", "v": r["pct"],
                       "color": "var(--good)" if r["pct"] >= 85 else "var(--accent)" if r["pct"] >= 60 else "var(--warn)"}
                      for r in ranking],
        "grow": grow,
    })
