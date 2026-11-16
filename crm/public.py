"""Ochiq ariza formasi: saytga, Instagram yoki Telegram profiliga qo'yiladi. Kirish talab qilinmaydi.

Yuborilgan ariza "Sayt (ariza)" manbali yangi lid bo'lib tushadi. Spamdan himoya: yashirin
maydon (honeypot), bir IP dan soatiga ko'pi bilan RATE ta ariza, minimal to'ldirish vaqti.
"""
import time

from django import forms
from django.core.cache import cache
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect

from .models import ActivityLog, Center, Group, Lead
from .security import client_ip

RATE = 5


class PublicLeadForm(forms.Form):
    name = forms.CharField(label="Ismingiz", max_length=200)
    phone = forms.CharField(label="Telefon raqamingiz", max_length=50)
    course = forms.ChoiceField(label="Qaysi kurs qiziqtiradi", required=False)
    note = forms.CharField(label="Izoh (ixtiyoriy)", required=False, max_length=500,
                           widget=forms.Textarea(attrs={"rows": 3}))
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))
    ts = forms.FloatField(widget=forms.HiddenInput, required=False)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        courses = sorted({g.course.strip() for g in Group.objects.all() if g.course.strip()})
        self.fields["course"].choices = [("", "Tanlang")] + [(c, c) for c in courses] + [("Boshqa", "Boshqa")]
        self.fields["phone"].widget.attrs.update({"inputmode": "tel", "placeholder": "+998 90 123 45 67",
                                                  "autocomplete": "tel"})
        self.fields["name"].widget.attrs.update({"autocomplete": "name"})

    def clean_phone(self):
        p = self.cleaned_data["phone"].strip()
        if sum(ch.isdigit() for ch in p) < 7:
            raise forms.ValidationError("Telefon raqamini to'liq yozing")
        return p


@csrf_protect
def ariza(request):
    center = Center.get()
    if not center.public_form:
        return render(request, "crm/public_form.html", {"center": center, "closed": True}, status=404)
    done = False
    form = PublicLeadForm(request.POST or None, initial={"ts": time.time()})
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        key = f"ariza:{client_ip(request)}"
        n = cache.get(key, 0)
        too_fast = cd.get("ts") and time.time() - cd["ts"] < 2
        if cd.get("website") or too_fast:
            done = True  # bot: indamay "qabul qilindi" deymiz
        elif n >= RATE:
            form.add_error(None, "Juda ko'p ariza yuborildi. Birozdan keyin qayta urinib ko'ring yoki qo'ng'iroq qiling.")
        else:
            cache.set(key, n + 1, 3600)
            lead = Lead.objects.create(name=cd["name"].strip(), phone=cd["phone"], course=cd.get("course") or "",
                                       source="Sayt (ariza)", status="yangi", next_contact=timezone.localdate(),
                                       note=cd.get("note", "").strip())
            ActivityLog.objects.create(user=None, text=f"Saytdan ariza: {lead.name} ({lead.phone})"[:300])
            try:
                from django.urls import reverse
                from .notify import notify_users, staff_with
                notify_users(staff_with("lidlar"), f"Saytdan yangi ariza: {lead.name} ({lead.phone})"
                             + (f", {lead.course}" if lead.course else ""), reverse("lead_log", args=[lead.pk]))
            except Exception:  # xabar yuborilmasa ham ariza saqlanadi
                pass
            done = True
    return render(request, "crm/public_form.html", {"center": center, "form": form, "done": done})
