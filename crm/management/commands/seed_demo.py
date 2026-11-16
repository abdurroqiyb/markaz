"""Namunaviy ma'lumot: markaz egasiga to'liq ishlagan CRM qanday ko'rinishini ko'rsatish uchun.

Oxirgi 6 oy: 4 o'qituvchi, 8 guruh, ~70 talaba (muzlatilgan, ketgan, kutayotganlar bilan), to'lovlar va qarzlar,
davomat, imtihonlar, lidlar va qo'ng'iroqlar, xarajatlar, reklama, promokod, vazifalar.
Har bir rol uchun demo login ham yaratiladi (DEMO_PASSWORD bilan).

Hammasi is_demo=True (yoki "demo." login) bilan belgilanadi va bitta tugma bilan o'chiriladi.
Haqiqiy ma'lumotlarga tegmaydi.
"""
import random
from datetime import date, datetime, time as dtime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from crm import services as sv
from crm.models import (AdSpend, Center, Attendance, Expense, Grade, Group, GroupChange, Lead, LeadCall, Lesson, Payment,
                        Promo, Script, Staff, StatusChange, Student, Task)

DEMO_USERS = [  # login, ism, familiya, rol
    ("demo.admin", "Gulnora", "Saidova", "administrator"),
    ("demo.marketolog", "Jasur", "Qodirov", "marketolog"),
    ("demo.dilnoza", "Dilnoza", "Karimova", "oqituvchi"),
    ("demo.sardor", "Sardor", "Aliyev", "oqituvchi"),
    ("demo.malika", "Malika", "Tursunova", "oqituvchi"),
    ("demo.bobur", "Bobur", "Rahimov", "oqituvchi"),
]
GROUPS = [  # nom, kurs, o'qituvchi login, kunlar, vaqt, xona, narx, sig'im, oylik turi, qiymat
    ("Ingliz tili Beginner", "Ingliz tili", "demo.dilnoza", "Du-Chor-Ju", "09:00-10:30", "1-xona", 350000, 12, "percent", 0),
    ("Ingliz tili A2 kechki", "Ingliz tili", "demo.dilnoza", "Du-Chor-Ju", "18:00-19:30", "2-xona", 400000, 12, "percent", 0),
    ("IELTS 6.5+", "IELTS", "demo.malika", "Se-Pay-Sha", "16:00-18:00", "2-xona", 650000, 10, "fixed", 3000000),
    ("Matematika 9-sinf", "Matematika", "demo.sardor", "Se-Pay-Sha", "15:00-16:30", "1-xona", 380000, 14, "percent", 0),
    ("Matematika DTM", "Matematika", "demo.sardor", "Du-Chor-Ju", "15:00-16:30", "3-xona", 450000, 14, "percent", 0),
    ("Rus tili", "Rus tili", "demo.malika", "Du-Chor-Ju", "11:00-12:30", "3-xona", 320000, 12, "perlesson", 40000),
    ("Kompyuter savodxonligi", "IT", "demo.bobur", "Se-Pay", "10:00-11:30", "Kompyuter xonasi", 300000, 10, "percent", 0),
    ("Python dasturlash", "IT", "demo.bobur", "Se-Pay-Sha", "17:00-19:00", "Kompyuter xonasi", 550000, 10, "percent", 0),
]
FIRST = ["Aziza", "Javohir", "Madina", "Bekzod", "Sevara", "Shahzod", "Nilufar", "Sardorbek", "Dilshoda", "Ulug'bek",
         "Mohinur", "Abdulloh", "Zarina", "Islom", "Feruza", "Doniyor", "Kamola", "Asadbek", "Shahlo", "Jahongir",
         "Munisa", "Otabek", "Charos", "Akmal", "Gulshan", "Behruz", "Sabina", "Muhammadali", "Laylo", "Temur",
         "Rayhona", "Sanjar", "Malika", "Firdavs", "Durdona", "Elyor", "Ziyoda", "Azizbek", "Nodira", "Hasan"]
LAST = ["Rahimov", "Tursunov", "Ergashev", "Olimov", "Yusupov", "Karimov", "Abdullayev", "Nazarov", "Qosimov",
        "Mirzayev", "Sobirov", "Xolmatov", "Ismoilov", "Jo'rayev", "Hamidov", "Salimov", "Umarov", "Islomov"]
