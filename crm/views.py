import csv
import io
import re
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services as sv
from .forms import (AdForm, CenterForm, ExpenseForm, GradeForm, GroupForm, ImportForm,
                    LeadCallForm, LeadForm, PaymentForm, PlanForm, PromoForm, RefundForm,
                    ScriptForm, StaffCreateForm, StudentForm, TaskForm)
from .models import (ActivityLog, AdSpend, Attendance, Center, Charge, Expense, Grade, Group,
                     Lead, LeadCall, Lesson, Payment, Promo, Script, Staff, Student, Task)
from .roles import (ROLES, allowed, can_money, director_required, home_section, is_director,
                    money_required, role_of, section_required)

User = get_user_model()


# ---------------------------------------------------------------- yordamchilar
def log(request, text):
    ActivityLog.objects.create(user=request.user if request.user.is_authenticated else None, text=str(text)[:300])


def back(request, default):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect(default)


def month_param(request):
    return sv.valid_month(request.GET.get("m"))


def month_nav(request, m):
    """Oldingi/keyingi oy havolalari uchun kontekst."""
    return {"m": m, "m_label": sv.mlabel(m), "m_prev": sv.shift_month(m, -1), "m_next": sv.shift_month(m, 1)}


def form_page(request, form, title, cancel, submit="Saqlash", extra=None, multipart=False):
    ctx = {"form": form, "title": title, "cancel": cancel, "submit": submit, "multipart": multipart,
           "next": request.GET.get("next") or request.POST.get("next") or ""}
    if extra:
        ctx.update(extra)
    return render(request, "crm/form.html", ctx)


def fill_item(d, g):
    n = d.active_in(g)
    p = n / g.capacity if g.capacity else 0
    return {"g": g, "n": n, "p": p, "col": "var(--warn)" if p >= 1 else "var(--accent)",
            "label": f"{round(p * 100)}%" if g.capacity else str(n)}


def verb(obj):
    return "o'zgartirildi" if obj else "qo'shildi"


def greet():
    h = timezone.localtime().hour
    return "Xayrli tong" if h < 12 else "Xayrli kun" if h < 18 else "Xayrli kech"


def first_name(user):
    return (user.first_name or user.username or "").split(" ")[0]


# ---------------------------------------------------------------- bosh sahifalar
@login_required
def home(request):
    return redirect(home_section(request.user))


@section_required("bugun")
def bugun(request):
    d = sv.Data()
    u = request.user
    my_tasks = Task.objects.filter(done=False).filter(Q(assignee=u) | Q(assignee__isnull=True))
    return render(request, "crm/bugun.html", {
        "section": "bugun", "d": d, "lead_ok": allowed(u, "lidlar"), "greet": greet(), "first": first_name(u), "role": ROLES[role_of(u)],
        "lessons_today": d.lessons_today(u), "my_tasks": sorted(my_tasks, key=lambda t: t.due or date.max)[:6],
        "due_leads": d.due_leads()[:6], "trials": d.trials()[:6], "bdays": d.birthdays()[:6],
        "debtors": d.debtors(d.NOW)[:5] if can_money(u) else [], "returning": d.returning()[:6],
        "paused": d.paused_count(), "ending": d.course_ending(),
    })


@section_required("dashboard")
def dashboard(request):
    d = sv.Data()
    u = request.user
    admin = is_director(u)
    faol = [s for s in d.students if s.status == "faol"]
    income = d.income(d.NOW)
    exp = d.month_exp(d.NOW) if admin else 0
    expected = d.expected_for(d.NOW)
    rate = min(1, income / expected) if expected else 0
    debt_rows = [(s, d.total_debt(s)) for s in faol]
    now = timezone.localtime()
    my_tasks = Task.objects.filter(done=False).filter(Q(assignee=u) | Q(assignee__isnull=True))
    chart = d.chart6(admin)
    ctx = {
        "section": "dashboard", "d": d, "admin": admin,
        "empty": not d.leads and not d.students and not d.groups,
        "has_demo": any(x.is_demo for x in d.groups + d.students + d.leads),
        "greet": greet(), "first": first_name(u),
        "date_line": f"{sv.DAYF[now.weekday()]}, {now.day} {sv.MONTHS[now.month - 1].lower()}",
        "now_label": sv.mlabel(d.NOW), "active": len(faol),
        "waiting_n": sum(1 for s in d.students if s.status == "navbat"),
        "due_n": len(d.due_leads()), "income": income, "exp": exp, "net": income - exp,
        "expected": expected, "rate": rate, "rate_pct": round(rate * 100),
        "debt_all": sum(t for _, t in debt_rows), "debt_n": sum(1 for _, t in debt_rows if t > 0),
        "new_leads": sum(1 for l in d.leads if l.status == "yangi"),
        "spark_students": d.month_series_students(), "spark_leads": d.month_series_leads(),
        "spark_inc": [c["inc"] for c in chart], "spark_exp": [c["exp"] for c in chart],
        "chart": chart, "sources": d.sources(), "funnel": d.funnel(),
        "group_fill": [fill_item(d, g) for g in d.groups],
        "rate_label": f"{round(rate * 100)}%" if expected else "-",
        "debtors": d.debtors(d.NOW)[:6], "risks": d.risks()[:6], "waiting": d.waiting()[:6],
        "due_leads": d.due_leads()[:6], "trials": d.trials()[:6], "bdays": d.birthdays()[:6],
        "returning": d.returning()[:6], "paused": d.paused_count(), "ending": d.course_ending(),
        "my_tasks": sorted(my_tasks, key=lambda t: t.due or date.max)[:6],
    }
    return render(request, "crm/dashboard.html", ctx)


