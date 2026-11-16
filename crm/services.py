"""Hisob-kitoblar: qarz, reja, oylik, xavf, jadval, marketing statistikasi.

JS versiyadagi funksiyalarning Python'dagi aynan nusxasi. Har bir so'rovda
`Data` obyektida kerakli ma'lumotlar bir marta yuklanadi va keshlanadi.
"""
import re
from collections import defaultdict
from datetime import date, timedelta
from functools import cached_property

from django.utils import timezone

from .models import (AdSpend, Attendance, Center, Charge, Expense, Group, Lead,
                     GroupChange, Lesson, Payment, Promo, StatusChange, Student)
from .roles import is_teacher_scoped

MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust",
          "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
SHORT = ["Yan", "Fev", "Mar", "Apr", "May", "Iyn", "Iyl", "Avg", "Sen", "Okt", "Noy", "Dek"]
DAYF = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


# ---------------------------------------------------------------- sana yordamchilari
def today():
    return timezone.localdate()


def mkey(d):
    return f"{d.year}-{d.month:02d}"


def now_month():
    return mkey(today())


def mlabel(k):
    y, m = k.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def shift_month(k, n):
    y, m = map(int, k.split("-"))
    idx = y * 12 + (m - 1) + n
    return f"{idx // 12}-{idx % 12 + 1:02d}"


