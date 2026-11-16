"""Markaz CRM ma'lumotlar modellari.

HTML/JS versiyadagi kolleksiyalar (leads, students, groups, payments, attendance,
expenses, calls, settings, charges, log, grades, tasks, ads, promos, scripts)
shu yerda Django modellariga aylantirilgan.
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

MONTH_HELP = "YYYY-MM ko'rinishida, masalan 2026-11"


class TimeStamped(models.Model):
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)
    is_demo = models.BooleanField("Namunaviy", default=False, editable=False)

    class Meta:
        abstract = True


# ---------------------------------------------------------------- sozlamalar
class Center(models.Model):
    """Markaz ma'lumotlari va oylik reja (yagona yozuv)."""
    name = models.CharField("Markaz nomi", max_length=200, default="O'quv markaz")
    director = models.CharField("Direktor F.I.Sh.", max_length=200, blank=True)
    phone = models.CharField("Telefon", max_length=50, blank=True)
    address = models.CharField("Manzil", max_length=300, blank=True)
    referral_bonus = models.PositiveIntegerField("Do'st olib kelganlik bonusi (so'm)", default=0)
    plan_income = models.PositiveBigIntegerField("Tushum rejasi (so'm / oy)", default=0)
    plan_expense = models.PositiveBigIntegerField("Xarajat chegarasi (so'm / oy)", default=0)
    public_form = models.BooleanField("Ochiq ariza formasi yoqilgan", default=True)
    reminder_text = models.TextField(
        "Qarz eslatmasi matni", blank=True,
        default="Assalomu alaykum! {markaz} dan yozyapmiz. {ism} uchun {oy} oyi to'lovi {summa} so'm "
                "hali to'lanmagan. Iltimos, to'lovni amalga oshiring. Savollar bo'lsa: {telefon}. Rahmat!",
        help_text="O'zgaruvchilar: {ism} {summa} {oy} {guruh} {markaz} {telefon}")

    class Meta:
        verbose_name = "Markaz ma'lumotlari"
        verbose_name_plural = "Markaz ma'lumotlari"

    def __str__(self):
        return self.name

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Staff(models.Model):
    ROLES = [
        ("direktor", "Direktor"),
        ("administrator", "Administrator"),
        ("oqituvchi", "O'qituvchi"),
        ("marketolog", "Marketolog"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff")
    role = models.CharField("Rol", max_length=20, choices=ROLES, default="oqituvchi")
    phone = models.CharField("Telefon", max_length=50, blank=True)
    # Bo'sh bo'lsa rol bo'yicha standart bo'limlar; aks holda faqat shu ro'yxatdagilar ochiq.
    sections = models.JSONField("Ochiq bo'limlar", default=list, blank=True)
    totp_secret = models.CharField("2FA kaliti", max_length=64, blank=True, editable=False)
    totp_enabled = models.BooleanField("Ikki bosqichli kirish yoqilgan", default=False)

    class Meta:
        verbose_name = "Xodim"
        verbose_name_plural = "Xodimlar"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


# ---------------------------------------------------------------- guruhlar
class Group(TimeStamped):
    PAY_MODELS = [
        ("percent", "Ulush (% tushumdan)"),
        ("fixed", "Qat'iy oylik"),
        ("perlesson", "Har dars uchun"),
    ]
    name = models.CharField("Guruh nomi", max_length=200)
    course = models.CharField("Kurs", max_length=200, blank=True)
    teacher = models.CharField("O'qituvchi", max_length=200, blank=True)
    teacher_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="taught_groups", verbose_name="O'qituvchi hisobi",
                                     help_text="Tanlansa, o'qituvchi o'z kabinetida shu guruhni ko'radi")
    days = models.CharField("Dars kunlari", max_length=100, blank=True, help_text="Masalan: Du-Chor-Ju")
    time = models.CharField("Vaqti", max_length=50, blank=True, help_text="Masalan: 18:00-19:30")
    room = models.CharField("Xona", max_length=100, blank=True)
    capacity = models.PositiveIntegerField("Sig'im (o'rin)", default=12)
    teacher_pct = models.PositiveIntegerField("O'qituvchi ulushi (%)", default=40)
    price = models.PositiveIntegerField("Oylik narx (so'm)")
    branch = models.CharField("Filial", max_length=100, blank=True)
    pay_model = models.CharField("Ustoz oyligi turi", max_length=20, choices=PAY_MODELS, default="percent")
    pay_value = models.PositiveIntegerField("Qat'iy summa yoki dars narxi", default=0)
    start_date = models.DateField("Kurs boshlanishi", null=True, blank=True)
    end_date = models.DateField("Kurs tugashi", null=True, blank=True)

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *a, **kw):
        if self.teacher_user_id and not self.teacher.strip():
            u = self.teacher_user
            self.teacher = u.get_full_name() or u.username
        super().save(*a, **kw)


