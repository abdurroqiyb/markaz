from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Case, When
from django.contrib.auth.password_validation import validate_password

from . import services as sv
from .roles import GRANTABLE, SECTION_LABELS
from .models import (AdSpend, Center, Expense, Grade, Group, Lead, LeadCall, Payment,
                     Promo, Script, Staff, Student, Task)

User = get_user_model()


class StyledMixin:
    """Barcha maydonlarga HTML versiyadagi kabi placeholder/turlarni qo'yadi."""
    placeholders = {}

    def _style(self):
        for name, f in self.fields.items():
            w = f.widget
            if isinstance(w, forms.DateInput):
                w.input_type = "date"
                w.format = "%Y-%m-%d"
            if name in self.placeholders:
                w.attrs["placeholder"] = self.placeholders[name]
            if isinstance(w, forms.NumberInput):
                w.attrs.setdefault("min", "0")
                w.attrs.setdefault("inputmode", "numeric")
            if isinstance(w, forms.Textarea):
                w.attrs.setdefault("rows", 3)


class StyledModelForm(StyledMixin, forms.ModelForm):
    rows = []  # bir qatorga joylanadigan maydonlar guruhlari

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()

    def layout(self):
        """[[field], [field, field], ...] ko'rinishidagi joylashuv."""
        used, out = set(), []
        row_of = {}
        for r in self.rows:
            for n in r:
                row_of[n] = r
        for name in self.fields:
            if name in used:
                continue
            r = row_of.get(name, [name])
            out.append([self[n] for n in r if n in self.fields])
            used.update(r)
        return out


def date_widgets(*names):
    return {n: forms.DateInput() for n in names}


class LeadForm(StyledModelForm):
    rows = [["phone", "course"], ["source", "status"], ["next_contact", "trial_date"]]
    placeholders = {"phone": "+998 90 123 45 67", "course": "Masalan: Ingliz tili"}

    class Meta:
        model = Lead
        fields = ["name", "phone", "course", "source", "status", "next_contact", "trial_date",
                  "trial_result", "note"]
        widgets = date_widgets("next_contact", "trial_date")


class LeadCallForm(StyledModelForm):
    next_contact = forms.DateField(label="Keyingi aloqa sanasi", required=False, widget=forms.DateInput())
    placeholders = {"text": "Nima gaplashildi?"}

    class Meta:
        model = LeadCall
        fields = ["text"]
        labels = {"text": "Yangi yozuv"}


class StudentForm(StyledModelForm):
    rows = [["phone", "parent"], ["join_date", "status"], ["discount", "promo"], ["birth_date", "return_date"]]

    class Meta:
        model = Student
        fields = ["name", "phone", "parent", "group", "join_date", "status", "discount", "promo",
                  "birth_date", "return_date", "referrer"]
        widgets = date_widgets("join_date", "birth_date", "return_date")

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["group"].empty_label = "Guruhsiz"
        self.fields["group"].label_from_instance = lambda g: f"{g.name} · {sv.fmt(g.price)} so'm"
        self.fields["referrer"].empty_label = "Hech kim"
        qs = Student.objects.order_by("name")
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["referrer"].queryset = qs


class GroupForm(StyledModelForm):
    rows = [["course", "branch"], ["teacher_user", "teacher"], ["days", "time"], ["room", "capacity", "teacher_pct"],
            ["price"], ["pay_model", "pay_value"], ["start_date", "end_date"]]
    placeholders = {"name": "Ingliz tili A2 · kechki", "days": "Du-Chor-Ju", "time": "18:00-19:30"}

    class Meta:
        model = Group
        fields = ["name", "course", "branch", "teacher_user", "teacher", "days", "time", "room", "capacity",
                  "teacher_pct", "price", "pay_model", "pay_value", "start_date", "end_date"]
        widgets = date_widgets("start_date", "end_date")

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        f = self.fields["teacher_user"]
        f.queryset = User.objects.filter(is_active=True, is_superuser=False).order_by("first_name", "username")
        f.label_from_instance = lambda u: u.get_full_name() or u.username
        f.empty_label = "Tanlanmagan"
        self.fields["teacher"].help_text = "Hisob tanlansa, bo'sh qoldirsangiz ismi o'zi yoziladi"