LEAD_NOTES = ["Narxini so'radi, o'ylab ko'raman dedi", "Kechki guruh qiziqtiradi", "Ota-onasi bilan maslahatlashadi",
              "Sinov darsiga yozildi", "Chegirma bor-yo'qligini so'radi", "Do'sti tavsiya qilgan"]


def _name(rnd, female):
    f = rnd.choice(FIRST)
    l = rnd.choice(LAST)
    if f in ("Aziza", "Madina", "Sevara", "Nilufar", "Dilshoda", "Mohinur", "Zarina", "Feruza", "Kamola", "Shahlo",
             "Munisa", "Charos", "Gulshan", "Sabina", "Laylo", "Rayhona", "Malika", "Durdona", "Ziyoda", "Nodira"):
        l = l + "a"
    return f"{f} {l}"


def _phone(rnd):
    return f"+998 {rnd.choice(['90', '91', '93', '94', '97', '99', '88', '33'])} {rnd.randint(100, 999)} " \
           f"{rnd.randint(10, 99)} {rnd.randint(10, 99)}"


def has_demo():
    return Group.objects.filter(is_demo=True).exists()


@transaction.atomic
def create_demo(seed=2026):
    if has_demo():
        return
    rnd = random.Random(seed)
    today = sv.today()
    now = sv.now_month()
    User = get_user_model()
    from crm.forms import make_code
    from crm.models import Center
    center = Center.get()
    code = make_code()  # har safar yangi: demo loginlar ochiq saytda xavfsiz bo'lishi uchun
    center.demo_code = code
    center.save(update_fields=["demo_code"])

    # --- demo xodimlar
    users = {}
    for login, fn, ln, role in DEMO_USERS:
        u = User.objects.filter(username=login).first()
        if not u:
            u = User.objects.create_user(login, password=code, first_name=fn, last_name=ln)
        else:
            u.set_password(code)
            u.is_active = True
            u.save()
        Staff.objects.update_or_create(user=u, defaults={"role": role, "phone": _phone(rnd)})
        users[login] = u

    # --- guruhlar
    groups = []
    start = date.fromisoformat(sv.shift_month(now, -6) + "-01")
    for i, (name, course, t, days, time, room, price, cap, pm, pv) in enumerate(GROUPS):
        u = users[t]
        g = Group.objects.create(name=name, course=course, teacher=u.get_full_name(), teacher_user=u, days=days,
                                 time=time, room=room, price=price, capacity=cap, pay_model=pm, pay_value=pv,
                                 teacher_pct=35, start_date=start + timedelta(days=7 * (i % 3)),
                                 end_date=today + timedelta(days=10) if i == 6 else None, branch="", is_demo=True)
        groups.append(g)

    # --- lidlar (6 oy)
    sources = ["Instagram"] * 5 + ["Telegram"] * 3 + ["Tanish-bilishlar"] * 3 + ["Reklama", "Sayt (ariza)", "Boshqa"]
    leads = []
    for i in range(70):
        created = today - timedelta(days=rnd.randint(0, 175))
        st = rnd.choices(["yangi", "aloqa", "sinov", "yozildi", "rad"], [8, 10, 6, 14, 9])[0]
        if (today - created).days > 40 and st in ("yangi",):
            st = rnd.choice(["yozildi", "rad", "aloqa"])
        g = rnd.choice(groups)
        l = Lead.objects.create(name=_name(rnd, rnd.random() < .5), phone=_phone(rnd), course=g.course,
                                source=rnd.choice(sources), status=st, is_demo=True,
                                next_contact=today + timedelta(days=rnd.randint(-2, 3)) if st in ("yangi", "aloqa") else None,
                                trial_date=today + timedelta(days=rnd.randint(0, 4)) if st == "sinov" else None,
                                trial_result=rnd.choice(["keldi", "qiziqmadi", "kelmadi"]) if st in ("yozildi", "rad") and rnd.random() < .6 else "",
                                note=rnd.choice(LEAD_NOTES) if rnd.random() < .5 else "")
        Lead.objects.filter(pk=l.pk).update(created_at=timezone.make_aware(
            datetime.combine(created, dtime.min)) + timedelta(hours=rnd.randint(9, 19)))
        if st != "yangi":
            for k in range(rnd.randint(1, 3)):
                LeadCall.objects.create(lead=l, text=rnd.choice(LEAD_NOTES), date=created + timedelta(days=k * 2),
                                        is_demo=True)
        leads.append(l)
    won = [l for l in leads if l.status == "yozildi"]

    # --- talabalar
    students = []
    for i in range(86):
        g = groups[i % len(groups)]
        # markaz avvaldan ishlayapti: yarmi boshidan o'qiydi, qolganlari har oy qo'shilgan
        join = start + timedelta(days=rnd.randint(0, 15) if i % 2 == 0 else rnd.randint(16, 170))
        if join > today:
            join = today - timedelta(days=3)
        st = rnd.choices(["faol", "muzlatilgan", "tark", "navbat"], [60, 4, 7, 4])[0]
        female = rnd.random() < .5
        s = Student(name=_name(rnd, female), phone=_phone(rnd), parent=_phone(rnd), group=g, join_date=join,
                    status="faol", discount=rnd.choice([0] * 8 + [30000, 50000]), is_demo=True,
                    birth_date=date(today.year - rnd.randint(10, 22), rnd.randint(1, 12), rnd.randint(1, 28)),
                    lead=won.pop() if won and rnd.random() < .7 else None)
        if i < 2:  # bu haftada tug'ilgan kun
            s.birth_date = (today + timedelta(days=i * 2)).replace(year=today.year - 15)
        s.save()
        s._final = st
        students.append(s)

    # holat tarixi: muzlatish / ketish sanalari
    for s in students:
        st = s._final
        if st == "faol":
            continue
        StatusChange.objects.filter(student=s).delete()
        StatusChange.objects.create(student=s, status="faol", date=s.join_date)
        if st == "navbat":
            StatusChange.objects.filter(student=s).delete()
            StatusChange.objects.create(student=s, status="navbat", date=s.join_date)
            Student.objects.filter(pk=s.pk).update(status="navbat")
        else:
            when = min(today, s.join_date + timedelta(days=rnd.randint(25, 90)))
            StatusChange.objects.create(student=s, status=st, date=when)
            upd = {"status": st}
            if st == "muzlatilgan":
                upd.update(paused_at=when, return_date=today + timedelta(days=rnd.randint(1, 20)))
            Student.objects.filter(pk=s.pk).update(**upd)
        s.status = st

    # bitta talaba guruh almashtirgan
    mover = next(s for s in students if s.status == "faol" and s.join_date < today - timedelta(days=80))
    old_g, new_g = mover.group, next(g for g in groups if g.course == mover.group.course and g != mover.group) \
        if any(g.course == mover.group.course and g != mover.group for g in groups) else groups[0]
    GroupChange.objects.filter(student=mover).delete()
    GroupChange.objects.create(student=mover, group=old_g, date=mover.join_date)
    GroupChange.objects.create(student=mover, group=new_g, date=today - timedelta(days=40))
    Student.objects.filter(pk=mover.pk).update(group=new_g)

    # do'st olib kelgan
    for a, b in zip(students[3:9:2], students[10:16:2]):
        Student.objects.filter(pk=b.pk).update(referrer=a, referral_paid=rnd.random() < .5)

    # --- to'lovlar: ko'pchilik o'z vaqtida, ba'zilar qisman yoki kechikkan
    d = sv.Data()
    methods = ["Naqd"] * 5 + ["Karta"] * 4 + ["O'tkazma"]
    pays = []
    for s in Student.objects.filter(is_demo=True):
        s = d.student_map[s.pk]
        habit = rnd.choices(["good", "late", "partial", "bad"], [66, 18, 11, 5])[0]
        for m in d.months_of(s):
            amt = d.charge_amt(s, m)
            if not amt or not d.billable(s, m) or d.joined_after(s, m):
                continue
            first = date.fromisoformat(m + "-01")
            if m == now:
                if habit == "bad" or rnd.random() < .25:
                    continue
                pay_day = min(today, first + timedelta(days=rnd.randint(0, max(0, today.day - 1))))
            else:
                if habit == "bad" and rnd.random() < .6:
                    continue
                if habit == "late" and m == sv.shift_month(now, -1) and rnd.random() < .5:
                    continue
                pay_day = first + timedelta(days=rnd.randint(0, 12 if habit != "late" else 25))
            if habit == "partial" and rnd.random() < .5:
                amt = round(amt * rnd.choice([.5, .6, .7]) / 1000) * 1000
            pays.append(Payment(student=s, amount=amt, month=m, method=rnd.choice(methods),
                                date=min(pay_day, today), is_demo=True))
    # bugun kassaga kelgan to'lovlar (joriy oy uchun hali to'lamaganlardan)
    paid_now = {p.student_id for p in pays if p.month == now}
    for s in [x for x in d.students if x.status == "faol" and x.pk not in paid_now and d.group_of(x)][:5]:
        pays.append(Payment(student=s, amount=d.charge_amt(s, now), month=now, method=rnd.choice(methods),
                            date=today, is_demo=True))
    Payment.objects.bulk_create(pays)

    # oxirgi kunlar kassasi yopilgan (bittasida kichik farq bilan)
    from crm.models import CashClose
    for k in range(1, 6):
        day = today - timedelta(days=k)
        if CashClose.objects.filter(date=day).exists():
            continue
        t = {"Naqd": 0, "Karta": 0, "O'tkazma": 0}
        for p in pays:
            if p.date == day:
                t[p.method] += p.amount
        diff = -50000 if k == 3 and t["Naqd"] else 0
        CashClose.objects.create(date=day, cash_sys=t["Naqd"], card_sys=t["Karta"], transfer_sys=t["O'tkazma"],
                                 cash_real=t["Naqd"] + diff, card_real=t["Karta"], user=users["demo.admin"],
                                 note="Namuna" + (": qaytim xato berilgan" if diff else ""))

    # --- davomat va mavzular (oxirgi 6 hafta)
    topics = {"Ingliz tili": ["Present Simple", "Past Simple", "Yangi so'zlar", "Listening", "Speaking club"],
              "IELTS": ["Writing Task 1", "Writing Task 2", "Reading: True/False", "Listening Section 3", "Speaking Part 2"],
              "Matematika": ["Tenglamalar", "Funksiyalar", "Masalalar yechish", "Geometriya", "Test yechish"],
              "Rus tili": ["Kelishiklar", "Fe'l zamonlari", "Matn bilan ishlash", "So'zlashuv"],
              "IT": ["Word va Excel", "Python: o'zgaruvchilar", "Shartlar va sikllar", "Funksiyalar", "Amaliy loyiha"]}
    marks = []
    for g in groups:
        studs = [s for s in Student.objects.filter(group=g, status="faol")]
        weak = {s.pk for s in studs if rnd.random() < .12}
        day = today - timedelta(days=42)
        while day <= today:
            if day.weekday() in sv.parse_days(g.days):
                l = Lesson.objects.create(group=g, date=day, topic=rnd.choice(topics.get(g.course, ["Takrorlash"])),
                                          homework=f"{rnd.randint(10, 60)}-bet, {rnd.randint(1, 8)}-mashq"
                                          if rnd.random() < .8 else "", is_demo=True)
                for s in studs:
                    if s.join_date and s.join_date > day:
                        continue
                    p = .55 if s.pk in weak else .92
                    r = rnd.random()
                    st = "keldi" if r < p else "sababli" if r < p + (1 - p) / 2 else "kelmadi"
                    marks.append(Attendance(lesson=l, student=s, status=st))
            day += timedelta(days=1)
    Attendance.objects.bulk_create(marks)

    # --- imtihonlar (har guruhda 3 ta)
    grades = []
    for g in groups:
        studs = list(Student.objects.filter(group=g, status="faol"))
        for k, title in enumerate(["Oylik test", "Oraliq nazorat", "Mock imtihon"]):
            dt = today - timedelta(days=50 - k * 21)
            for s in studs:
                base = rnd.randint(45, 95)
                grades.append(Grade(student=s, group=g, title=title, score=min(100, base + k * rnd.randint(0, 6)),
                                    max_score=100, date=dt, is_demo=True))
    Grade.objects.bulk_create(grades)

    # --- xarajatlar va reklama
    exps = []
    for n in range(-5, 1):
        m = sv.shift_month(now, n)
        dt = min(today, date.fromisoformat(m + "-05"))
        exps += [Expense(title="Ofis ijarasi", category="Ijara", amount=4000000, month=m, date=dt, is_demo=True),
                 Expense(title="Elektr, gaz, internet", category="Kommunal", amount=rnd.randint(7, 11) * 100000,
                         month=m, date=dt, is_demo=True),
                 Expense(title="Administrator oyligi", category="Maosh", amount=3000000, month=m, date=dt,
                         is_demo=True)]
        if n < 0:
            for g in groups:
                sal = d.group_salary(g, m)
                if sal:
                    exps.append(Expense(title=f"Oylik: {g.teacher}", category="Maosh", amount=sal, month=m,
                                        date=min(today, date.fromisoformat(sv.shift_month(m, 1) + "-03")),
                                        teacher=g.teacher, is_demo=True))
        if n == -4:
            exps.append(Expense(title="Doska va proyektor", category="Jihozlar", amount=2500000, month=m, date=dt,
                                is_demo=True))
        for src, lo, hi in (("Instagram", 10, 18), ("Telegram", 3, 8), ("Reklama", 0, 6)):
            v = rnd.randint(lo, hi) * 100000
            if v:
                AdSpend.objects.create(source=src, amount=v, month=m, note="Target reklama", is_demo=True)
    Expense.objects.bulk_create(exps)

    # --- marketing: promokod, skript
    if not Promo.objects.filter(code="DEMO10").exists():
        Promo.objects.create(code="DEMO10", type="percent", value=10, note="Yangi o'quvchilar uchun", is_demo=True)
    Script.objects.create(title="Birinchi qo'ng'iroq", is_demo=True,
                          text="Assalomu alaykum! Siz bizning kurslarimizga ariza qoldirgan ekansiz. "
                               "Qaysi yo'nalish qiziqtiradi? Bepul sinov darsiga taklif qilamiz.")

    # --- vazifalar
    adm = users["demo.admin"]
    for title, who, dd, done in [("Qarzdorlarga qo'ng'iroq qilish", adm, 0, False),
                                 ("Yangi guruh uchun e'lon tayyorlash", users["demo.marketolog"], 2, False),
                                 ("Oraliq nazorat natijalarini kiritish", users["demo.dilnoza"], -1, False),
                                 ("Ota-onalar majlisini tashkil qilish", adm, 5, False),
                                 ("Oylik hisobotni tayyorlash", None, -3, True)]:
        Task.objects.create(title=title, assignee=who, due=today + timedelta(days=dd), done=done,
                            done_at=timezone.now() if done else None, is_demo=True)


@transaction.atomic
def delete_demo():
    from crm.models import CashClose
    CashClose.objects.filter(note__startswith="Namuna", user__username__startswith="demo.").delete()
    for m in (Attendance, ):
        m.objects.filter(lesson__is_demo=True).delete()
    for m in (Task, Script, Promo, AdSpend, Expense, Grade, Lesson, LeadCall, Payment, Student, Lead, Group):
        m.objects.filter(is_demo=True).delete()
    get_user_model().objects.filter(username__startswith="demo.", is_superuser=False).delete()
    from crm.models import Center
    Center.objects.filter(pk=1).update(demo_code="")


class Command(BaseCommand):
    help = "Namunaviy (demo) ma'lumot: 6 oylik to'liq markaz va har rol uchun demo login."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="Namunalarni o'chirish")

    def handle(self, *args, **opts):
        if opts["delete"]:
            delete_demo()
            self.stdout.write(self.style.SUCCESS("Namunalar o'chirildi."))
            return
        create_demo()
        self.stdout.write(self.style.SUCCESS(
            f"Namunaviy ma'lumot qo'shildi. Demo loginlar: {', '.join(u[0] for u in DEMO_USERS)}; "
            f"kod: {Center.get().demo_code}"))