# ---------------------------------------------------------------- lidlar
@section_required("lidlar")
def lidlar(request):
    q = request.GET.get("q", "").strip()
    f = request.GET.get("f", "all")
    v = request.GET.get("v", "list")
    all_leads = list(Lead.objects.all().prefetch_related("calls"))
    rows = [l for l in all_leads if (f == "all" or l.status == f) and
            (not q or q.lower() in f"{l.name} {l.phone} {l.course}".lower())]
    counts = {k: sum(1 for l in all_leads if l.status == k) for k, _ in Lead.STATUSES}
    chips = [("all", "Barchasi", None)] + [(k, t, counts[k]) for k, t in Lead.STATUSES]
    board = [{"k": k, "t": t, "cls": Lead.STATUS_CLS[k], "rows": [l for l in rows if l.status == k]}
             for k, t in Lead.STATUSES]
    return render(request, "crm/lidlar.html", {
        "section": "lidlar", "rows": rows, "total": len(all_leads), "q": q, "f": f, "v": v,
        "chips": chips, "board": board, "statuses": Lead.STATUSES, "today": sv.today(),
    })


@section_required("lidlar")
def lead_form(request, pk=None):
    obj = get_object_or_404(Lead, pk=pk) if pk else None
    form = LeadForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        l = form.save()
        log(request, f"Lid {verb(obj)}: {l.name}")
        messages.success(request, "Saqlandi")
        return back(request, "lidlar")
    return form_page(request, form, "Lidni tahrirlash" if obj else "Yangi lid", reverse("lidlar"))


@section_required("lidlar")
@require_POST
def lead_delete(request, pk):
    l = get_object_or_404(Lead, pk=pk)
    log(request, f"Lid o'chirildi: {l.name}")
    l.delete()
    messages.success(request, "O'chirildi")
    return back(request, "lidlar")


@section_required("lidlar")
@require_POST
def lead_status(request, pk):
    l = get_object_or_404(Lead, pk=pk)
    st = request.POST.get("status")
    if st in dict(Lead.STATUSES):
        l.status = st
        l.save(update_fields=["status"])
        log(request, f"Lid o'zgartirildi: {l.name}")
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"ok": True})
    return back(request, "lidlar")


@section_required("lidlar")
def lead_log(request, pk):
    l = get_object_or_404(Lead, pk=pk)
    form = LeadCallForm(request.POST or None, initial={"next_contact": l.next_contact})
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        c.lead = l
        c.date = sv.today()
        c.save()
        l.next_contact = form.cleaned_data.get("next_contact")
        if l.status == "yangi":
            l.status = "aloqa"
        l.save()
        log(request, f"Lid o'zgartirildi: {l.name} (aloqa yozildi)")
        messages.success(request, "Saqlandi")
        return redirect("lead_log", pk=l.pk)
    return render(request, "crm/lead_log.html", {"section": "lidlar", "lead": l, "calls": l.calls.all(),
                                                  "form": form})


@section_required("talabalar")
def lead_to_student(request, pk):
    l = get_object_or_404(Lead, pk=pk)
    return student_form(request, from_lead=l)


# ---------------------------------------------------------------- talabalar
@section_required("talabalar")
def talabalar(request):
    d = sv.Data()
    q = request.GET.get("q", "").strip()
    gf = request.GET.get("g", "all")
    rows = []
    for s in sorted(d.students, key=lambda s: s.created_at, reverse=True):
        if gf != "all" and str(s.group_id) != gf:
            continue
        if q and q.lower() not in f"{s.name} {s.phone}".lower():
            continue
        rows.append({"s": s, "g": d.group_of(s), "debt": d.debt_for(s, d.NOW)})
    return render(request, "crm/talabalar.html", {
        "section": "talabalar", "rows": rows, "q": q, "gf": gf, "groups": d.groups,
        "total": len(d.students), "active": sum(1 for s in d.students if s.status == "faol"),
        "money": can_money(request.user),
    })