class MonthField(forms.ChoiceField):
    def __init__(self, *a, **kw):
        kw.setdefault("label", "Qaysi oy uchun")
        super().__init__(*a, **kw)


class PaymentForm(StyledModelForm):
    rows = [["amount", "month"], ["months", "method"], ["date"]]
    month = MonthField()
    months = forms.IntegerField(label="Necha oy uchun (oldindan to'lov)", min_value=1, max_value=12, initial=1, required=False,
                                help_text="2 va undan ko'p bo'lsa summa shu oydan boshlab oylarga teng bo'linadi")

    class Meta:
        model = Payment
        fields = ["student", "amount", "month", "method", "date"]
        widgets = date_widgets("date")

    def __init__(self, *a, month=None, **kw):
        super().__init__(*a, **kw)
        # Faol talabalar va qarzi qolgan (muzlatilgan / tark etgan) talabalar ham to'lov qila oladi.
        self.fields["student"].queryset = Student.objects.exclude(status="navbat").select_related("group") \
            .order_by(Case(When(status="faol", then=0), default=1), "name")
        self.fields["student"].empty_label = None
        st = dict(Student.STATUSES)
        self.fields["student"].label_from_instance = lambda s: s.name + (f" · {s.group.name}" if s.group else "") + \
            ("" if s.status == "faol" else f" ({st[s.status].lower()})")
        self.fields["month"].choices = sv.month_options(month or self.initial.get("month"), back=2, fwd=1)
        self.fields["amount"].widget.attrs["min"] = "1"
        self.fields["months"].widget.attrs["max"] = "12"

    def clean_date(self):
        d = self.cleaned_data["date"]
        from .models import CashClose
        if d and CashClose.objects.filter(date=d).exists():
            raise forms.ValidationError("Bu kun kassasi yopilgan. Boshqa sana tanlang yoki direktor kassani qayta ochsin.")
        return d

    def clean_amount(self):
        a = self.cleaned_data["amount"]
        if a <= 0:
            raise forms.ValidationError("Summa 0 dan katta bo'lishi kerak")
        return a


class RefundForm(StyledMixin, forms.Form):
    amount = forms.IntegerField(label="Qaytariladigan summa (so'm)", min_value=1)
    note = forms.CharField(label="Sabab", required=False, widget=forms.Textarea)

    def __init__(self, *a, payment=None, **kw):
        super().__init__(*a, **kw)
        self.payment = payment
        self._style()

    def clean_amount(self):
        a = self.cleaned_data["amount"]
        if self.payment and a > self.payment.amount:
            raise forms.ValidationError("Summa to'lovdan oshmasligi kerak")
        return a

    def layout(self):
        return [[f] for f in self]


class ExpenseForm(StyledModelForm):
    rows = [["category", "amount"], ["month", "date"]]
    month = MonthField()
    placeholders = {"title": "Masalan: Ofis ijarasi"}

    class Meta:
        model = Expense
        fields = ["title", "category", "amount", "month", "date", "teacher"]
        widgets = date_widgets("date")

    def __init__(self, *a, month=None, **kw):
        super().__init__(*a, **kw)
        self.fields["month"].choices = sv.month_options(month or self.initial.get("month"))


class CenterForm(StyledModelForm):
    rows = [["phone", "address"]]

    class Meta:
        model = Center
        fields = ["name", "director", "phone", "address", "referral_bonus", "public_form", "parent_cabinet",
                  "prorate_first_month", "reminder_text"]


class PlanForm(StyledModelForm):
    class Meta:
        model = Center
        fields = ["plan_income", "plan_expense"]


