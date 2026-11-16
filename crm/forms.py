from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from . import services as sv
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
    rows = [["course", "teacher"], ["days", "time"], ["room", "capacity", "teacher_pct"],
            ["price", "branch"], ["pay_model", "pay_value"], ["start_date", "end_date"]]
    placeholders = {"name": "Ingliz tili A2 · kechki", "days": "Du-Chor-Ju", "time": "18:00-19:30"}

    class Meta:
        model = Group
        fields = ["name", "course", "teacher", "days", "time", "room", "capacity", "teacher_pct",
                  "price", "branch", "pay_model", "pay_value", "start_date", "end_date"]
        widgets = date_widgets("start_date", "end_date")


class MonthField(forms.ChoiceField):
    def __init__(self, *a, **kw):
        kw.setdefault("label", "Qaysi oy uchun")
        super().__init__(*a, **kw)


class PaymentForm(StyledModelForm):
    rows = [["amount", "month"], ["method", "date"]]
    month = MonthField()

    class Meta:
        model = Payment
        fields = ["student", "amount", "month", "method", "date"]
        widgets = date_widgets("date")

    def __init__(self, *a, month=None, **kw):
        super().__init__(*a, **kw)
        self.fields["student"].queryset = Student.objects.filter(status="faol").select_related("group").order_by("name")
        self.fields["student"].empty_label = None
        self.fields["student"].label_from_instance = lambda s: s.name + (f" · {s.group.name}" if s.group else "")
        self.fields["month"].choices = sv.month_options(month or self.initial.get("month"), back=2, fwd=1)
        self.fields["amount"].widget.attrs["min"] = "1"

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
        fields = ["name", "director", "phone", "address", "referral_bonus"]


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


class StaffCreateForm(StyledMixin, forms.Form):
    first_name = forms.CharField(label="Ism", max_length=150)
    last_name = forms.CharField(label="Familiya", max_length=150, required=False)
    username = forms.CharField(label="Login", max_length=150)
    password = forms.CharField(label="Parol", widget=forms.PasswordInput, min_length=8)
    role = forms.ChoiceField(label="Rol", choices=[c for c in Staff.ROLES])

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()

    def clean_username(self):
        u = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError("Bu login band")
        return u

    def clean_password(self):
        p = self.cleaned_data["password"]
        validate_password(p)
        return p

    def layout(self):
        return [[self["first_name"], self["last_name"]], [self["username"], self["password"]], [self["role"]]]


class ImportForm(StyledMixin, forms.Form):
    kind = forms.ChoiceField(label="Nimani import qilamiz", choices=[("students", "Talabalar"), ("leads", "Lidlar")])
    file = forms.FileField(label="Excel (.xlsx) yoki CSV fayl")

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()
        self.fields["file"].widget.attrs["accept"] = ".xlsx,.csv"

    def layout(self):
        return [[self["kind"]], [self["file"]]]
