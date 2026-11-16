from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import services as sv
from .management.commands.seed_demo import create_demo
from . import backup as bk
from .models import Attendance, Backup, Charge, Grade, Group, Lead, Lesson, Payment, Promo, Staff, Student

User = get_user_model()

PAGES = ["bugun", "dashboard", "lidlar", "talabalar", "guruhlar", "jadval", "davomat", "tolovlar",
         "vazifalar", "marketing", "hisobotlar", "xarajatlar", "xodimlar", "jurnal", "qidiruv", "zaxira", "parol"]


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


class AccessTest(TestCase):
    def setUp(self):
        self.boss = User.objects.create_superuser("boss", password="Kuchli-parol-123")
        self.t = User.objects.create_user("dilnoza", password="Kuchli-parol-123", first_name="Dilnoza", last_name="Karimova")
        Staff.objects.create(user=self.t, role="oqituvchi")
        self.mine = Group.objects.create(name="Mine", price=300000, teacher_user=self.t, days="Du-Chor-Ju",
                                         pay_model="fixed", pay_value=2000000)
        self.byname = Group.objects.create(name="ByName", price=300000, teacher="dilnoza karimova")
        self.other = Group.objects.create(name="Other", price=300000, teacher="Sardor")
        self.s1 = Student.objects.create(name="Mening talabam", group=self.mine)
        self.s2 = Student.objects.create(name="Begona talaba", group=self.other)

    def test_teacher_name_autofill_and_scope(self):
        self.assertEqual(self.mine.teacher, "Dilnoza Karimova")
        self.assertEqual(sv.my_group_ids(self.t), {self.mine.id, self.byname.id})
        self.assertIsNone(sv.my_group_ids(self.boss))

    def test_teacher_sees_only_own(self):
        self.client.force_login(self.t)
        r = self.client.get(reverse("talabalar"))
        self.assertContains(r, "Mening talabam")
        self.assertNotContains(r, "Begona talaba")
        self.assertEqual(self.client.get(reverse("student_profile", args=[self.s2.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("student_profile", args=[self.s1.pk])).status_code, 200)
        r = self.client.get(reverse("davomat"))
        self.assertContains(r, "Mine")
        self.assertNotContains(r, ">Other<")
        self.assertEqual(self.client.get(reverse("student_edit", args=[self.s1.pk])).status_code, 302)
        r = self.client.get(reverse("kabinet"))
        self.assertContains(r, "2\xa0000\xa0000")
        self.assertEqual(self.client.get(reverse("home"))["Location"], reverse("kabinet"))

    def test_director_views_teacher_cabinet(self):
        self.client.force_login(self.boss)
        r = self.client.get(reverse("kabinet") + f"?t={self.t.pk}")
        self.assertContains(r, "Mine")
        self.assertEqual(self.client.get(reverse("kabinet")).status_code, 200)

    def test_custom_sections(self):
        self.client.force_login(self.boss)
        r = self.client.post(reverse("staff_edit", args=[self.t.pk]), {
            "first_name": "Dilnoza", "last_name": "Karimova", "role": "administrator",
            "custom": "on", "sections": ["lidlar", "hisobotlar"]})
        self.assertEqual(r.status_code, 302)
        self.t.refresh_from_db()
        self.assertEqual(self.t.staff.sections, ["lidlar", "hisobotlar"])
        bad = self.client.post(reverse("staff_edit", args=[self.t.pk]), {
            "first_name": "D", "role": "administrator", "custom": "on", "sections": ["xodimlar"]})
        self.assertEqual(bad.status_code, 200)  # xodimlar faqat direktorga, berib bo'lmaydi
        self.client.force_login(self.t)
        self.assertEqual(self.client.get(reverse("hisobotlar")).status_code, 200)
        self.assertEqual(self.client.get(reverse("lidlar")).status_code, 200)
        for name in ["talabalar", "tolovlar", "xodimlar", "zaxira", "jurnal"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 302, name)

    def test_password_reset_and_change(self):
        self.client.force_login(self.boss)
        self.client.post(reverse("staff_password", args=[self.t.pk]), {"password": "Yangi-parol-456"})
        self.assertTrue(User.objects.get(pk=self.t.pk).check_password("Yangi-parol-456"))
        self.client.force_login(User.objects.get(pk=self.t.pk))
        r = self.client.post(reverse("parol"), {"old_password": "Yangi-parol-456",
                                                "new_password1": "Boshqa-parol-789", "new_password2": "Boshqa-parol-789"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.get(pk=self.t.pk).check_password("Boshqa-parol-789"))

    def test_block_and_restore_staff(self):
        self.client.force_login(self.boss)
        self.client.post(reverse("staff_remove", args=[self.t.pk]))
        self.assertFalse(User.objects.get(pk=self.t.pk).is_active)
        self.client.post(reverse("staff_restore", args=[self.t.pk]))
        self.assertTrue(User.objects.get(pk=self.t.pk).is_active)

    def test_teacher_cannot_backup(self):
        self.client.force_login(self.t)
        self.assertEqual(self.client.get(reverse("backup_download_now")).status_code, 302)
        self.assertEqual(self.client.post(reverse("backup_create")).status_code, 302)
        self.assertFalse(Backup.objects.filter(kind="manual").exists())


class BackupTest(Base):
    def test_roundtrip(self):
        create_demo()
        n_students, n_pay = Student.objects.count(), Payment.objects.count()
        b = bk.make_backup("manual")
        self.assertGreater(b.objects_count, 10)
        Student.objects.all().delete()
        Payment.objects.all().delete()
        r = self.client.post(reverse("backup_restore", args=[b.pk]), {"confirm": "tiklash"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Student.objects.count(), n_students)
        self.assertEqual(Payment.objects.count(), n_pay)
        self.assertTrue(Backup.objects.filter(kind="pre_restore").exists())
        # tiklashdan keyin yangi yozuv qo'shish (sequence to'g'ri)
        Student.objects.create(name="Yangi")

    def test_download_and_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        Group.objects.create(name="Zaxira guruhi", price=1)
        raw = self.client.get(reverse("backup_download_now")).content
        Group.objects.all().delete()
        f = SimpleUploadedFile("z.json.gz", raw, content_type="application/gzip")
        self.client.post(reverse("backup_restore_file"), {"confirm": "TIKLASH", "file": f})
        self.assertTrue(Group.objects.filter(name="Zaxira guruhi").exists())

    def test_bad_file_and_confirm(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        Group.objects.create(name="Qolsin", price=1)
        f = SimpleUploadedFile("z.json", b'{"x":1}')
        self.client.post(reverse("backup_restore_file"), {"confirm": "TIKLASH", "file": f})
        b = bk.make_backup()
        self.client.post(reverse("backup_restore", args=[b.pk]), {"confirm": "yo'q"})
        self.assertTrue(Group.objects.filter(name="Qolsin").exists())

    def test_daily_and_retention(self):
        Backup.objects.all().delete()
        self.assertIsNotNone(bk.ensure_daily_backup(force_check=True))
        self.assertIsNone(bk.ensure_daily_backup(force_check=True))
        for _ in range(bk.KEEP + 3):
            bk.make_backup()
        self.assertEqual(Backup.objects.count(), bk.KEEP)


class CsrfTest(TestCase):
    def setUp(self):
        User.objects.create_user("ali", password="Kuchli-parol-123")
        self.c = self.client_class(enforce_csrf_checks=True)

    def test_stale_login_form_redirects_back(self):
        r = self.c.post(reverse("login") + "?next=/talabalar/", {"username": "ali", "password": "Kuchli-parol-123"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], reverse("login") + "?next=/talabalar/")
        r = self.c.get(r["Location"])
        self.assertContains(r, "Sahifa eskirgan")

    def test_other_page_friendly_403(self):
        self.c.force_login(User.objects.get(username="ali"))
        r = self.c.post(reverse("parol"), {})
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "Sahifani yangilash", status_code=403)


class SecurityTest(TestCase):
    def setUp(self):
        self.boss = User.objects.create_superuser("boss", password="Kuchli-parol-123")
        self.u = User.objects.create_user("ali", password="Kuchli-parol-123")
        Staff.objects.create(user=self.u, role="administrator")

    def login(self, username="ali", password="Kuchli-parol-123"):
        return self.client.post(reverse("login"), {"username": username, "password": password})

    def test_lockout_and_unlock(self):
        from .models import LoginEvent
        for _ in range(5):
            self.assertEqual(self.login(password="xato").status_code, 200)
        self.assertEqual(LoginEvent.objects.filter(kind="fail").count(), 5)
        r = self.login()  # to'g'ri parol ham bloklangan
        self.assertContains(r, "daqiqadan keyin")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.client.force_login(self.boss)
        self.client.post(reverse("unlock"), {"username": "ali"})
        self.client.logout()
        self.assertEqual(self.login().status_code, 302)
        self.assertTrue(LoginEvent.objects.filter(kind="ok", user=self.u).exists())

    def test_two_factor(self):
        from . import security as sec
        self.client.force_login(self.u)
        self.assertEqual(self.client.get(reverse("xavfsizlik")).status_code, 200)
        secret = self.client.session["_2fa_setup_secret"]
        self.client.post(reverse("twofa_enable"), {"code": "000000" if sec.totp_now(secret) != "000000" else "111111"})
        self.assertFalse(Staff.objects.get(user=self.u).totp_enabled)
        self.client.post(reverse("twofa_enable"), {"code": sec.totp_now(secret)})
        self.assertTrue(Staff.objects.get(user=self.u).totp_enabled)
        self.client.logout()
        r = self.login()
        self.assertEqual(r["Location"], reverse("login_2fa"))
        self.assertNotIn("_auth_user_id", self.client.session)
        r = self.client.post(reverse("login_2fa"), {"code": "12"})
        self.assertContains(r, "Kod noto")
        r = self.client.post(reverse("login_2fa"), {"code": sec.totp_now(secret)})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.u.pk)

    def test_totp_rfc_vector(self):
        from . import security as sec
        # RFC 6238 test vektori (SHA1, kalit "12345678901234567890", t=59 -> 94287082, 6 raqam: 287082)
        import base64
        secret = base64.b32encode(b"12345678901234567890").decode()
        self.assertEqual(sec.totp_now(secret, at=59), "287082")

    def test_headers_session_admin(self):
        from django.conf import settings
        self.client.force_login(self.boss)
        r = self.client.get(reverse("dashboard"))
        self.assertIn("frame-ancestors 'none'", r["Content-Security-Policy"])
        self.assertIn("no-store", r["Cache-Control"])
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertLessEqual(settings.SESSION_COOKIE_AGE, 4 * 3600)
        self.client.logout()
        r = self.client.get("/" + settings.ADMIN_URL + "login/")
        self.assertTrue(r["Location"].startswith(reverse("login")))
        self.assertEqual(self.client.get("/admin/").status_code, 404)

    def test_security_page_for_all_roles(self):
        t = User.objects.create_user("ustoz", password="Kuchli-parol-123")
        Staff.objects.create(user=t, role="oqituvchi")
        self.client.force_login(t)
        r = self.client.get(reverse("xavfsizlik"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Barcha kirishlar tarixi")
        self.client.force_login(self.boss)
        self.assertContains(self.client.get(reverse("xavfsizlik")), "Barcha kirishlar tarixi")

    def test_offsite_send(self):
        from unittest import mock
        b = bk.make_backup("manual")
        env = {"BACKUP_TELEGRAM_BOT_TOKEN": "x", "BACKUP_TELEGRAM_CHAT_ID": "1"}
        with mock.patch.dict("os.environ", env), mock.patch.object(bk, "_send_telegram") as st:
            done, errors = bk.send_offsite(b.pk)
        st.assert_called_once()
        self.assertEqual(done, ["telegram"])
        b.refresh_from_db()
        self.assertEqual(b.sent, "telegram")


class DesignTest(Base):
    def test_calendar_pwa_dashboard(self):
        create_demo()
        r = self.client.get(reverse("jadval") + "?v=kal")
        self.assertContains(r, 'class="calev')
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Davomat dinamikasi")
        self.assertContains(r, "To'lov yig'ilishi")
        m = self.client.get(reverse("manifest")).json()
        self.assertEqual(m["display"], "standalone")
        sw = self.client.get(reverse("sw"))
        self.assertEqual(sw["Service-Worker-Allowed"], "/")
        self.client.logout()
        self.assertEqual(self.client.get(reverse("offline")).status_code, 200)
        self.assertEqual(self.client.get(reverse("manifest")).status_code, 200)

    def test_salary_paid_status(self):
        from .models import Expense
        g = Group.objects.create(name="A", price=100000, teacher="Ali", pay_model="fixed", pay_value=500000)
        Student.objects.create(name="S", group=g)
        m = sv.now_month()
        Expense.objects.create(title="Avans", category="Avans", amount=200000, month=m, teacher="Ali")
        r = self.client.get(reverse("xarajatlar"))
        self.assertContains(r, "Qisman")
        self.assertContains(r, "300\xa0000")


class FeatureTest(Base):
    def test_public_form(self):
        import time
        from django.core.cache import cache
        cache.clear()
        Group.objects.create(name="A", price=1, course="Ingliz tili")
        self.client.logout()
        r = self.client.get(reverse("ariza"))
        self.assertContains(r, "Ingliz tili")
        ok = {"name": "Nodira", "phone": "+998 90 111 22 33", "course": "Ingliz tili", "ts": time.time() - 10}
        r = self.client.post(reverse("ariza"), ok)
        self.assertContains(r, "qabul qilindi")
        lead = Lead.objects.get(name="Nodira")
        self.assertEqual(lead.source, "Sayt (ariza)")
        # bot (honeypot) - lid yaratilmaydi
        self.client.post(reverse("ariza"), {**ok, "name": "Bot", "website": "spam"})
        self.assertFalse(Lead.objects.filter(name="Bot").exists())
        # cheklov
        for i in range(6):
            self.client.post(reverse("ariza"), {**ok, "name": f"X{i}"})
        self.assertEqual(Lead.objects.filter(name__startswith="X").count(), 4)
        from .models import Center
        c = Center.get(); c.public_form = False; c.save()
        self.assertEqual(self.client.get(reverse("ariza")).status_code, 404)

    def test_reminder_text(self):
        g = Group.objects.create(name="A", price=300000)
        s = Student.objects.create(name="Vali", group=g, parent="+99890", join_date=date(2020, 1, 1))
        r = self.client.get(reverse("tolovlar"))
        self.assertContains(r, "t.me/share")
        self.assertContains(r, "Vali uchun")
        d = sv.Data()
        msg = sv.reminder(d.center, s, g, 300000, sv.now_month())
        self.assertIn("300\\xa0000".encode().decode("unicode_escape"), msg)

    def test_exams(self):
        t = User.objects.create_user("ustoz", password="Kuchli-parol-123", first_name="Ali")
        Staff.objects.create(user=t, role="oqituvchi")
        g = Group.objects.create(name="A", price=1, teacher_user=t)
        other = Group.objects.create(name="Begona guruh", price=1)
        a = Student.objects.create(name="Aziz", group=g)
        b = Student.objects.create(name="Bobur", group=g)
        self.client.force_login(t)
        r = self.client.post(reverse("imtihon"), {"g": g.pk, "title": "Unit 1", "date": "2026-11-10",
                                                   "max_score": 50, f"s{a.pk}": "45", f"s{b.pk}": "30"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Grade.objects.filter(title="Unit 1").count(), 2)
        r = self.client.get(r["Location"])
        self.assertContains(r, "Reyting: Unit 1")
        self.assertContains(r, "1. Aziz")
        # boshqa guruh o'qituvchiga ko'rinmaydi
        r = self.client.get(reverse("imtihon") + f"?g={other.pk}")
        self.assertNotContains(r, "Begona guruh")

    def test_print_report(self):
        create_demo()
        r = self.client.get(reverse("hisobotlar") + "?chop=1")
        self.assertContains(r, "Oylik hisobot")
        self.assertContains(r, "window.print()")


class StatusHistoryTest(Base):
    """Qarz talaba holati tarixi bo'yicha: muzlatilgan oylar qarz emas, ketgan talabaning eski qarzi qoladi."""

    def setUp(self):
        super().setUp()
        self.g = Group.objects.create(name="A", price=100000)
        self.now = sv.now_month()
        self.m3 = sv.shift_month(self.now, -3)
        self.s = Student.objects.create(name="Vali", group=self.g, join_date=date.fromisoformat(self.m3 + "-01"))

    def _log(self, *pairs):
        from .models import StatusChange
        StatusChange.objects.filter(student=self.s).delete()
        for d_, st in pairs:
            StatusChange.objects.create(student=self.s, status=st, date=d_)

    def test_frozen_months_not_debt_after_return(self):
        m1, m2 = sv.shift_month(self.now, -2), sv.shift_month(self.now, -1)
        Payment.objects.create(student=self.s, amount=100000, month=self.m3)
        self._log((date.fromisoformat(self.m3 + "-01"), "faol"), (date.fromisoformat(m1 + "-01"), "muzlatilgan"),
                  (sv.today(), "faol"))
        Student.objects.filter(pk=self.s.pk).update(status="faol")
        d = sv.Data()
        self.s.refresh_from_db()
        self.assertEqual(d.debt_for(self.s, m1), 0)
        self.assertEqual(d.debt_for(self.s, m2), 0)
        self.assertEqual(d.total_debt(self.s), 100000)  # faqat joriy oy

    def test_left_student_keeps_old_debt(self):
        self._log((date.fromisoformat(self.m3 + "-01"), "faol"), (sv.today(), "tark"))
        Student.objects.filter(pk=self.s.pk).update(status="tark")
        self.s.refresh_from_db()
        d = sv.Data()
        self.assertEqual(d.debt_for(self.s, self.now), 0)
        self.assertEqual(d.total_debt(self.s), 300000)
        r = self.client.get(reverse("tolovlar"))
        self.assertContains(r, "Vali")
        # ketgan talaba ham qarzini to'lay oladi
        r = self.client.post(reverse("payment_add"), {"student": self.s.pk, "amount": 100000, "month": self.m3,
                                                      "method": "Naqd", "date": sv.today().isoformat()})
        self.assertEqual(r.status_code, 302)

    def test_save_records_history(self):
        from .models import StatusChange
        self.assertEqual(list(StatusChange.objects.filter(student=self.s).values_list("status", flat=True)), ["faol"])
        self.s.status = "muzlatilgan"
        self.s.save()
        self.client.post(reverse("student_activate", args=[self.s.pk]))
        self.assertEqual(list(StatusChange.objects.filter(student=self.s).values_list("status", flat=True)),
                         ["faol", "muzlatilgan", "faol"])
        self.s.refresh_from_db()
        self.assertIsNone(self.s.paused_at)

    def test_api_debt_bad_input(self):
        self.assertEqual(self.client.get(reverse("api_debt") + "?student=abc").status_code, 200)


class NewFeaturesTest(Base):
    def setUp(self):
        super().setUp()
        self.g = Group.objects.create(name="A", price=300000, days="Du-Chor-Ju", time="10:00-11:30")
        self.s = Student.objects.create(name="Vali", group=self.g, parent="+998 90 111 22 33",
                                        join_date=date(2020, 1, 1))

    def test_student_gets_parent_code(self):
        self.assertRegex(self.s.code, r"^\d{6}$")

    def test_staff_auto_login_and_code(self):
        r = self.client.post(reverse("xodimlar"), {"first_name": "Dilnoza", "last_name": "Karimova",
                                                   "role": "oqituvchi", "groups": [self.g.pk]})
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username="dilnoza.karimova")
        self.g.refresh_from_db()
        self.assertEqual(self.g.teacher_user, u)
        r = self.client.get(reverse("xodimlar"))
        self.assertContains(r, "dilnoza.karimova")
        code = self.client.session.get("new_cred") or {}
        # kod sahifada bir marta ko'rinadi va u bilan (katta harfli login bilan ham) kirish mumkin
        import re
        m = re.search(r'<b class="tnum">([^<]+)</b>', r.content.decode())
        self.client.logout()
        self.assertTrue(self.client.login(username="Dilnoza.Karimova", password=m.group(1)))

    def test_parent_cabinet(self):
        self.client.logout()
        r = self.client.post(reverse("parent_login"), {"phone": "90 111 22 33", "code": "000000"})
        self.assertContains(r, "Telefon yoki kod")
        r = self.client.post(reverse("parent_login"), {"phone": "+998901112233", "code": self.s.code})
        self.assertRedirects(r, reverse("parent_home"))
        self.assertContains(self.client.get(reverse("parent_home")), "Vali")

    def test_advance_payment_splits_months(self):
        now = sv.now_month()
        self.client.post(reverse("payment_add"), {"student": self.s.pk, "amount": 900000, "month": now,
                                                  "months": 3, "method": "Naqd", "date": sv.today().isoformat()})
        self.assertEqual(sorted(Payment.objects.values_list("month", "amount")),
                         [(now, 300000), (sv.shift_month(now, 1), 300000), (sv.shift_month(now, 2), 300000)])

    def test_prorate_first_month(self):
        from .models import Center
        c = Center.get()
        c.prorate_first_month = True
        c.save()
        s = Student.objects.create(name="Yangi", group=self.g, join_date=date(2026, 11, 16))  # dushanba
        d = sv.Data()
        amt = d.charge_amt(s, "2026-11")
        self.assertTrue(0 < amt < 300000)
        self.assertEqual(d.charge_amt(s, "2026-12"), 300000)

    def test_transfer_keeps_old_price_for_old_months(self):
        g2 = Group.objects.create(name="B", price=500000)
        m_old = sv.shift_month(sv.now_month(), -2)
        r = self.client.post(reverse("student_transfer", args=[self.s.pk]),
                             {"group": g2.pk, "date": sv.today().isoformat(), "keep_discount": "on"})
        self.assertEqual(r.status_code, 302)
        d = sv.Data()
        self.s.refresh_from_db()
        self.assertEqual(d.charge_amt(self.s, m_old), 300000)
        self.assertEqual(d.charge_amt(self.s, sv.now_month()), 500000)
        self.assertEqual(len(d.group_history(self.s)), 2)

    def test_cash_close_blocks_payments(self):
        from .models import CashClose
        r = self.client.post(reverse("kassa"), {"d": sv.today().isoformat(), "cash_real": 0, "card_real": 0})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(CashClose.objects.filter(date=sv.today()).exists())
        r = self.client.post(reverse("payment_add"), {"student": self.s.pk, "amount": 1000, "month": sv.now_month(),
                                                      "method": "Naqd", "date": sv.today().isoformat()})
        self.assertEqual(r.status_code, 200)  # forma xato bilan qaytadi
        self.assertFalse(Payment.objects.exists())

    def test_notifications_on_task(self):
        from .models import Notification
        other = User.objects.create_user("ali", password="Kuchli-parol-123")
        self.client.post(reverse("task_add"), {"title": "Qo'ng'iroq", "assignee": other.pk})
        self.assertEqual(Notification.objects.filter(user=other).count(), 1)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("bildirishnomalar")).status_code, 200)

    def test_telegram_link_and_absent(self):
        import os
        from unittest import mock
        from . import telegram as tg
        from .models import ParentChat
        sent = []
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "x", "TG_SYNC": "1"}), \
                mock.patch.object(tg, "api", side_effect=lambda m, **p: sent.append((m, p)) or {}):
            tg.handle({"message": {"chat": {"id": 77}, "text": f"/start {self.s.code}", "from": {"first_name": "Ona"}}})
            self.assertTrue(ParentChat.objects.filter(chat_id="77", student=self.s).exists())
            sent.clear()
            self.client.post(reverse("davomat"), {"g": self.g.pk, "d": sv.today().isoformat(),
                                                  f"s{self.s.pk}": "kelmadi"})
            self.assertTrue(any("kelmadi" in p.get("text", "") for _, p in sent))
            r = self.client.post(reverse("tg_hook", args=[tg.hook_secret()]), data="{}",
                                 content_type="application/json")
            self.assertEqual(r.status_code, 403)  # sarlavhadagi maxfiy kalitsiz

    def test_demo_seed_and_delete(self):
        from .management.commands.seed_demo import create_demo, delete_demo
        real = Student.objects.count()
        create_demo()
        self.assertTrue(User.objects.filter(username="demo.admin").exists())
        for name in ["dashboard", "tolovlar", "hisobotlar", "kassa", "zaxira", "imtihon"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        delete_demo()
        self.assertEqual(Student.objects.count(), real)
        self.assertFalse(User.objects.filter(username__startswith="demo.").exists())


class DemoSpeedTest(Base):
    def test_demo_uses_few_queries(self):
        """Render + Neon da har bir so'rov ~0.1 s: namuna 60 soniyalik limitga sig'ishi uchun so'rovlar kam bo'lsin."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as c:
            r = self.client.post(reverse("seed"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Student.objects.filter(is_demo=True).count() > 50)
        self.assertLess(len(c.captured_queries), 150)


class BranchFinanceTest(Base):
    def setUp(self):
        super().setUp()
        from .models import Branch
        self.b1, self.b2 = Branch.objects.create(name="Chilonzor"), Branch.objects.create(name="Yunusobod")
        self.g1 = Group.objects.create(name="G1", price=300000, filial=self.b1)
        self.g2 = Group.objects.create(name="G2", price=400000, filial=self.b2)
        self.s1 = Student.objects.create(name="Ali", group=self.g1, join_date=date(2020, 1, 1))
        self.s2 = Student.objects.create(name="Vali", group=self.g2, join_date=date(2020, 1, 1))
        self.admin = User.objects.create_user("adm", password="Kuchli-parol-123")
        Staff.objects.create(user=self.admin, role="administrator", filial=self.b2)

    def test_student_inherits_group_branch(self):
        self.assertEqual(self.s1.filial, self.b1)
        self.s1.group = self.g2
        self.s1.save()
        self.assertEqual(self.s1.filial, self.b2)

    def test_locked_admin_sees_only_own_branch(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("talabalar"))
        self.assertContains(r, "Vali")
        self.assertNotContains(r, "Ali<")
        self.assertEqual(self.client.get(reverse("student_profile", args=[self.s1.pk])).status_code, 404)
        # filialni almashtira olmaydi
        self.client.post(reverse("filial_switch"), {"filial": self.b1.pk})
        self.assertNotContains(self.client.get(reverse("talabalar")), "Ali<")
        # yangi lid avtomatik o'z filialiga
        self.client.post(reverse("lead_add"), {"name": "Yangi lid", "source": "Instagram", "status": "yangi"})
        self.assertEqual(Lead.objects.get(name="Yangi lid").filial, self.b2)

    def test_director_switches_branch(self):
        self.assertContains(self.client.get(reverse("talabalar")), "Ali")
        self.client.post(reverse("filial_switch"), {"filial": self.b1.pk})
        r = self.client.get(reverse("talabalar"))
        self.assertContains(r, "Ali")
        self.assertNotContains(r, "Vali")
        self.client.post(reverse("filial_switch"), {"filial": ""})
        self.assertContains(self.client.get(reverse("talabalar")), "Vali")

    def test_finance_page_and_leave_reason(self):
        r = self.client.post(reverse("student_edit", args=[self.s1.pk]),
                             {"name": "Ali", "group": self.g1.pk, "status": "tark", "discount": 0,
                              "join_date": "2020-01-01"})
        self.assertEqual(r.status_code, 200)  # sabab majburiy
        r = self.client.post(reverse("student_edit", args=[self.s1.pk]),
                             {"name": "Ali", "group": self.g1.pk, "status": "tark", "discount": 0,
                              "join_date": "2020-01-01", "leave_reason": "narx"})
        self.assertEqual(r.status_code, 302)
        from .models import StatusChange
        self.assertEqual(StatusChange.objects.filter(student=self.s1, status="tark").first().reason, "narx")
        r = self.client.get(reverse("moliya"))
        self.assertContains(r, "Narx qimmat")
        self.assertContains(r, "Chilonzor")

    def test_palette_search(self):
        r = self.client.get(reverse("palette") + "?q=val")
        self.assertEqual(r.json()["items"][0]["t"], "Vali")
        self.client.force_login(self.admin)
        self.assertEqual([x["t"] for x in self.client.get(reverse("palette") + "?q=ali").json()["items"]], ["Vali"])

    def test_branch_pages(self):
        for name in ["filiallar", "moliya", "kassa", "guruhlar", "hisobotlar", "dashboard"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