def month_end(k):
    y, m = map(int, k.split("-"))
    return date(y + m // 12, m % 12 + 1, 1) - timedelta(days=1)


def lesson_days(g, k, since=None):
    """Guruhning k oyidagi dars kunlari (jadval bo'yicha); jadval bo'lmasa oyning barcha kunlari."""
    days = parse_days(g.days) if g else []
    y, m = map(int, k.split("-"))
    d, end, out = date(y, m, 1), month_end(k), []
    while d <= end:
        if (not days or d.weekday() in days) and (since is None or d >= since):
            out.append(d)
        d += timedelta(days=1)
    return out


def prorate(full, g, join):
    """Oy o'rtasida kelgan talaba uchun: qolgan darslar ulushi, 1000 so'mgacha yaxlitlangan."""
    k = mkey(join)
    total = len(lesson_days(g, k))
    left = len(lesson_days(g, k, since=join))
    if not total or left >= total:
        return full
    return int(round(full * left / total / 1000) * 1000)


def day_closed(day, student=None):
    """Shu kun kassasi yopilganmi: umumiy kassa yoki talaba filialining kassasi."""
    from .models import CashClose
    fid = getattr(student, "filial_id", None)
    qs = CashClose.objects.filter(date=day)
    return qs.filter(filial=None).exists() or bool(fid and qs.filter(filial_id=fid).exists())


def valid_month(k, default=None):
    return k if k and MONTH_RE.match(k) else (default or now_month())


def month_options(selected=None, back=3, fwd=1):
    now = now_month()
    keys = [shift_month(now, n) for n in range(-back, fwd + 1)]
    if selected and selected not in keys:
        keys.append(selected)
    return [(k, mlabel(k)) for k in keys]


def pct(a, b):
    return round(a / b * 100) if b else 0


def fmt(n):
    try:
        n = int(round(float(n or 0)))
    except (TypeError, ValueError):
        return str(n)
    s = f"{abs(n):,}".replace(",", " ")
    return ("-" if n < 0 else "") + s


def compact(n):
    if n >= 1e6:
        return (f"{n / 1e6:.1f}").rstrip("0").rstrip(".") + " mln"
    if n >= 1e3:
        return f"{round(n / 1e3)} ming"
    return str(round(n))


# ---------------------------------------------------------------- jadval
DAY_MAP = [("du", 0), ("se", 1), ("ch", 2), ("pa", 3), ("ju", 4), ("sh", 5), ("ya", 6)]


def parse_days(s):
    out = []
    for t in re.split(r"[^a-z]+", str(s or "").lower()):
        if not t:
            continue
        for pref, i in DAY_MAP:
            if t.startswith(pref) and i not in out:
                out.append(i)
                break
    return out


def parse_time(s):
    s = str(s or "")
    r = re.search(r"(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})", s)
    if r:
        return int(r[1]) * 60 + int(r[2]), int(r[3]) * 60 + int(r[4])
    a = re.search(r"(\d{1,2})[:.](\d{2})", s)
    if a:
        st = int(a[1]) * 60 + int(a[2])
        return st, st + 90
    return None


def hm(n):
    return f"{n // 60:02d}:{n % 60:02d}"


def time_range(g):
    t = parse_time(g.time)
    return f"{hm(t[0])} - {hm(t[1])}" if t else "Vaqt yo'q"


def conflicts(groups):
    res, lst = defaultdict(list), []
    groups = list(groups)
    for i, a in enumerate(groups):
        for b in groups[i + 1:]:
            da, db = parse_days(a.days), parse_days(b.days)
            ta, tb = parse_time(a.time), parse_time(b.time)
            if not set(da) & set(db) or not ta or not tb or not (ta[0] < tb[1] and tb[0] < ta[1]):
                continue
            why = []
            if a.room and b.room and a.room.strip().lower() == b.room.strip().lower():
                why.append(f"bir xona ({a.room})")
            if a.teacher and b.teacher and a.teacher.strip().lower() == b.teacher.strip().lower():
                why.append(f"bir o'qituvchi ({a.teacher})")
            if not why:
                continue
            res[a.id].append(b.name)
            res[b.id].append(a.name)
            lst.append(f"{a.name} va {b.name}: {', '.join(why)}")
    return res, lst


# ---------------------------------------------------------------- asosiy hisob
def teacher_names(user):
    """O'qituvchi guruhga matn sifatida qanday yozilgan bo'lishi mumkin."""
    names = {user.get_full_name().strip().lower(), user.username.lower()}
    return {n for n in names if n}


def is_my_group(g, user):
    if g.teacher_user_id:
        return g.teacher_user_id == user.id
    return bool(g.teacher) and g.teacher.strip().lower() in teacher_names(user)


def my_group_ids(user):
    """O'qituvchiga tegishli guruhlar; cheklanmagan foydalanuvchi uchun None."""
    if user is None or not is_teacher_scoped(user):
        return None
    return {g.id for g in Group.objects.all() if is_my_group(g, user)}


class Data:
    """Bitta so'rov uchun ma'lumotlar va hisob-kitoblar.

    `user` o'qituvchi bo'lsa, guruhlar, talabalar va to'lovlar faqat uning
    guruhlari bilan cheklanadi.
    """

    def __init__(self, user=None):
        self.NOW = now_month()
        self.TODAY = today()
        self.user = user
        self.scope = my_group_ids(user)
        self.branch = getattr(user, "active_branch_id", None) if user is not None else None

    # --- yuklash
    def _br(self, rows):
        """Tanlangan filial bo'yicha filtr (filial bo'lmasa hammasi)."""
        return rows if not self.branch else [x for x in rows if x.filial_id == self.branch]

    @cached_property
    def groups(self):
        gs = self._br(list(Group.objects.all()))
        return gs if self.scope is None else [g for g in gs if g.id in self.scope]

    @cached_property
    def group_map(self):
        return {g.id: g for g in self.groups}

    @cached_property
    def students(self):
        ss = self._br(list(Student.objects.all()))
        return ss if self.scope is None else [x for x in ss if x.group_id in self.scope]

    @cached_property
    def student_map(self):
        return {s.id: s for s in self.students}

    @cached_property
    def leads(self):
        ls = list(Lead.objects.all())
        return ls if not self.branch else [x for x in ls if x.filial_id in (self.branch, None)]

    @cached_property
    def payments(self):
        ps = list(Payment.objects.all())
        if self.scope is None and not self.branch:
            return ps
        ids = set(self.student_map)
        return [p for p in ps if p.student_id in ids]

    @cached_property
    def expenses(self):
        return self._br(list(Expense.objects.all()))

    @cached_property
    def ads(self):
        return self._br(list(AdSpend.objects.all()))

    @cached_property
    def charges(self):
        return {(c.student_id, c.month): c.amount for c in Charge.objects.all()}

    @cached_property
    def center(self):
        return Center.get()

    @cached_property
    def lessons(self):
        return list(Lesson.objects.all().order_by("date"))

    @cached_property
    def marks(self):
        """{lesson_id: {student_id: status}}"""
        out = defaultdict(dict)
        for lid, sid, st in Attendance.objects.values_list("lesson_id", "student_id", "status"):
            out[lid][sid] = st
        return out

    @cached_property
    def all_groups(self):
        return {g.id: g for g in Group.objects.all()}

    @cached_property
    def group_log(self):
        out = defaultdict(list)
        for sid, d_, gid in GroupChange.objects.order_by("date", "id").values_list("student_id", "date", "group_id"):
            out[sid].append((d_, gid))
        return out

    def group_on(self, s, m):
        """Oy oxirida (joriy oy bo'lsa bugun) talaba qaysi guruhda bo'lgan."""
        log = self.group_log.get(s.id)
        if not log:
            return self.group_map.get(s.group_id) or (self.all_groups.get(s.group_id) if s.group_id else None)
        day = min(month_end(m), self.TODAY)
        gid = log[0][1]
        for d_, x in log:
            if d_ > day:
                break
            gid = x
        return self.all_groups.get(gid) if gid else None

    def group_history(self, s):
        """[(sana, guruh)] profil uchun."""
        return [(d_, self.all_groups.get(gid) if gid else None) for d_, gid in self.group_log.get(s.id, [])]

    @cached_property
    def status_log(self):
        """{student_id: [(date, status), ...]} sana bo'yicha."""
        out = defaultdict(list)
        for sid, d_, st in StatusChange.objects.order_by("date", "id").values_list("student_id", "date", "status"):
            out[sid].append((d_, st))
        return out

    def timeline(self, s):
        """Talaba holatlari tarixi. Tarix bo'lmasa (eski yozuvlar) hozirgi holatdan tiklanadi."""
        log = self.status_log.get(s.id)
        if log:
            return log
        start = s.join_date or date.min
        if s.status == "muzlatilgan" and s.paused_at:
            return [(start, "faol"), (s.paused_at, "muzlatilgan")]
        return [(start, s.status)]

    def status_on(self, s, day):
        tl = self.timeline(s)
        st = tl[0][1]
        for d_, x in tl:
            if d_ > day:
                break
            st = x
        return st

    def billable(self, s, m):
        """Oy uchun to'lov olinadimi: oy oxirida (joriy oy bo'lsa bugun) talaba faol bo'lgan bo'lsa."""
        return self.status_on(s, min(month_end(m), self.TODAY)) == "faol"

    @cached_property
    def paid_map(self):
        m = defaultdict(int)
        for p in self.payments:
            if p.student_id:
                m[(p.student_id, p.month)] += p.amount
        return m

    # --- yordamchi
    def group_of(self, s):
        return self.group_map.get(s.group_id)

    def active_in(self, g):
        return sum(1 for s in self.students if s.group_id == g.id and s.status == "faol")

    def waiting_in(self, g):
        return sum(1 for s in self.students if s.group_id == g.id and s.status == "navbat")

    def paid_for(self, s, m):
        return self.paid_map.get((s.id, m), 0)

    def charge_amt(self, s, m):
        if (s.id, m) in self.charges:
            return self.charges[(s.id, m)]
        g = self.group_on(s, m)
        if not g:
            return 0
        full = max(0, g.price - (s.discount or 0))
        if self.center.prorate_first_month and s.join_date and mkey(s.join_date) == m:
            return prorate(full, g, s.join_date)
        return full

    def joined_after(self, s, m):
        return bool(s.join_date and mkey(s.join_date) > m)

    def debt_for(self, s, m):
        if not self.group_on(s, m) or self.joined_after(s, m) or not self.billable(s, m):
            return 0
        return max(0, self.charge_amt(s, m) - self.paid_for(s, m))

    def debtors(self, m):
        rows = [{"s": s, "g": self.group_of(s), "debt": self.debt_for(s, m)} for s in self.students]
        return sorted([r for r in rows if r["debt"] > 0], key=lambda r: -r["debt"])

    def months_of(self, s):
        lo = shift_month(self.NOW, -11)
        a = mkey(s.join_date) if s.join_date else self.NOW
        if a < lo:
            a = lo
        out, k = [], a
        while k <= self.NOW and len(out) < 14:
            out.append(k)
            k = shift_month(k, 1)
        return out

    def total_debt(self, s):
        return sum(self.debt_for(s, m) for m in self.months_of(s))

    def overdue_months(self, s):
        return sum(1 for m in self.months_of(s) if m < self.NOW and self.debt_for(s, m) > 0)

    def expected_for(self, m):
        return sum(self.charge_amt(s, m) for s in self.students
                   if self.group_on(s, m) and not self.joined_after(s, m) and self.billable(s, m))

    def income(self, m):
        return sum(p.amount for p in self.payments if p.month == m)

    def month_exp(self, m):
        return sum(x.amount for x in self.expenses if x.month == m) + sum(a.amount for a in self.ads if a.month == m)

    # --- davomat
    def student_marks(self, s, since=None):
        """[(date, status)] sana bo'yicha tartiblangan."""
        out = []
        for l in self.lessons:
            st = self.marks.get(l.id, {}).get(s.id)
            if st and (since is None or l.date >= since):
                out.append((l.date, st))
        return out

    def risk_of(self, s):
        ms = [st for _, st in self.student_marks(s, since=self.TODAY - timedelta(days=30))]
        miss = ms.count("kelmadi")
        rate = ms.count("keldi") / len(ms) if ms else 1
        od = self.overdue_months(s)
        low = len(ms) >= 3 and rate < .6
        why = []
        if miss:
            why.append(f"{miss} marta kelmadi")
        if od:
            why.append(f"{od} oy qarz")
        if low:
            why.append(f"davomat {round(rate * 100)}%")
        sc = min(45, miss * 15) + min(40, od * 20) + (15 if low else 0)
        return {"s": s, "g": self.group_of(s), "sc": sc, "why": ", ".join(why)}

    def risks(self):
        rows = [self.risk_of(s) for s in self.students if s.status == "faol"]
        return sorted([r for r in rows if r["sc"] >= 25], key=lambda r: -r["sc"])

    # --- oylik
    def group_income(self, g, m):
        ids = {s.id for s in self.students if s.group_id == g.id}
        return sum(p.amount for p in self.payments if p.month == m and p.student_id in ids)

    def lessons_in(self, g, m):
        return sum(1 for l in self.lessons if l.group_id == g.id and mkey(l.date) == m)

    def group_salary(self, g, m):
        if g.pay_model == "fixed":
            return g.pay_value if self.active_in(g) else 0
        if g.pay_model == "perlesson":
            return g.pay_value * self.lessons_in(g, m)
        return round(self.group_income(g, m) * (g.teacher_pct or 0) / 100)

    def teacher_salaries(self, m):
        out = {}
        for g in self.groups:
            if not g.teacher:
                continue
            t = out.setdefault(g.teacher, {"name": g.teacher, "income": 0, "salary": 0})
            t["income"] += self.group_income(g, m)
            t["salary"] += self.group_salary(g, m)
        return list(out.values())

    # --- marketing
    def src_stats(self, m):
        rows = []
        lead_src = {l.id: l.source for l in self.leads}
        for src, _ in Lead.SOURCES:
            leads = [l for l in self.leads if l.source == src and mkey(timezone.localtime(l.created_at)) == m]
            won = sum(1 for l in leads if l.status == "yozildi")
            spend = sum(a.amount for a in self.ads if a.source == src and a.month == m)
            ids = {s.id for s in self.students if s.lead_id and lead_src.get(s.lead_id) == src}
            rev = sum(p.amount for p in self.payments if p.month == m and p.student_id in ids)
            n = len(leads)
            rows.append({"src": src, "n": n, "won": won, "spend": spend, "rev": rev,
                         "conv": pct(won, n), "cpl": round(spend / n) if n else 0,
                         "cpa": round(spend / won) if won else 0})
        return rows

    # --- paneller
    def due_leads(self):
        return sorted([l for l in self.leads if l.next_contact and l.next_contact <= self.TODAY and l.is_live],
                      key=lambda l: l.next_contact)

    def trials(self):
        return sorted([l for l in self.leads if l.trial_date and l.trial_date >= self.TODAY and l.is_live],
                      key=lambda l: l.trial_date)

    def waiting(self):
        rows = []
        for s in sorted([s for s in self.students if s.status == "navbat"], key=lambda s: s.created_at):
            g = self.group_of(s)
            rows.append({"s": s, "g": g, "free": bool(g and g.capacity > self.active_in(g))})
        return rows

    def birthdays(self, days=7):
        t0 = self.TODAY
        out = []
        for s in self.students:
            if not s.birth_date or s.status == "tark":
                continue
            b = s.birth_date
            try:
                n = b.replace(year=t0.year)
            except ValueError:  # 29-fevral
                n = date(t0.year, 3, 1)
            if n < t0:
                try:
                    n = b.replace(year=t0.year + 1)
                except ValueError:
                    n = date(t0.year + 1, 3, 1)
            diff = (n - t0).days
            if diff <= days:
                txt = (f"Hurmatli {s.name}! Tug'ilgan kuningiz bilan chin dildan tabriklaymiz. "
                       f"{self.center.name or 'Markaz'} jamoasi.")
                out.append({"s": s, "diff": diff, "age": n.year - b.year, "txt": txt})
        return sorted(out, key=lambda x: x["diff"])

    def returning(self):
        lim = self.TODAY + timedelta(days=7)
        return sorted([s for s in self.students if s.status == "muzlatilgan" and s.return_date and s.return_date <= lim],
                      key=lambda s: s.return_date)

    def paused_count(self):
        return sum(1 for s in self.students if s.status == "muzlatilgan")

    def course_ending(self):
        lo, hi = self.TODAY - timedelta(days=14), self.TODAY + timedelta(days=21)
        rows = []
        for g in sorted([g for g in self.groups if g.end_date and lo <= g.end_date <= hi], key=lambda g: g.end_date):
            left = (g.end_date - self.TODAY).days
            cls = "mute" if left < 0 else "bad" if left <= 7 else "warn"
            label = "Tugagan" if left < 0 else "Bugun" if left == 0 else f"{left} kun"
            rows.append({"g": g, "n": self.active_in(g), "cls": cls, "label": label})
        return rows

    def lessons_today(self, user=None):
        d = self.TODAY.weekday()
        rows = []
        for g in sorted([g for g in self.groups if d in parse_days(g.days)],
                        key=lambda g: (parse_time(g.time) or (0,))[0]):
            mine = bool(user and is_my_group(g, user))
            rows.append({"g": g, "time": time_range(g), "mine": mine})
        return rows

    def lead_counts(self):
        return {k: sum(1 for l in self.leads if l.status == k) for k, _ in Lead.STATUSES}

    def funnel(self):
        keys = ["yangi", "aloqa", "sinov", "yozildi"]
        live = [l for l in self.leads if l.status != "rad"]
        cum = [sum(1 for l in live if keys.index(l.status) >= i) for i in range(len(keys))]
        labels = dict(Lead.STATUSES)
        rows = []
        for i, k in enumerate(keys):
            w = max(22, cum[i] / cum[0] * 100) if cum[0] else 22
            rows.append({"label": labels[k], "n": cum[i], "w": round(w, 1),
                         "pct": (pct(cum[i], cum[i - 1]) if i and cum[i - 1] else (0 if i else None))})
        return {"rows": rows, "rad": sum(1 for l in self.leads if l.status == "rad")}

    def sources(self):
        rows = []
        for i, (src, _) in enumerate(Lead.SOURCES):
            t = [l for l in self.leads if l.source == src]
            if t:
                w = sum(1 for l in t if l.status == "yozildi")
                rows.append({"s": src, "i": i % 6, "n": len(t), "w": w, "pct": pct(w, len(t))})
        return rows

    def chart6(self, admin=True):
        out = []
        for n in range(-5, 1):
            k = shift_month(self.NOW, n)
            inc = self.income(k)
            exp = self.month_exp(k) if admin else 0
            out.append({"k": k, "label": mlabel(k), "short": SHORT[int(k[5:]) - 1],
                        "inc": inc, "exp": exp, "net": inc - exp})
        return out

    def series6(self):
        """Oxirgi 6 oy: reja (kutilgan) va yig'ilgan to'lov, davomat foizi."""
        by_month = defaultdict(lambda: [0, 0])
        for l in self.lessons:
            for st in self.marks.get(l.id, {}).values():
                c = by_month[mkey(l.date)]
                c[1] += 1
                c[0] += st == "keldi"
        out = []
        for n in range(-5, 1):
            k = shift_month(self.NOW, n)
            came, tot = by_month.get(k, (0, 0))
            out.append({"k": k, "label": mlabel(k), "short": SHORT[int(k[5:]) - 1],
                        "plan": self.expected_for(k), "got": self.income(k),
                        "att": pct(came, tot) if tot else 0})
        return out

    def expense_cats(self, m):
        tot = defaultdict(int)
        for x in self.expenses:
            if x.month == m:
                tot[x.category] += x.amount
        return [{"label": c, "v": v} for c, v in sorted(tot.items(), key=lambda kv: -kv[1]) if v]

    def month_series_students(self):
        return [sum(1 for s in self.students if s.join_date and mkey(s.join_date) == shift_month(self.NOW, n))
                for n in range(-5, 1)]

    def month_series_leads(self):
        return [sum(1 for l in self.leads if mkey(timezone.localtime(l.created_at)) == shift_month(self.NOW, n))
                for n in range(-5, 1)]


# ---------------------------------------------------------------- qoidalar
def apply_student_rules(student, previous=None):
    """Promokod chegirmasi va muzlatish sanasi. Xabar matnini qaytaradi."""
    msg = None
    g = student.group
    prev_applied = previous.promo_applied if previous else ""
    code = (student.promo or "").strip().upper()
    if code and code != prev_applied:
        p = Promo.objects.filter(code=code, active=True).first()
        if p and g:
            student.discount = round(g.price * p.value / 100) if p.type == "percent" else p.value
            student.promo = p.code
            student.promo_applied = p.code
            msg = f"Promokod qo'llandi: chegirma {fmt(student.discount)} so'm"
        else:
            msg = "Promokod topilmadi yoki guruh tanlanmagan"
    if student.status == "muzlatilgan":
        if not (previous and previous.status == "muzlatilgan" and previous.paused_at):
            student.paused_at = today()
    else:
        student.paused_at = None
    return msg


# ---------------------------------------------------------------- hujjatlar
def contract_text(d, s):
    c, g = d.center, d.group_of(s)
    price = d.charge_amt(s, d.NOW)
    gname = g.name if g else "[guruh]"
    course = (g.course or g.name) if g else "[kurs]"
    sched = ", ".join(x for x in [g.days, g.time] if x) if g else ""
    room = f", {g.room}" if g and g.room else ""
    disc = f" ({fmt(s.discount)} so'm chegirma hisobga olingan)" if s.discount else ""
    parent = f"\nOta-ona/vakil telefoni: {s.parent}" if s.parent else ""
    return f"""O'QITISH SHARTNOMASI
Sana: {d.TODAY}

{c.name or "[Markaz nomi]"} (keyingi o'rinlarda "Markaz"), direktor {c.director or "[F.I.Sh.]"} bir tomondan, va {s.name} (keyingi o'rinlarda "Talaba") ikkinchi tomondan quyidagi shartlarda shartnoma tuzdilar.

1. Markaz Talabaga "{course}" kursi bo'yicha {gname} guruhida ta'lim xizmatini ko'rsatadi.
2. Darslar: {sched or "[jadval]"}{room}.
3. Oylik to'lov: {fmt(price)} so'm{disc}.
4. To'lov muddati: [har oyning ... sanasigacha].
5. Tomonlarning boshqa huquq va majburiyatlari: [to'ldiring].

Markaz: {c.name or "[nomi]"}, {c.address or "[manzil]"}, {c.phone or "[telefon]"}
Talaba: {s.name}, {s.phone or "[telefon]"}{parent}

Imzolar: ______________   ______________

Eslatma: bu namunaviy shablon. Ishlatishdan oldin yurist bilan tekshiring."""


def cert_text(d, s):
    c, g = d.center, d.group_of(s)
    course = (g.course or g.name) if g else "[kurs]"
    return f"""SERTIFIKAT

{c.name or "[Markaz nomi]"}

Ushbu sertifikat {s.name} ga "{course}" kursini muvaffaqiyatli tamomlagani uchun topshirildi.

O'qituvchi: {(g.teacher if g else "") or "[F.I.Sh.]"}
Sana: {d.TODAY}
Direktor: {c.director or "[F.I.Sh.]"}"""


def receipt_text(d, p):
    c = d.center
    s = d.student_map.get(p.student_id)
    g = d.group_of(s) if s else None
    phone = f" · {c.phone}" if c.phone else ""
    return f"""KVITANSIYA
{c.name or "[Markaz nomi]"}{phone}

Sana: {p.date or d.TODAY}
Talaba: {s.name if s else "-"}
Guruh: {g.name if g else "-"}
Qaysi oy uchun: {mlabel(p.month)}
Summa: {fmt(p.amount)} so'm
To'lov turi: {p.method or "-"}

Qabul qildi: ______________"""


# ---------------------------------------------------------------- o'qituvchi kabineti
def cabinet(d, groups):
    """O'qituvchi kabineti: guruhlari, bugungi darslar, davomat va maosh (6 oy)."""
    m, tdy = d.NOW, d.TODAY.weekday()
    rows = []
    for g in groups:
        lessons = [l for l in d.lessons if l.group_id == g.id and mkey(l.date) == m]
        marks = [st for l in lessons for st in d.marks.get(l.id, {}).values()]
        came = sum(1 for st in marks if st == "keldi")
        days = parse_days(g.days)
        nxt = None
        for k in range(0, 7):
            if (tdy + k) % 7 in days:
                nxt = "Bugun" if k == 0 else "Ertaga" if k == 1 else DAYF[(tdy + k) % 7]
                break
        rows.append({"g": g, "n": d.active_in(g), "time": time_range(g), "today": tdy in days, "next": nxt,
                     "lessons": len(lessons), "att": pct(came, len(marks)) if marks else None,
                     "sal": d.group_salary(g, m), "model": g.get_pay_model_display()})
    six = []
    for n in range(-5, 1):
        k = shift_month(m, n)
        six.append({"k": k, "label": mlabel(k), "short": SHORT[int(k[5:]) - 1],
                    "sal": sum(d.group_salary(g, k) for g in groups)})
    tot_marks = sum(len(d.marks.get(l.id, {})) for l in d.lessons
                    if l.group_id in {g.id for g in groups} and mkey(l.date) == m)
    tot_came = sum(1 for l in d.lessons if l.group_id in {g.id for g in groups} and mkey(l.date) == m
                   for st in d.marks.get(l.id, {}).values() if st == "keldi")
    out = {
        "paid": sum(x.amount for x in d.expenses if x.month == m and x.category in ("Maosh", "Avans")
                    and x.teacher.strip().lower() in {g.teacher.strip().lower() for g in groups if g.teacher}),
        "rows": sorted(rows, key=lambda r: (not r["today"], (parse_time(r["g"].time) or (0,))[0])),
        "today_rows": [r for r in rows if r["today"]],
        "students": sum(r["n"] for r in rows), "sal": sum(r["sal"] for r in rows),
        "rest": 0,
        "lessons": sum(r["lessons"] for r in rows),
        "att": pct(tot_came, tot_marks) if tot_marks else None,
        "att_p": tot_came / tot_marks if tot_marks else 0,
        "att_label": f"{pct(tot_came, tot_marks)}%" if tot_marks else "-",
        "six": six, "now_label": mlabel(m),
    }
    out["rest"] = max(0, out["sal"] - out["paid"])
    return out



# ---------------------------------------------------------------- qarz eslatmasi
class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def reminder(center, s, g, debt, m):
    """Markaz sozlamasidagi shablon bo'yicha bitta talabaga eslatma matni."""
    tpl = center.reminder_text or ("Assalomu alaykum! {ism} uchun {oy} oyi to'lovi {summa} so'm hali to'lanmagan. "
                                   "{markaz}, {telefon}")
    return tpl.format_map(_Safe(ism=s.name, summa=fmt(debt), oy=mlabel(m), guruh=g.name if g else "",
                                markaz=center.name or "", telefon=center.phone or "")).strip()


def with_reminders(d, rows, m):
    from urllib.parse import quote
    for x in rows:
        x["msg"] = reminder(d.center, x["s"], x.get("g") or d.group_of(x["s"]), x["debt"], m)
        x["tg"] = "https://t.me/share/url?url=%20&text=" + quote(x["msg"])
        x["to"] = x["s"].parent or x["s"].phone
    return rows