# ---------------------------------------------------------------- lidlar
class Lead(TimeStamped):
    STATUSES = [
        ("yangi", "Yangi"),
        ("aloqa", "Aloqada"),
        ("sinov", "Sinov darsi"),
        ("yozildi", "Yozildi"),
        ("rad", "Rad etdi"),
    ]
    STATUS_CLS = {"yangi": "info", "aloqa": "warn", "sinov": "warn", "yozildi": "good", "rad": "mute"}
    SOURCES = [(s, s) for s in ["Instagram", "Telegram", "Tanish-bilishlar", "Reklama", "Sayt (ariza)", "Boshqa"]]
    TRIAL_RESULTS = [
        ("", "Hali yo'q"),
        ("keldi", "Sinovga keldi, yoqdi"),
        ("qiziqmadi", "Keldi, qiziqmadi"),
        ("kelmadi", "Sinovga kelmadi"),
    ]
    TRIAL_CLS = {"keldi": "good", "qiziqmadi": "warn", "kelmadi": "bad"}

    name = models.CharField("Ism-familiya", max_length=200)
    phone = models.CharField("Telefon", max_length=50, blank=True)
    course = models.CharField("Qiziqqan kurs", max_length=200, blank=True)
    source = models.CharField("Manba", max_length=50, choices=SOURCES, default="Instagram")
    status = models.CharField("Holati", max_length=20, choices=STATUSES, default="yangi")
    next_contact = models.DateField("Keyingi aloqa sanasi", null=True, blank=True)
    trial_date = models.DateField("Sinov darsi sanasi", null=True, blank=True)
    trial_result = models.CharField("Sinov natijasi", max_length=20, choices=TRIAL_RESULTS, blank=True)
    note = models.TextField("Izoh", blank=True)

    class Meta:
        verbose_name = "Lid"
        verbose_name_plural = "Lidlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def is_live(self):
        return self.status not in ("yozildi", "rad")

    @property
    def status_cls(self):
        return self.STATUS_CLS.get(self.status, "mute")

    @property
    def trial_cls(self):
        return self.TRIAL_CLS.get(self.trial_result, "mute")


class LeadCall(TimeStamped):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="calls", verbose_name="Lid")
    text = models.TextField("Yozuv")
    date = models.DateField("Sana", default=timezone.localdate)

    class Meta:
        verbose_name = "Aloqa yozuvi"
        verbose_name_plural = "Aloqa tarixi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.lead} · {self.date}"


# ---------------------------------------------------------------- talabalar
class Student(TimeStamped):
    STATUSES = [
        ("faol", "Faol"),
        ("muzlatilgan", "Muzlatilgan"),
        ("tark", "Tark etgan"),
        ("navbat", "Kutmoqda"),
    ]
    STATUS_CLS = {"faol": "good", "muzlatilgan": "warn", "tark": "mute", "navbat": "info"}

    name = models.CharField("Ism-familiya", max_length=200)
    phone = models.CharField("Telefon", max_length=50, blank=True)
    parent = models.CharField("Ota-ona telefoni", max_length=50, blank=True)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="students", verbose_name="Guruh")
    join_date = models.DateField("Kelgan sana", default=timezone.localdate, null=True, blank=True)
    status = models.CharField("Holati", max_length=20, choices=STATUSES, default="faol")
    discount = models.PositiveIntegerField("Chegirma (so'm / oy)", default=0)
    promo = models.CharField("Promokod", max_length=50, blank=True)
    promo_applied = models.CharField(max_length=50, blank=True, editable=False)
    birth_date = models.DateField("Tug'ilgan sana", null=True, blank=True)
    return_date = models.DateField("Qaytish sanasi (muzlatilgan bo'lsa)", null=True, blank=True)
    paused_at = models.DateField("Muzlatilgan sana", null=True, blank=True, editable=False)
    referrer = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="referred", verbose_name="Kim olib keldi (talaba)")
    referral_paid = models.BooleanField("Bonus berilgan", default=False)
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="students", verbose_name="Qaysi liddan")

    class Meta:
        verbose_name = "Talaba"
        verbose_name_plural = "Talabalar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def status_cls(self):
        return self.STATUS_CLS.get(self.status, "mute")

    def save(self, *args, **kwargs):
        """Holat o'zgarsa tarixga yoziladi: qarz shu tarix bo'yicha hisoblanadi."""
        old = None
        if self.pk:
            old = Student.objects.filter(pk=self.pk).values_list("status", flat=True).first()
        super().save(*args, **kwargs)
        if old != self.status:
            day = timezone.localdate()
            if old is None:
                day = self.join_date or day
            elif not self.status_log.exists():
                # Eski yozuv: avvalgi holatni ham boshlang'ich nuqta sifatida saqlaymiz.
                start = self.join_date or day
                if old == "muzlatilgan" and self.paused_at:
                    StatusChange.objects.create(student=self, status="faol", date=min(start, self.paused_at))
                    start = self.paused_at
                StatusChange.objects.create(student=self, status=old, date=min(start, day))
            StatusChange.objects.create(student=self, status=self.status, date=day)