@section_required("talabalar")
def student_form(request, pk=None, from_lead=None):
    obj = get_object_or_404(Student, pk=pk) if pk else None
    previous = Student.objects.get(pk=pk) if pk else None
    initial = {}
    if from_lead:
        initial = {"name": from_lead.name, "phone": from_lead.phone}
    form = StudentForm(request.POST or None, instance=obj, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            s = form.save(commit=False)
            msg = sv.apply_student_rules(s, previous)
            if from_lead:
                s.lead = from_lead
            s.save()
            if from_lead:
                from_lead.status = "yozildi"
                from_lead.save(update_fields=["status"])
        if msg:
            messages.info(request, msg)
        log(request, f"Talaba {verb(obj)}: {s.name}")
        messages.success(request, "Saqlandi")
        return back(request, "talabalar")
    title = "Talabani tahrirlash" if obj else "Yangi talaba"
    return form_page(request, form, title, reverse("talabalar"))


@section_required("talabalar")
@require_POST
def student_delete(request, pk):
    s = get_object_or_404(Student, pk=pk)
    log(request, f"Talaba o'chirildi: {s.name}")
    s.delete()
    messages.success(request, "O'chirildi")
    return back(request, "talabalar")


@section_required("talabalar")
@require_POST
def student_activate(request, pk):
    s = get_object_or_404(Student, pk=pk)
    s.status = "faol"
    s.save(update_fields=["status"])
    log(request, f"Talaba o'zgartirildi: {s.name} (faollashtirildi)")
    messages.success(request, f"{s.name} faollashtirildi")
    return back(request, "dashboard")


@section_required("talabalar")
def student_profile(request, pk):
    d = sv.Data()
    s = d.student_map.get(pk) or get_object_or_404(Student, pk=pk)
    g = d.group_of(s)
    marks = d.student_marks(s)
    came = sum(1 for _, st in marks if st == "keldi")
    grades = list(s.grades.all())
    avg = round(sum(x.pct for x in grades) / len(grades)) if grades else None
    risk = d.risk_of(s)
    return render(request, "crm/profile.html", {
        "section": "talabalar", "s": s, "g": g, "d": d, "money": can_money(request.user),
        "price": d.charge_amt(s, d.NOW) if g else 0, "debt": d.debt_for(s, d.NOW), "total_debt": d.total_debt(s),
        "now_label": sv.mlabel(d.NOW), "att_pct": sv.pct(came, len(marks)) if marks else None,
        "marks": marks[-24:], "grades": list(reversed(grades))[:6], "grade_spark": [x.pct for x in grades[-10:]],
        "avg": avg, "risk": risk if s.status == "faol" and risk["sc"] >= 25 else None,
        "payments": s.payments.all()[:8],
    })


@section_required("talabalar")
def student_doc(request, pk, kind):
    d = sv.Data()
    s = get_object_or_404(Student, pk=pk)
    if kind == "shartnoma":
        title, text = f"Shartnoma: {s.name}", sv.contract_text(d, s)
    else:
        title, text = f"Sertifikat: {s.name}", sv.cert_text(d, s)
    return render(request, "crm/doc.html", {"section": "talabalar", "title": title, "text": text,
                                             "cancel": reverse("student_profile", args=[s.pk])})


@section_required("talabalar")
def grade_add(request, pk):
    s = get_object_or_404(Student, pk=pk)
    form = GradeForm(request.POST or None, initial={"max_score": 100, "date": sv.today()})
    if request.method == "POST" and form.is_valid():
        gr = form.save(commit=False)
        gr.student, gr.group = s, s.group
        gr.save()
        log(request, f"Baho qo'shildi: {s.name} · {gr.title}")
        messages.success(request, "Saqlandi")
        return redirect("student_profile", pk=s.pk)
    return form_page(request, form, f"Baho: {s.name}", reverse("student_profile", args=[s.pk]))


@section_required("talabalar")
@require_POST
def grade_delete(request, pk):
    gr = get_object_or_404(Grade, pk=pk)
    sid = gr.student_id
    gr.delete()
    log(request, "Baho o'chirildi")
    return redirect("student_profile", pk=sid)


# ---------------------------------------------------------------- guruhlar va jadval
def branch_ctx(request, groups):
    br = request.GET.get("br", "")
    branches = sorted({g.branch for g in groups if g.branch})
    return br, branches


@section_required("guruhlar")
def guruhlar(request):
    d = sv.Data()
    br, branches = branch_ctx(request, d.groups)
    cf, _ = sv.conflicts(d.groups)
    rows = []
    for g in d.groups:
        if br and g.branch != br:
            continue
        rows.append({**fill_item(d, g), "wl": d.waiting_in(g), "conflict": g.id in cf})
    return render(request, "crm/guruhlar.html", {"section": "guruhlar", "rows": rows, "br": br,
                                                  "branches": branches, "total": len(d.groups)})


@section_required("guruhlar")
def group_form(request, pk=None):
    obj = get_object_or_404(Group, pk=pk) if pk else None
    form = GroupForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        g = form.save()
        log(request, f"Guruh {verb(obj)}: {g.name}")
        messages.success(request, "Saqlandi")
        return back(request, "guruhlar")
    return form_page(request, form, "Guruhni tahrirlash" if obj else "Yangi guruh", reverse("guruhlar"))


@section_required("guruhlar")
@require_POST
def group_delete(request, pk):
    g = get_object_or_404(Group, pk=pk)
    log(request, f"Guruh o'chirildi: {g.name}")
    g.delete()
    messages.success(request, "O'chirildi")
    return redirect("guruhlar")


@section_required("jadval")
def jadval(request):
    d = sv.Data()
    br, branches = branch_ctx(request, d.groups)
    gs = [g for g in d.groups if (not br or g.branch == br) and sv.parse_days(g.days)]
    cf, cf_list = sv.conflicts(d.groups)
    tdy = d.TODAY.weekday()
    days = []
    for i, dn in enumerate(sv.DAYF):
        items = sorted([g for g in gs if i in sv.parse_days(g.days)], key=lambda g: (sv.parse_time(g.time) or (0,))[0])
        days.append({"name": dn, "today": i == tdy,
                     "items": [{"g": g, "time": sv.time_range(g), "bad": g.id in cf} for g in items]})
    return render(request, "crm/jadval.html", {"section": "jadval", "days": days, "conflicts": cf_list,
                                                "br": br, "branches": branches, "has": bool(gs)})


# ---------------------------------------------------------------- davomat
ATT = Attendance.STATUSES


@section_required("davomat")
def davomat(request):
    groups = list(Group.objects.all())
    if not groups:
        return render(request, "crm/davomat.html", {"section": "davomat", "no_groups": True})
    src = request.POST if request.method == "POST" else request.GET
    try:
        g = next(x for x in groups if str(x.pk) == src.get("g"))
    except StopIteration:
        g = groups[0]
    try:
        day = date.fromisoformat(src.get("d", ""))
    except ValueError:
        day = sv.today()
    studs = list(Student.objects.filter(group=g, status="faol").order_by("name"))
    lesson = Lesson.objects.filter(group=g, date=day).first()
    url = f"{reverse('davomat')}?g={g.pk}&d={day.isoformat()}"

    if request.method == "POST":
        action = request.POST.get("action", "marks")
        with transaction.atomic():
            lesson, _ = Lesson.objects.get_or_create(group=g, date=day)
            if action == "text":
                lesson.topic = request.POST.get("topic", "").strip()[:300]
                lesson.homework = request.POST.get("homework", "").strip()[:300]
                lesson.save()
                messages.success(request, "Mavzu saqlandi")
            else:
                valid = dict(ATT)
                for s in studs:
                    v = "keldi" if action == "all" else request.POST.get(f"s{s.pk}")
                    if v in valid:
                        Attendance.objects.update_or_create(lesson=lesson, student=s, defaults={"status": v})
                messages.success(request, "Davomat saqlandi")
        log(request, f"Davomat: {g.name} · {day}")
        return redirect(url)

    marks = {m.student_id: m.status for m in lesson.marks.all()} if lesson else {}
    ym = sv.mkey(day)
    month_lessons = list(Lesson.objects.filter(group=g, date__year=day.year, date__month=day.month))
    mm = {}
    for a in Attendance.objects.filter(lesson__in=month_lessons):
        mm.setdefault(a.student_id, []).append(a.status)
    rows = [{"s": s, "mark": marks.get(s.pk), "came": mm.get(s.pk, []).count("keldi"), "tot": len(mm.get(s.pk, []))}
            for s in studs]
    cnt = {k: sum(1 for r in rows if r["mark"] == k) for k, _ in ATT}
    last = list(Lesson.objects.filter(group=g).order_by("-date")[:14])[::-1]
    lm = {}
    for a in Attendance.objects.filter(lesson__in=last):
        lm[(a.lesson_id, a.student_id)] = a.status
    labels = dict(ATT)
    heat = [{"s": s, "cells": [{"v": lm.get((l.pk, s.pk), "none"), "t": f"{l.date}: {labels.get(lm.get((l.pk, s.pk)), 'belgilanmagan')}"}
                               for l in last]} for s in studs]
    return render(request, "crm/davomat.html", {
        "section": "davomat", "groups": groups, "g": g, "day": day, "rows": rows, "cnt": cnt,
        "none": len(rows) - sum(cnt.values()), "lesson": lesson, "att": ATT, "m_label": sv.mlabel(ym),
        "heat": heat if last else None, "heat_n": len(last),
    })


# ---------------------------------------------------------------- to'lovlar
@money_required
def tolovlar(request):
    d = sv.Data()
    m = month_param(request)
    pays = sorted([p for p in d.payments if p.month == m], key=lambda p: (p.date, p.created_at), reverse=True)
    total = sum(p.amount for p in pays)
    ds = d.debtors(m)
    exp = d.expected_for(m)
    frozen = any(k[1] == m for k in d.charges)
    allrows = sorted([{"s": s, "t": d.total_debt(s), "od": d.overdue_months(s)}
                      for s in d.students if s.status == "faol"], key=lambda r: -r["t"])
    allrows = [r for r in allrows if r["t"] > 0][:12]
    meth = [(n, sum(p.amount for p in pays if p.method == n)) for n, _ in Payment.METHODS]
    mmx = max([1] + [v for _, v in meth])
    debt_text = "\n".join(
        f"Assalomu alaykum! {x['s'].name} uchun {sv.mlabel(m)} oyi to'lovidan {sv.fmt(x['debt'])} so'm qolgan."
        + (f" ({x['s'].parent or x['s'].phone})" if (x['s'].parent or x['s'].phone) else "") for x in ds)
    return render(request, "crm/tolovlar.html", {
        "section": "tolovlar", **month_nav(request, m), "pays": [{"p": p, "s": d.student_map.get(p.student_id)} for p in pays],
        "total": total, "debtors": ds, "dsum": sum(x["debt"] for x in ds), "expected": exp,
        "rate": min(1, total / exp) if exp else 0, "rate_label": f"{sv.pct(total, exp)}%", "frozen": frozen,
        "allrows": allrows, "meth": [(n, v, v / mmx * 100) for n, v in meth],
        "today_sum": sum(p.amount for p in d.payments if p.date == d.TODAY), "today": d.TODAY,
        "admin": is_director(request.user), "debt_text": debt_text,
    })


@money_required
def payment_add(request):
    m = sv.valid_month(request.GET.get("m") or request.POST.get("month"))
    if not Student.objects.filter(status="faol").exists():
        messages.error(request, "Avval faol talaba qo'shing")
        return redirect("talabalar")
    d = sv.Data()
    sid = request.GET.get("student")
    st = Student.objects.filter(pk=sid, status="faol").first() if sid else Student.objects.filter(status="faol").order_by("name").first()
    initial = {"student": st, "month": m, "method": "Naqd", "date": sv.today(),
               "amount": d.debt_for(st, m) or None if st else None}
    form = PaymentForm(request.POST or None, initial=initial, month=m)
    if request.method == "POST" and form.is_valid():
        p = form.save()
        log(request, f"To'lov qo'shildi: {p.student.name} {sv.fmt(p.amount)} so'm")
        messages.success(request, "To'lov qabul qilindi")
        return back(request, f"{reverse('tolovlar')}?m={p.month}")
    return form_page(request, form, "To'lov qabul qilish", reverse("tolovlar"),
                     extra={"debt_api": reverse("api_debt")})


@money_required
def api_debt(request):
    d = sv.Data()
    s = d.student_map.get(int(request.GET.get("student") or 0))
    m = sv.valid_month(request.GET.get("m"))
    return JsonResponse({"debt": d.debt_for(s, m) if s else 0})


@money_required
@require_POST
def payment_delete(request, pk):
    p = get_object_or_404(Payment, pk=pk)
    log(request, f"To'lov o'chirildi: {p.student.name if p.student else ''} {sv.fmt(p.amount)} so'm")
    m = p.month
    p.delete()
    messages.success(request, "O'chirildi")
    return back(request, f"{reverse('tolovlar')}?m={m}")


@director_required
def payment_refund(request, pk):
    p = get_object_or_404(Payment, pk=pk, refund=False, amount__gt=0)
    form = RefundForm(request.POST or None, payment=p, initial={"amount": p.amount})
    if request.method == "POST" and form.is_valid():
        Payment.objects.create(student=p.student, amount=-form.cleaned_data["amount"], month=p.month,
                               method=p.method, date=sv.today(), refund=True,
                               note=form.cleaned_data["note"], refund_of=p)
        log(request, f"To'lov qaytarildi: {p.student.name if p.student else ''} {sv.fmt(form.cleaned_data['amount'])} so'm")
        messages.success(request, "Qaytarish yozildi")
        return redirect(f"{reverse('tolovlar')}?m={p.month}")
    return form_page(request, form, f"To'lovni qaytarish: {p.student.name if p.student else ''}",
                     f"{reverse('tolovlar')}?m={p.month}")


@money_required
def payment_receipt(request, pk):
    p = get_object_or_404(Payment, pk=pk)
    return render(request, "crm/doc.html", {"section": "tolovlar", "title": "Kvitansiya",
                                             "text": sv.receipt_text(sv.Data(), p),
                                             "cancel": f"{reverse('tolovlar')}?m={p.month}"})


@director_required
@require_POST
def freeze_month(request):
    m = sv.valid_month(request.POST.get("m"))
    d = sv.Data()
    todo = [s for s in d.students if s.status == "faol" and d.group_of(s) and not d.joined_after(s, m)
            and (s.id, m) not in d.charges]
    if not todo:
        messages.info(request, f"{sv.mlabel(m)} uchun hisob allaqachon yozilgan")
    else:
        Charge.objects.bulk_create([Charge(student=s, month=m, amount=d.charge_amt(s, m)) for s in todo])
        log(request, f"{sv.mlabel(m)} oyi hisoblandi ({len(todo)} talaba)")
        messages.success(request, f"{len(todo)} ta talaba uchun hisoblandi")
    return redirect(f"{reverse('tolovlar')}?m={m}")


# ---------------------------------------------------------------- xarajatlar
@section_required("xarajatlar")
def xarajatlar(request):
    d = sv.Data()
    m = month_param(request)
    ex = sorted([x for x in d.expenses if x.month == m], key=lambda x: (x.date, x.created_at), reverse=True)
    inc = d.income(m)
    ex_sum = d.month_exp(m)
    sal = []
    for t in d.teacher_salaries(m):
        paid = sum(x.amount for x in ex if x.category in ("Maosh", "Avans") and x.teacher == t["name"])
        sal.append({**t, "paid": paid, "rest": max(0, t["salary"] - paid)})
    return render(request, "crm/xarajatlar.html", {"section": "xarajatlar", **month_nav(request, m), "ex": ex,
                                                    "inc": inc, "ex_sum": ex_sum, "profit": inc - ex_sum, "sal": sal})


@section_required("xarajatlar")
def expense_add(request):
    m = sv.valid_month(request.GET.get("m") or request.POST.get("month"))
    initial = {"category": request.GET.get("category", "Boshqa"), "month": m, "date": sv.today(),
               "title": request.GET.get("title", ""), "teacher": request.GET.get("teacher", ""),
               "amount": request.GET.get("amount") or None}
    form = ExpenseForm(request.POST or None, initial=initial, month=m)
    if request.method == "POST" and form.is_valid():
        x = form.save()
        log(request, f"Xarajat qo'shildi: {x.title}")
        messages.success(request, "Saqlandi")
        return redirect(f"{reverse('xarajatlar')}?m={x.month}")
    return form_page(request, form, "Xarajat qo'shish", f"{reverse('xarajatlar')}?m={m}")


@section_required("xarajatlar")
@require_POST
def expense_delete(request, pk):
    x = get_object_or_404(Expense, pk=pk)
    log(request, f"Xarajat o'chirildi: {x.title}")
    m = x.month
    x.delete()
    messages.success(request, "O'chirildi")
    return redirect(f"{reverse('xarajatlar')}?m={m}")


# ---------------------------------------------------------------- vazifalar
@section_required("vazifalar")
def vazifalar(request):
    f = request.GET.get("f", "mine")
    u = request.user
    qs = Task.objects.select_related("assignee")
    if f == "mine":
        rows = list(qs.filter(done=False).filter(Q(assignee=u) | Q(assignee__isnull=True)))
    elif f == "all":
        rows = list(qs.filter(done=False))
    else:
        rows = list(qs.filter(done=True).order_by("-done_at"))
    if f != "done":
        rows.sort(key=lambda t: (t.due or date.max, -t.created_at.timestamp()))
    late = Task.objects.filter(done=False, due__lt=sv.today()).count()
    return render(request, "crm/vazifalar.html", {"section": "vazifalar", "rows": rows, "f": f, "late": late,
                                                   "today": sv.today()})


@section_required("vazifalar")
def task_add(request):
    form = TaskForm(request.POST or None, initial={"assignee": request.user})
    if request.method == "POST" and form.is_valid():
        t = form.save(commit=False)
        t.created_by = request.user
        t.save()
        log(request, f"Vazifa qo'shildi: {t.title}")
        messages.success(request, "Saqlandi")
        return redirect("vazifalar")
    return form_page(request, form, "Yangi vazifa", reverse("vazifalar"))


@section_required("vazifalar")
@require_POST
def task_toggle(request, pk):
    t = get_object_or_404(Task, pk=pk)
    t.done = not t.done
    t.done_at = timezone.now() if t.done else None
    t.save(update_fields=["done", "done_at"])
    log(request, f"Vazifa o'zgartirildi: {t.title}")
    return back(request, "vazifalar")


@section_required("vazifalar")
@require_POST
def task_delete(request, pk):
    t = get_object_or_404(Task, pk=pk)
    log(request, f"Vazifa o'chirildi: {t.title}")
    t.delete()
    return back(request, "vazifalar")


# ---------------------------------------------------------------- marketing
@section_required("marketing")
def marketing(request):
    d = sv.Data()
    m = month_param(request)
    st = d.src_stats(m)
    tot = {k: sum(x[k] for x in st) for k in ("n", "won", "spend", "rev")}
    mx = max([1] + [x["n"] for x in st])
    for x in st:
        x["w"] = x["n"] / mx * 100
    bonus = d.center.referral_bonus
    refs = {}
    for s in d.students:
        if s.referrer_id and s.referrer_id in d.student_map:
            refs.setdefault(s.referrer_id, []).append(s)
    ref_rows = [{"r": d.student_map[rid], "arr": arr, "sum": len(arr) * bonus} for rid, arr in refs.items()]
    pend = sum(1 for arr in refs.values() for s in arr if not s.referral_paid)
    promos = []
    for p in Promo.objects.all():
        used = sum(1 for s in d.students if (s.promo or "").upper() == p.code.upper())
        promos.append({"p": p, "used": used})
    return render(request, "crm/marketing.html", {
        "section": "marketing", **month_nav(request, m), "st": st, "tot": tot,
        "tot_conv": sv.pct(tot["won"], tot["n"]),
        "cpl": round(tot["spend"] / tot["n"]) if tot["n"] and tot["spend"] else None,
        "cpa": round(tot["spend"] / tot["won"]) if tot["won"] and tot["spend"] else None,
        "ads": [a for a in d.ads if a.month == m], "promos": promos, "refs": ref_rows, "bonus": bonus,
        "pend_sum": pend * bonus, "scripts": Script.objects.all(), "admin": is_director(request.user),
    })


@section_required("marketing")
def ad_add(request):
    m = sv.valid_month(request.GET.get("m") or request.POST.get("month"))
    form = AdForm(request.POST or None, initial={"month": m, "source": "Instagram"}, month=m)
    if request.method == "POST" and form.is_valid():
        a = form.save()
        log(request, f"Reklama xarajati qo'shildi: {a.source} {sv.fmt(a.amount)} so'm")
        messages.success(request, "Saqlandi")
        return redirect(f"{reverse('marketing')}?m={a.month}")
    return form_page(request, form, "Reklama xarajati", f"{reverse('marketing')}?m={m}")


@section_required("marketing")
@require_POST
def ad_delete(request, pk):
    a = get_object_or_404(AdSpend, pk=pk)
    m = a.month
    log(request, f"Reklama xarajati o'chirildi: {a.source}")
    a.delete()
    return redirect(f"{reverse('marketing')}?m={m}")


@director_required
def promo_add(request):
    form = PromoForm(request.POST or None, initial={"type": "percent"})
    if request.method == "POST" and form.is_valid():
        p = form.save()
        log(request, f"Promokod qo'shildi: {p.code}")
        messages.success(request, "Saqlandi")
        return redirect("marketing")
    return form_page(request, form, "Yangi promokod", reverse("marketing"))


@director_required
@require_POST
def promo_toggle(request, pk):
    p = get_object_or_404(Promo, pk=pk)
    p.active = not p.active
    p.save(update_fields=["active"])
    log(request, f"Promokod o'zgartirildi: {p.code}")
    return back(request, "marketing")


@director_required
@require_POST
def promo_delete(request, pk):
    p = get_object_or_404(Promo, pk=pk)
    log(request, f"Promokod o'chirildi: {p.code}")
    p.delete()
    return back(request, "marketing")


@section_required("marketing")
@require_POST
def referral_paid(request, pk):
    s = get_object_or_404(Student, pk=pk)
    s.referral_paid = True
    s.save(update_fields=["referral_paid"])
    log(request, f"Talaba o'zgartirildi: {s.name} (bonus berildi)")
    return back(request, "marketing")


@section_required("marketing")
def script_add(request):
    form = ScriptForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        s = form.save()
        log(request, f"Skript qo'shildi: {s.title}")
        return redirect("marketing")
    return form_page(request, form, "Yangi skript", reverse("marketing"))


@section_required("marketing")
@require_POST
def script_delete(request, pk):
    s = get_object_or_404(Script, pk=pk)
    log(request, f"Skript o'chirildi: {s.title}")
    s.delete()
    return back(request, "marketing")


# ---------------------------------------------------------------- hisobotlar
@section_required("hisobotlar")
def hisobotlar(request):
    d = sv.Data()
    m = month_param(request)
    inc, exp = d.income(m), d.month_exp(m)
    c = d.center
    rows = sorted([{"g": g, "i": d.group_income(g, m), "sal": d.group_salary(g, m), "n": d.active_in(g)}
                   for g in d.groups], key=lambda r: -r["i"])
    mx = max([1] + [r["i"] for r in rows])
    for r in rows:
        r["rest"] = r["i"] - r["sal"]
        r["w"] = r["i"] / mx * 100
    tmap = {}
    for g in d.groups:
        if not g.teacher:
            continue
        t = tmap.setdefault(g.teacher, {"name": g.teacher, "act": 0, "left": 0, "inc": 0})
        t["act"] += d.active_in(g)
        t["left"] += sum(1 for s in d.students if s.group_id == g.id and s.status == "tark")
        t["inc"] += d.group_income(g, m)
    trs = sorted(tmap.values(), key=lambda t: -t["inc"])
    for t in trs:
        t["keep"] = sv.pct(t["act"], t["act"] + t["left"]) if t["act"] + t["left"] else None
    six = []
    for n in range(-5, 1):
        k = sv.shift_month(m, n)
        i, e = d.income(k), d.month_exp(k)
        six.append({"label": sv.mlabel(k), "i": i, "e": e, "net": i - e,
                    "n": sum(1 for p in d.payments if p.month == k and not p.refund and p.amount > 0)})
    return render(request, "crm/hisobotlar.html", {
        "section": "hisobotlar", **month_nav(request, m), "inc": inc, "exp": exp, "net": inc - exp,
        "margin": sv.pct(inc - exp, inc) if inc else None, "p_inc": c.plan_income, "p_exp": c.plan_expense,
        "inc_rate": min(1, inc / c.plan_income) if c.plan_income else 0, "inc_pct": f"{sv.pct(inc, c.plan_income)}%",
        "exp_rate": min(1, exp / c.plan_expense) if c.plan_expense else 0, "exp_pct": f"{sv.pct(exp, c.plan_expense)}%",
        "exp_col": "var(--bad)" if c.plan_expense and exp > c.plan_expense else "var(--warn)",
        "exp_over": bool(c.plan_expense and exp > c.plan_expense),
        "rows": rows, "trs": trs, "src": [x for x in d.src_stats(m) if x["n"] or x["spend"]], "six": six,
    })


@director_required
def plan_edit(request):
    c = Center.get()
    form = PlanForm(request.POST or None, instance=c)
    if request.method == "POST" and form.is_valid():
        form.save()
        log(request, "Oylik reja o'zgartirildi")
        messages.success(request, "Saqlandi")
        return redirect("hisobotlar")
    return form_page(request, form, "Oylik reja", reverse("hisobotlar"))


@director_required
def center_edit(request):
    c = Center.get()
    form = CenterForm(request.POST or None, instance=c)
    if request.method == "POST" and form.is_valid():
        form.save()
        log(request, "Markaz ma'lumotlari o'zgartirildi")
        messages.success(request, "Saqlandi")
        return redirect("dashboard")
    return form_page(request, form, "Markaz ma'lumotlari", reverse("dashboard"))


# ---------------------------------------------------------------- xodimlar va jurnal
@section_required("xodimlar")
def xodimlar(request):
    form = StaffCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        with transaction.atomic():
            u = User.objects.create_user(username=cd["username"], password=cd["password"],
                                         first_name=cd["first_name"], last_name=cd["last_name"])
            Staff.objects.create(user=u, role=cd["role"])
        log(request, f"Xodim qo'shildi: {u.get_full_name() or u.username} ({ROLES[cd['role']]})")
        messages.success(request, "Xodim qo'shildi")
        return redirect("xodimlar")
    users = User.objects.filter(is_active=True).select_related("staff").order_by("first_name", "username")
    rows = [{"u": u, "role": role_of(u), "super": u.is_superuser, "me": u == request.user} for u in users]
    return render(request, "crm/xodimlar.html", {"section": "xodimlar", "form": form, "rows": rows,
                                                  "roles": Staff.ROLES})


@section_required("xodimlar")
@require_POST
def staff_role(request, pk):
    u = get_object_or_404(User, pk=pk, is_superuser=False)
    role = request.POST.get("role")
    if role in ROLES:
        Staff.objects.update_or_create(user=u, defaults={"role": role})
        log(request, f"Xodim roli o'zgartirildi: {u.get_full_name() or u.username} - {ROLES[role]}")
        messages.success(request, "Rol o'zgartirildi")
    return redirect("xodimlar")


@section_required("xodimlar")
@require_POST
def staff_remove(request, pk):
    u = get_object_or_404(User, pk=pk, is_superuser=False)
    if u == request.user:
        messages.error(request, "O'zingizni olib tashlay olmaysiz")
        return redirect("xodimlar")
    u.is_active = False
    u.save(update_fields=["is_active"])
    log(request, f"Xodim olib tashlandi: {u.get_full_name() or u.username}")
    messages.success(request, "Xodim o'chirildi (kirish bloklandi)")
    return redirect("xodimlar")


@section_required("jurnal")
def jurnal(request):
    rows = ActivityLog.objects.select_related("user")[:200]
    return render(request, "crm/jurnal.html", {"section": "jurnal", "rows": rows})


# ---------------------------------------------------------------- qidiruv
def digits(x):
    return re.sub(r"\D", "", str(x or ""))


@section_required("qidiruv")
def qidiruv(request):
    q = request.GET.get("q", "").strip()
    ctx = {"section": "qidiruv", "q": q, "short": len(q) < 2}
    if len(q) >= 2:
        d = sv.Data()
        ql, ph = q.lower(), digits(q)

        def hit(*a):
            return ql in " ".join(str(x or "") for x in a).lower()

        def by_phone(p):
            return len(ph) >= 3 and ph in digits(p)

        ctx["students"] = [{"s": s, "g": d.group_of(s)} for s in d.students
                           if hit(s.name, s.phone, s.parent) or by_phone(s.phone) or by_phone(s.parent)][:8]
        ctx["leads"] = [l for l in d.leads if hit(l.name, l.phone, l.course) or by_phone(l.phone)][:8] \
            if allowed(request.user, "lidlar") else []
        ctx["groups"] = [{"g": g, "n": d.active_in(g)} for g in d.groups if hit(g.name, g.course, g.teacher, g.room)][:8]
        ctx["pays"] = sorted([{"p": p, "s": d.student_map[p.student_id]} for p in d.payments
                              if p.student_id in d.student_map and hit(d.student_map[p.student_id].name)],
                             key=lambda x: x["p"].date, reverse=True)[:6] if can_money(request.user) else []
        ctx["found"] = any(ctx[k] for k in ("students", "leads", "groups", "pays"))
    return render(request, "crm/qidiruv.html", ctx)


# ---------------------------------------------------------------- Excel eksport / import
def _xlsx_response(wb, filename):
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@money_required
def export_xlsx(request):
    from openpyxl import Workbook
    d = sv.Data()
    gn = lambda gid: d.group_map[gid].name if gid in d.group_map else ""
    lead_st, stu_st = dict(Lead.STATUSES), dict(Student.STATUSES)
    sheets = [
        ("Lidlar", ["Ism", "Telefon", "Kurs", "Manba", "Holati", "Keyingi aloqa", "Izoh"],
         [[l.name, l.phone, l.course, l.source, lead_st.get(l.status), l.next_contact, l.note] for l in d.leads]),
        ("Talabalar", ["Ism", "Telefon", "Ota-ona", "Guruh", "Holati", "Kelgan sana", "Chegirma", f"{sv.mlabel(d.NOW)} qarz"],
         [[s.name, s.phone, s.parent, gn(s.group_id), stu_st.get(s.status), s.join_date, s.discount, d.debt_for(s, d.NOW)]
          for s in d.students]),
        ("Guruhlar", ["Guruh", "Kurs", "O'qituvchi", "Kunlar", "Vaqt", "Xona", "Narx", "Sig'im", "Faol talaba"],
         [[g.name, g.course, g.teacher, g.days, g.time, g.room, g.price, g.capacity, d.active_in(g)] for g in d.groups]),
        ("To'lovlar", ["Sana", "Talaba", "Guruh", "Oy", "Summa", "Turi"],
         [[p.date, d.student_map[p.student_id].name if p.student_id in d.student_map else "",
           gn(d.student_map[p.student_id].group_id) if p.student_id in d.student_map else "", p.month, p.amount, p.method]
          for p in sorted(d.payments, key=lambda p: p.date, reverse=True)]),
        ("Davomat", ["Sana", "Guruh", "Talaba", "Holati"],
         [[a.lesson.date, a.lesson.group.name, a.student.name, a.status]
          for a in Attendance.objects.select_related("lesson__group", "student").order_by("-lesson__date")]),
    ]
    if is_director(request.user):
        sheets.append(("Xarajatlar", ["Sana", "Nomi", "Turkum", "Oy", "Summa", "O'qituvchi"],
                       [[x.date, x.title, x.category, x.month, x.amount, x.teacher] for x in d.expenses]))
    deb = sorted([(s, d.total_debt(s)) for s in d.students if s.status == "faol"], key=lambda x: -x[1])
    sheets.append(("Qarzdorlar", ["Talaba", "Guruh", "Telefon", "Ota-ona", "Kechikkan oylar", "Jami qarz"],
                   [[s.name, gn(s.group_id), s.phone, s.parent, d.overdue_months(s), t] for s, t in deb if t > 0]))
    sheets.append((f"Kassa {d.NOW}", ["To'lov turi", "Summa"],
                   [[mm, sum(p.amount for p in d.payments if p.month == d.NOW and p.method == mm)] for mm, _ in Payment.METHODS]))
    wb = Workbook()
    wb.remove(wb.active)
    for name, head, rows in sheets:
        ws = wb.create_sheet(name[:31])
        ws.append(head)
        for r in rows:
            ws.append(["" if v is None else v for v in r])
    return _xlsx_response(wb, f"markaz-crm-{d.TODAY}.xlsx")


IK = {"name": ["ism", "ism-familiya", "ism familiya", "ismi", "fio", "f.i.sh", "f.i.o", "name"],
      "phone": ["telefon", "tel", "phone", "raqam", "telefon raqam"],
      "parent": ["ota-ona", "ota ona", "ota-ona telefoni", "parent"], "group": ["guruh", "group"],
      "discount": ["chegirma", "discount"], "course": ["kurs", "course"], "source": ["manba", "source"]}


def _read_rows(f):
    name = f.name.lower()
    if name.endswith(".csv"):
        text = f.read().decode("utf-8-sig", errors="replace")
        return list(csv.DictReader(io.StringIO(text)))[:500]
    from openpyxl import load_workbook
    wb = load_workbook(f, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    head = [str(h or "").strip() for h in next(it, [])]
    rows = []
    for r in it:
        rows.append({head[i]: (v if v is not None else "") for i, v in enumerate(r) if i < len(head)})
        if len(rows) >= 500:
            break
    return rows


def _ik(row, key):
    for k, v in row.items():
        if str(k).strip().lower() in IK[key]:
            return str(v if v is not None else "").strip()
    return ""


@section_required("talabalar")
def import_data(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        kind = form.cleaned_data["kind"]
        try:
            rows = _read_rows(form.cleaned_data["file"])
        except Exception:
            messages.error(request, "Faylni o'qib bo'lmadi. .xlsx yoki .csv ekanini tekshiring.")
            return redirect("import_data")
        model = Student if kind == "students" else Lead
        seen = {digits(p) for p in model.objects.values_list("phone", flat=True) if digits(p)}
        groups = {g.name.strip().lower(): g for g in Group.objects.all()}
        sources = dict(Lead.SOURCES)
        objs, dup, empty, nog = [], 0, 0, 0
        for r in rows:
            name = _ik(r, "name")
            if not name:
                empty += 1
                continue
            ph = digits(_ik(r, "phone"))
            if ph and ph in seen:
                dup += 1
                continue
            if ph:
                seen.add(ph)
            if kind == "students":
                gname = _ik(r, "group").lower()
                g = groups.get(gname) if gname else None
                if gname and not g:
                    nog += 1
                objs.append(Student(name=name, phone=_ik(r, "phone"), parent=_ik(r, "parent"), group=g,
                                    status="faol", join_date=sv.today(),
                                    discount=int(digits(_ik(r, "discount")) or 0)))
            else:
                src = _ik(r, "source")
                objs.append(Lead(name=name, phone=_ik(r, "phone"), course=_ik(r, "course"),
                                 source=src if src in sources else "Boshqa", status="yangi"))
        model.objects.bulk_create(objs)
        if objs:
            log(request, f"Excel'dan import: {len(objs)} ta {'talaba' if kind == 'students' else 'lid'}")
        info = f"{len(objs)} ta yozuv qo'shildi"
        if dup:
            info += f", {dup} tasi takror (o'tkazib yuborildi)"
        if empty:
            info += f", {empty} ta qatorda ism yo'q"
        if nog:
            info += f". Guruhi topilmagan: {nog} ta (guruhsiz qo'shildi)"
        messages.success(request, info + ".")
        return redirect("talabalar" if kind == "students" else "lidlar")
    return form_page(request, form, "Excel'dan import", reverse("talabalar"), submit="Import qilish",
                     multipart=True, extra={"import_help": True})


@login_required
def import_template(request):
    from openpyxl import Workbook
    kind = request.GET.get("kind", "students")
    wb = Workbook()
    ws = wb.active
    ws.title = "Shablon"
    if kind == "leads":
        ws.append(["Ism", "Telefon", "Kurs", "Manba"])
        ws.append(["Nigora Hasanova", "+998 90 123 45 67", "Ingliz tili", "Instagram"])
    else:
        g = Group.objects.first()
        ws.append(["Ism", "Telefon", "Ota-ona", "Guruh", "Chegirma"])
        ws.append(["Aziza Rahimova", "+998 90 123 45 67", "+998 91 765 43 21", g.name if g else "Guruh nomi", 0])
    return _xlsx_response(wb, f"{'lidlar' if kind == 'leads' else 'talabalar'}-shablon.xlsx")


# ---------------------------------------------------------------- namunaviy ma'lumot
@director_required
@require_POST
def seed(request):
    from .management.commands.seed_demo import create_demo
    create_demo()
    messages.success(request, "Namunaviy ma'lumot qo'shildi")
    return redirect("dashboard")


@director_required
@require_POST
def unseed(request):
    for m in (Payment, Student, Lead, Group):
        m.objects.filter(is_demo=True).delete()
    messages.success(request, "Namunalar o'chirildi")
    return redirect("dashboard")