class GradeForm(StyledModelForm):
    rows = [["score", "max_score"]]
    placeholders = {"title": "Masalan: Oylik test"}

    class Meta:
        model = Grade
        fields = ["title", "score", "max_score", "date"]
        widgets = date_widgets("date")

    def clean(self):
        c = super().clean()
        if c.get("score") is not None and c.get("max_score") and c["score"] > c["max_score"]:
            raise forms.ValidationError("Ball maksimaldan oshmasligi kerak")
        return c


class TaskForm(StyledModelForm):
    rows = [["assignee", "due"]]
    placeholders = {"title": "Masalan: Nigoraga qo'ng'iroq qilish"}

    class Meta:
        model = Task
        fields = ["title", "assignee", "due", "note"]
        widgets = date_widgets("due")

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["assignee"].queryset = User.objects.filter(is_active=True).order_by("first_name", "username")
        self.fields["assignee"].empty_label = "Hamma uchun"
        self.fields["assignee"].label_from_instance = lambda u: u.get_full_name() or u.username


class AdForm(StyledModelForm):
    rows = [["source", "amount"]]
    month = MonthField()
    placeholders = {"note": "Masalan: Instagram target, 3 ta reklama"}

    class Meta:
        model = AdSpend
        fields = ["source", "amount", "month", "note"]

    def __init__(self, *a, month=None, **kw):
        super().__init__(*a, **kw)
        self.fields["month"].choices = sv.month_options(month or self.initial.get("month"))


class PromoForm(StyledModelForm):
    rows = [["type", "value"]]
    placeholders = {"code": "YANGI20"}

    class Meta:
        model = Promo
        fields = ["code", "type", "value", "note"]

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        qs = Promo.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Bu kod allaqachon bor")
        return code


class ScriptForm(StyledModelForm):
    placeholders = {"title": "Birinchi qo'ng'iroq"}

    class Meta:
        model = Script
        fields = ["title", "text"]


TRANSLIT = {"o'": "o", "g'": "g", "o‘": "o", "g‘": "g", "sh": "sh", "ch": "ch", "'": "", "‘": "", "’": "", "`": "",
            "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
            "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
            "у": "u", "ф": "f", "х": "x", "ц": "s", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "",
            "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h"}


def make_login(first, last=""):
    """Ism-familiyadan bo'sh login: "Dilnoza Karimova" -> "dilnoza.karimova" (band bo'lsa raqam qo'shiladi)."""
    import re as _re
    def clean(x):
        x = (x or "").strip().lower()
        for k, v in TRANSLIT.items():
            x = x.replace(k, v)
        return _re.sub(r"[^a-z0-9]+", "", x)
    base = ".".join(p for p in (clean(first), clean(last)) if p) or "xodim"
    base, n, cand = base[:30], 1, base[:30]
    while User.objects.filter(username__iexact=cand).exists():
        n += 1
        cand = f"{base}{n}"
    return cand


def make_code():
    """Eslab qolish oson, lekin taxmin qilib bo'lmaydigan kirish kodi: masalan "kexa-4821"."""
    import secrets
    cons, vow = "bdfgkmnprstvxz", "aeiou"
    word = "".join(secrets.choice(cons) + secrets.choice(vow) for _ in range(2))
    return f"{word}-{secrets.randbelow(9000) + 1000}"