class StatusChange(models.Model):
    """Talaba holati tarixi: qaysi sanadan qaysi holatda bo'lgani."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="status_log", verbose_name="Talaba")
    status = models.CharField("Holati", max_length=20, choices=Student.STATUSES)
    date = models.DateField("Sanadan")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Holat o'zgarishi"
        verbose_name_plural = "Holatlar tarixi"
        ordering = ["date", "id"]

    def __str__(self):
        return f"{self.student} · {self.date} · {self.get_status_display()}"


class Payment(TimeStamped):
    METHODS = [(m, m) for m in ["Naqd", "Karta", "O'tkazma"]]
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, related_name="payments",
                                verbose_name="Talaba")
    amount = models.BigIntegerField("Summa (so'm)")
    month = models.CharField("Qaysi oy uchun", max_length=7, help_text=MONTH_HELP, db_index=True)
    method = models.CharField("To'lov turi", max_length=20, choices=METHODS, default="Naqd")
    date = models.DateField("Sana", default=timezone.localdate)
    refund = models.BooleanField("Qaytarish", default=False)
    refund_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="refunds", verbose_name="Qaysi to'lov qaytarildi")
    note = models.TextField("Izoh", blank=True)

    class Meta:
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.student} · {self.month} · {self.amount}"


class Charge(TimeStamped):
    """Oy hisoblanganda (oyni muzlatish) talabaga yozilgan summa."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="charges", verbose_name="Talaba")
    month = models.CharField("Oy", max_length=7, help_text=MONTH_HELP)
    amount = models.PositiveIntegerField("Summa")

    class Meta:
        verbose_name = "Oylik hisob"
        verbose_name_plural = "Oylik hisoblar"
        unique_together = [("student", "month")]

    def __str__(self):
        return f"{self.student} · {self.month}"


# ---------------------------------------------------------------- davomat
class Lesson(TimeStamped):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="lessons", verbose_name="Guruh")
    date = models.DateField("Dars sanasi")
    topic = models.CharField("Mavzu", max_length=300, blank=True)
    homework = models.CharField("Uy vazifasi", max_length=300, blank=True)

    class Meta:
        verbose_name = "Dars"
        verbose_name_plural = "Darslar (davomat)"
        unique_together = [("group", "date")]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.group} · {self.date}"


class Attendance(models.Model):
    STATUSES = [("keldi", "Keldi"), ("sababli", "Sababli"), ("kelmadi", "Kelmadi")]
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="marks", verbose_name="Dars")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="marks", verbose_name="Talaba")
    status = models.CharField("Holati", max_length=10, choices=STATUSES)

    class Meta:
        verbose_name = "Davomat belgisi"
        verbose_name_plural = "Davomat belgilari"
        unique_together = [("lesson", "student")]

    def __str__(self):
        return f"{self.student} · {self.lesson.date} · {self.status}"


class Grade(TimeStamped):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="grades", verbose_name="Talaba")
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Guruh")
    title = models.CharField("Nima uchun", max_length=200)
    score = models.PositiveIntegerField("Ball")
    max_score = models.PositiveIntegerField("Maksimal ball", default=100, validators=[MinValueValidator(1)])
    date = models.DateField("Sana", default=timezone.localdate)

    class Meta:
        verbose_name = "Baho"
        verbose_name_plural = "Baholar"
        ordering = ["date", "created_at"]

    def __str__(self):
        return f"{self.student} · {self.title}"

    @property
    def pct(self):
        return round(self.score / self.max_score * 100) if self.max_score else 0


# ---------------------------------------------------------------- moliya
class Expense(TimeStamped):
    CATEGORIES = [(c, c) for c in ["Ijara", "Maosh", "Avans", "Marketing", "Kommunal", "Jihozlar", "Boshqa"]]
    title = models.CharField("Nomi", max_length=200)
    category = models.CharField("Turkum", max_length=30, choices=CATEGORIES, default="Boshqa")
    amount = models.PositiveBigIntegerField("Summa (so'm)")
    month = models.CharField("Qaysi oy uchun", max_length=7, help_text=MONTH_HELP, db_index=True)
    date = models.DateField("Sana", default=timezone.localdate)
    teacher = models.CharField("O'qituvchi (oylik bo'lsa)", max_length=200, blank=True)

    class Meta:
        verbose_name = "Xarajat"
        verbose_name_plural = "Xarajatlar"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return self.title


