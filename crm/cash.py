"""Kunlik kassa yopilishi.

Kun oxirida kassir naqd pulni sanaydi, terminal (karta) hisobotini ko'radi va kiritadi. Tizim shu kungi
to'lovlar bilan solishtiradi va farqni ko'rsatadi. Yopilgan kunga to'lov qo'shib bo'lmaydi; o'chirishni
faqat direktor qila oladi. Direktor kerak bo'lsa kassani qayta ochadi.
"""
from datetime import date, timedelta

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import services as sv
from .forms import StyledMixin
from .models import CashClose, Payment
from .roles import director_required, is_director, money_required


class CloseForm(StyledMixin, forms.Form):
    cash_real = forms.IntegerField(label="Kassadagi naqd pul (sanab chiqildi)", min_value=0)
    card_real = forms.IntegerField(label="Karta terminali hisoboti", min_value=0)
    note = forms.CharField(label="Izoh (farq bo'lsa sababi)", required=False, max_length=300)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()

    def layout(self):
        return [[self["cash_real"], self["card_real"]], [self["note"]]]


def totals(day, branch=None):
    t = {"Naqd": 0, "Karta": 0, "O'tkazma": 0}
    qs = Payment.objects.filter(date=day)
    if branch:
        qs = qs.filter(student__filial_id=branch)
    rows = list(qs.select_related("student").order_by("-created_at"))
    for p in rows:
        t[p.method] = t.get(p.method, 0) + p.amount
    return t, rows


@money_required
def kassa(request):
    try:
        day = date.fromisoformat(request.GET.get("d") or request.POST.get("d") or "")
    except ValueError:
        day = sv.today()
    from .branches import active
    br = active(request)
    t, rows = totals(day, br)
    closed = CashClose.objects.filter(date=day, filial_id=br).first()
    form = CloseForm(request.POST or None, initial={"cash_real": t["Naqd"], "card_real": t["Karta"]})
    if request.method == "POST" and not closed and form.is_valid():
        cd = form.cleaned_data
        c = CashClose.objects.create(date=day, filial_id=br, cash_sys=t["Naqd"], card_sys=t["Karta"], transfer_sys=t["O'tkazma"],
                                     cash_real=cd["cash_real"], card_real=cd["card_real"], note=cd["note"],
                                     user=request.user)
        from .views import log
        log(request, f"Kassa yopildi: {day} (naqd farq {sv.fmt(c.cash_diff)}, karta farq {sv.fmt(c.card_diff)})")
        if not c.ok:
            from .notify import notify_users, staff_with
            notify_users([u for u in staff_with("xodimlar")],
                         f"Kassa {day:%d.%m.%Y}: farq bor (naqd {sv.fmt(c.cash_diff)}, karta {sv.fmt(c.card_diff)} so'm)",
                         f"{reverse('kassa')}?d={day}", exclude=request.user)
            messages.warning(request, "Kassa yopildi, lekin farq bor. Direktorga xabar berildi.")
        else:
            messages.success(request, "Kassa yopildi, farq yo'q")
        return redirect(f"{reverse('kassa')}?d={day}")
    history = list(CashClose.objects.filter(filial_id=br).select_related("user")[:30])
    return render(request, "crm/kassa.html", {
        "section": "tolovlar", "day": day, "t": t, "total": sum(t.values()), "rows": rows, "closed": closed,
        "form": form, "history": history, "prev": day - timedelta(days=1), "next": day + timedelta(days=1),
        "is_today": day == sv.today(), "admin": is_director(request.user),
    })


@director_required
@require_POST
def kassa_reopen(request, pk):
    c = get_object_or_404(CashClose, pk=pk)
    day = c.date
    c.delete()
    from .views import log
    log(request, f"Kassa qayta ochildi: {day}")
    messages.success(request, "Kassa qayta ochildi")
    return redirect(f"{reverse('kassa')}?d={day}")
