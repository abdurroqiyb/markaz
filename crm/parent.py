"""Ota-ona kabineti: telefon raqami va farzandining 6 xonali kodi bilan kiriladi (xodim paroli kerak emas).

Ko'rinadi: guruh va jadval, davomat, baholar, uy vazifalari, qarz va to'lovlar.
Himoya: kod + telefon birga to'g'ri bo'lishi kerak, bir IP dan 15 daqiqada 10 ta xato urinish.
Bir ota-ona bir nechta farzandini qo'shishi mumkin (har birining kodi bilan).
"""
import re

from django import forms
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .models import Center, Student
from .security import client_ip

SESSION = "parent_students"
TRIES = 10


def digits(x):
    return re.sub(r"\D", "", str(x or ""))


def phone_match(a, b):
    a, b = digits(a), digits(b)
    return len(a) >= 7 and len(b) >= 7 and a[-9:] == b[-9:]


class ParentLoginForm(forms.Form):
    phone = forms.CharField(label="Telefon raqamingiz", max_length=50,
                            widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "+998 90 123 45 67",
                                                          "autocomplete": "tel"}))
    code = forms.CharField(label="Farzandingiz kodi (6 raqam)", max_length=12,
                           widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code",
                                                         "placeholder": "123456"}))


def _ids(request):
    return [int(x) for x in request.session.get(SESSION, []) if str(x).isdigit()]


@csrf_protect
def kirish(request):
    center = Center.get()
    if not center.parent_cabinet:
        return render(request, "crm/parent.html", {"center": center, "closed": True}, status=404)
    form = ParentLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        key = f"parent:{client_ip(request)}"
        n = cache.get(key, 0)
        if n >= TRIES:
            form.add_error(None, "Juda ko'p xato urinish. 15 daqiqadan keyin qayta urinib ko'ring.")
        else:
            code = digits(form.cleaned_data["code"])
            s = Student.objects.filter(code=code).first() if len(code) == 6 else None
            if s and (phone_match(form.cleaned_data["phone"], s.parent) or
                      phone_match(form.cleaned_data["phone"], s.phone)):
                ids = _ids(request)
                if s.pk not in ids:
                    ids.append(s.pk)
                request.session[SESSION] = ids
                request.session.cycle_key()
                return redirect("parent_home")
            cache.set(key, n + 1, 900)
            form.add_error(None, "Telefon yoki kod noto'g'ri. Kodni markazdan so'rang.")
    return render(request, "crm/parent.html", {"center": center, "form": form, "login": True,
                                                "has": bool(_ids(request))})


def kabinet(request):
    from . import services as sv
    from . import telegram as tg
    center = Center.get()
    ids = _ids(request)
    if not center.parent_cabinet or not ids:
        return redirect("parent_login")
    d = sv.Data()
    kids = []
    for sid in ids:
        s = d.student_map.get(sid)
        if not s:
            continue
        g = d.group_of(s)
        marks = d.student_marks(s)
        came = sum(1 for _, st in marks if st == "keldi")
        lessons = [l for l in d.lessons if g and l.group_id == g.id and (l.topic or l.homework)][-5:][::-1]
        grades = list(s.grades.all().order_by("-date"))[:8]
        months = [{"label": sv.mlabel(m), "debt": d.debt_for(s, m), "paid": d.paid_for(s, m)}
                  for m in d.months_of(s)][-6:][::-1]
        kids.append({"s": s, "g": g, "time": sv.time_range(g) if g else "", "marks": marks[-20:],
                     "att": sv.pct(came, len(marks)) if marks else None, "came": came, "tot": len(marks),
                     "lessons": lessons, "grades": grades, "debt": d.total_debt(s), "months": months,
                     "pays": [p for p in s.payments.all()[:6]], "tg": tg.deep_link(s.code) if tg.enabled() else ""})
    if not kids:
        request.session.pop(SESSION, None)
        return redirect("parent_login")
    return render(request, "crm/parent.html", {"center": center, "kids": kids})


@require_POST
def chiqish(request):
    request.session.pop(SESSION, None)
    return redirect("parent_login")