# ---------------------------------------------------------------- marketing
class AdSpend(TimeStamped):
    source = models.CharField("Manba", max_length=50, choices=Lead.SOURCES, default="Instagram")
    amount = models.PositiveBigIntegerField("Summa (so'm)")
    month = models.CharField("Qaysi oy uchun", max_length=7, help_text=MONTH_HELP, db_index=True)
    note = models.CharField("Izoh", max_length=300, blank=True)

    class Meta:
        verbose_name = "Reklama xarajati"
        verbose_name_plural = "Reklama xarajatlari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source} · {self.month}"


class Promo(TimeStamped):
    TYPES = [("percent", "Foiz (%)"), ("sum", "Summa (so'm)")]
    code = models.CharField("Kod", max_length=50, unique=True)
    type = models.CharField("Turi", max_length=10, choices=TYPES, default="percent")
    value = models.PositiveIntegerField("Qiymati")
    note = models.CharField("Izoh", max_length=300, blank=True)
    active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Promokod"
        verbose_name_plural = "Promokodlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class Script(TimeStamped):
    title = models.CharField("Nomi", max_length=200)
    text = models.TextField("Matn")

    class Meta:
        verbose_name = "Qo'ng'iroq skripti"
        verbose_name_plural = "Qo'ng'iroq skriptlari"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


# ---------------------------------------------------------------- vazifalar, jurnal
class Task(TimeStamped):
    title = models.CharField("Vazifa", max_length=300)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="tasks", verbose_name="Kimga")
    due = models.DateField("Muddat", null=True, blank=True)
    note = models.TextField("Izoh", blank=True)
    done = models.BooleanField("Bajarildi", default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="created_tasks", editable=False)

    class Meta:
        verbose_name = "Vazifa"
        verbose_name_plural = "Vazifalar"
        ordering = ["done", "due", "-created_at"]

    def __str__(self):
        return self.title


class ActivityLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Xodim")
    text = models.CharField("Harakat", max_length=300)
    at = models.DateTimeField("Vaqt", auto_now_add=True)

    class Meta:
        verbose_name = "Jurnal yozuvi"
        verbose_name_plural = "Faoliyat jurnali"
        ordering = ["-at"]

    def __str__(self):
        return self.text


# ---------------------------------------------------------------- zaxira
class Backup(models.Model):
    """Ma'lumotlar bazasining siqilgan (gzip JSON) nusxasi."""
    KINDS = [("auto", "Avtomatik"), ("manual", "Qo'lda"), ("pre_restore", "Tiklashdan oldin")]
    created_at = models.DateTimeField("Sana", auto_now_add=True, db_index=True)
    kind = models.CharField("Turi", max_length=20, choices=KINDS, default="auto")
    size = models.PositiveIntegerField("Hajmi (bayt)", default=0)
    objects_count = models.PositiveIntegerField("Yozuvlar soni", default=0)
    summary = models.JSONField("Tarkibi", default=dict, blank=True)
    data = models.BinaryField("Ma'lumot", editable=False)
    sent = models.CharField("Tashqariga yuborildi", max_length=200, blank=True)

    class Meta:
        verbose_name = "Zaxira nusxa"
        verbose_name_plural = "Zaxira nusxalar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Zaxira {self.created_at:%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------- xavfsizlik
class LoginEvent(models.Model):
    """Har bir kirish urinishi: muvaffaqiyatli, xato yoki bloklangan."""
    KINDS = [("ok", "Kirdi"), ("fail", "Xato parol"), ("blocked", "Bloklangan"), ("2fa_fail", "Xato kod"),
             ("logout", "Chiqdi")]
    created_at = models.DateTimeField("Vaqt", auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="login_events", verbose_name="Foydalanuvchi")
    username = models.CharField("Login", max_length=150, db_index=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True, db_index=True)
    agent = models.CharField("Qurilma", max_length=300, blank=True)
    kind = models.CharField("Natija", max_length=10, choices=KINDS)

    class Meta:
        verbose_name = "Kirish urinishi"
        verbose_name_plural = "Kirishlar tarixi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username} · {self.get_kind_display()} · {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def ok(self):
        return self.kind == "ok"

    @property
    def device(self):
        a = self.agent.lower()
        os_ = ("Android" if "android" in a else "iPhone" if "iphone" in a else "iPad" if "ipad" in a else
               "Windows" if "windows" in a else "Mac" if "mac os" in a else "Linux" if "linux" in a else "")
        br = ("Edge" if "edg/" in a else "Opera" if "opr/" in a else "Chrome" if "chrome" in a else
              "Firefox" if "firefox" in a else "Safari" if "safari" in a else "")
        return " · ".join(x for x in (br, os_) if x) or (self.agent[:40] or "noma'lum")
