from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import services as sv
from .management.commands.seed_demo import create_demo
from .models import Attendance, Charge, Group, Lead, Lesson, Payment, Promo, Staff, Student

User = get_user_model()

PAGES = ["bugun", "dashboard", "lidlar", "talabalar", "guruhlar", "jadval", "davomat", "tolovlar",
         "vazifalar", "marketing", "hisobotlar", "xarajatlar", "xodimlar", "jurnal", "qidiruv"]


class Base(TestCase):
    def setUp(self):
        self.boss = User.objects.create_superuser("boss", password="Kuchli-parol-123")
        self.client.force_login(self.boss)


class PagesTest(Base):
    def test_login_required(self):
        self.client.logout()
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_all_pages_empty_and_seeded(self):
        for name in PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        create_demo()
        s = Student.objects.first()
        extra = [reverse(n) for n in PAGES] + [
            reverse("lidlar") + "?v=board", reverse("qidiruv") + "?q=Aziza",
            reverse("student_profile", args=[s.pk]), reverse("student_doc", args=[s.pk, "shartnoma"]),
            reverse("student_doc", args=[s.pk, "sertifikat"]), reverse("payment_add"),
            reverse("payment_receipt", args=[Payment.objects.first().pk]), reverse("export_xlsx"),
            reverse("import_data"), reverse("import_template"), reverse("lead_log", args=[Lead.objects.first().pk]),
            reverse("lead_to_student", args=[Lead.objects.first().pk]), reverse("center_edit"),
        ]
        for url in extra:
            self.assertEqual(self.client.get(url).status_code, 200, url)


class LogicTest(Base):
    def setUp(self):
        super().setUp()
        self.g = Group.objects.create(name="A", price=400000, capacity=2, teacher="Ali", teacher_pct=50)
        self.s = Student.objects.create(name="Vali", group=self.g, join_date=date(2020, 1, 1))

    def test_debt_and_payment(self):
        now = sv.now_month()
        d = sv.Data()
        self.assertEqual(d.debt_for(self.s, now), 400000)
        r = self.client.post(reverse("payment_add"), {"student": self.s.pk, "amount": 150000, "month": now,
                                                      "method": "Naqd", "date": sv.today().isoformat()})
        self.assertEqual(r.status_code, 302)
        d = sv.Data()
        self.assertEqual(d.debt_for(self.s, now), 250000)
        self.assertEqual(d.teacher_salaries(now)[0]["salary"], 75000)

    def test_freeze_month_and_refund(self):
        now = sv.now_month()
        self.client.post(reverse("freeze_month"), {"m": now})
        self.assertTrue(Charge.objects.filter(student=self.s, month=now, amount=400000).exists())
        p = Payment.objects.create(student=self.s, amount=400000, month=now)
        self.client.post(reverse("payment_refund", args=[p.pk]), {"amount": 100000, "note": "x"})
        self.assertEqual(sv.Data().debt_for(self.s, now), 100000)

    def test_promo_applied(self):
        Promo.objects.create(code="yangi20", type="percent", value=20)
        self.client.post(reverse("student_edit", args=[self.s.pk]), {
            "name": "Vali", "group": self.g.pk, "status": "faol", "discount": 0, "promo": "YANGI20",
            "join_date": "2020-01-01"})
        self.s.refresh_from_db()
        self.assertEqual(self.s.discount, 80000)

    def test_attendance(self):
        d = sv.today().isoformat()
        self.client.post(reverse("davomat"), {"g": self.g.pk, "d": d, "action": "marks", f"s{self.s.pk}": "kelmadi"})
        self.assertEqual(Attendance.objects.get().status, "kelmadi")
        self.client.post(reverse("davomat"), {"g": self.g.pk, "d": d, "action": "all"})
        self.assertEqual(Attendance.objects.get().status, "keldi")
        self.assertEqual(Lesson.objects.count(), 1)

    def test_lead_to_student(self):
        l = Lead.objects.create(name="Nigora", phone="+99890")
        self.client.post(reverse("lead_to_student", args=[l.pk]), {"name": "Nigora", "status": "faol", "discount": 0})
        l.refresh_from_db()
        self.assertEqual(l.status, "yozildi")
        self.assertTrue(Student.objects.filter(lead=l).exists())

    def test_schedule_conflict(self):
        a = Group(id=1, name="A", days="Du-Chor", time="18:00-19:30", room="1")
        b = Group(id=2, name="B", days="Dushanba", time="19:00-20:00", room="1")
        res, lst = sv.conflicts([a, b])
        self.assertEqual(len(lst), 1)


class RolesTest(TestCase):
    def test_teacher_cannot_see_money(self):
        u = User.objects.create_user("ustoz", password="Kuchli-parol-123")
        Staff.objects.create(user=u, role="oqituvchi")
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("davomat")).status_code, 200)
        for name in ["tolovlar", "xarajatlar", "hisobotlar", "xodimlar", "dashboard", "export_xlsx"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 302, name)