class StaffCreateForm(StyledMixin, forms.Form):
    first_name = forms.CharField(label="Ism", max_length=150)
    last_name = forms.CharField(label="Familiya", max_length=150, required=False)
    phone = forms.CharField(label="Telefon", max_length=50, required=False)
    role = forms.ChoiceField(label="Rol", choices=[c for c in Staff.ROLES], initial="oqituvchi")
    username = forms.CharField(label="Login (bo'sh qoldirsangiz ismdan yasaladi)", max_length=150, required=False)
    password = forms.CharField(label="Kod / parol (bo'sh qoldirsangiz avtomatik)", required=False,
                               widget=forms.TextInput(attrs={"autocomplete": "new-password"}))
    groups = forms.ModelMultipleChoiceField(label="Guruhlari (o'qituvchi uchun)", required=False,
                                            queryset=Group.objects.none(), widget=forms.CheckboxSelectMultiple)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["groups"].queryset = Group.objects.order_by("name")
        self.fields["groups"].label_from_instance = lambda g: g.name + (f" ({g.teacher})" if g.teacher else "")
        self._style()

    def clean_username(self):
        u = self.cleaned_data["username"].strip()
        if u and User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError("Bu login band")
        return u

    def clean(self):
        cd = super().clean()
        if self.errors:
            return cd
        if not cd.get("username"):
            cd["username"] = make_login(cd.get("first_name"), cd.get("last_name"))
        if cd.get("password"):
            try:
                validate_password(cd["password"], User(username=cd["username"], first_name=cd.get("first_name", "")))
            except forms.ValidationError as e:
                self.add_error("password", e)
        else:
            cd["password"] = make_code()
        return cd

    def layout(self):
        rows = [[self["first_name"], self["last_name"]], [self["phone"], self["role"]],
                [self["username"], self["password"]]]
        if self.fields["groups"].queryset.exists():
            rows.append([self["groups"]])
        return rows


class StaffEditForm(StyledMixin, forms.Form):
    first_name = forms.CharField(label="Ism", max_length=150)
    last_name = forms.CharField(label="Familiya", max_length=150, required=False)
    phone = forms.CharField(label="Telefon", max_length=50, required=False)
    role = forms.ChoiceField(label="Rol", choices=[c for c in Staff.ROLES])
    custom = forms.BooleanField(label="Bo'limlarni o'zim belgilayman (rol standartidan farqli)", required=False)
    sections = forms.MultipleChoiceField(label="Ochiq bo'limlar", required=False,
                                         widget=forms.CheckboxSelectMultiple,
                                         choices=[(k, SECTION_LABELS[k]) for k in GRANTABLE])

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()

    def clean(self):
        cd = super().clean()
        if cd.get("custom") and not cd.get("sections"):
            self.add_error("sections", "Kamida bitta bo'lim belgilang")
        return cd


class ResetPasswordForm(StyledMixin, forms.Form):
    password = forms.CharField(label="Yangi parol", widget=forms.PasswordInput, min_length=8)

    def __init__(self, *a, user=None, **kw):
        self.user = user
        super().__init__(*a, **kw)
        self._style()

    def clean_password(self):
        p = self.cleaned_data["password"]
        validate_password(p, self.user)
        return p


class RestoreForm(StyledMixin, forms.Form):
    file = forms.FileField(label="Zaxira fayli (.json.gz)", required=False)
    confirm = forms.CharField(label="Tasdiqlash uchun TIKLASH deb yozing", max_length=20)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()

    def clean_confirm(self):
        v = self.cleaned_data["confirm"].strip().upper()
        if v != "TIKLASH":
            raise forms.ValidationError("TIKLASH so'zini yozing")
        return v


class ImportForm(StyledMixin, forms.Form):
    kind = forms.ChoiceField(label="Nimani import qilamiz", choices=[("students", "Talabalar"), ("leads", "Lidlar")])
    file = forms.FileField(label="Excel (.xlsx) yoki CSV fayl")

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()
        self.fields["file"].widget.attrs["accept"] = ".xlsx,.csv"

    def layout(self):
        return [[self["kind"]], [self["file"]]]


class TransferForm(StyledMixin, forms.Form):
    group = forms.ModelChoiceField(label="Yangi guruh", queryset=Group.objects.none(), required=False,
                                   empty_label="Guruhsiz")
    date = forms.DateField(label="Qaysi sanadan", widget=forms.DateInput)
    keep_discount = forms.BooleanField(label="Chegirma saqlansin", required=False, initial=True)

    def __init__(self, *a, student=None, **kw):
        super().__init__(*a, **kw)
        qs = Group.objects.order_by("name")
        if student and student.group_id:
            qs = qs.exclude(pk=student.group_id)
        self.fields["group"].queryset = qs
        self.fields["group"].label_from_instance = lambda g: f"{g.name} · {sv.fmt(g.price)} so'm"
        self._style()

    def layout(self):
        return [[self["group"], self["date"]], [self["keep_discount"]]]
