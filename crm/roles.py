"""Rollar va bo'limlarga kirish huquqi.

Har bir xodim o'z login/paroli bilan kiradi. Qaysi bo'limlar ochiqligi:
  1) direktor (superuser yoki "direktor" roli) - hamma narsa;
  2) xodimga direktor alohida bo'limlar belgilagan bo'lsa - faqat o'shalar;
  3) aks holda rol bo'yicha standart ro'yxat (ACCESS).
O'qituvchi esa ma'lumot darajasida ham cheklanadi: faqat o'z guruhlari va talabalari.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

ROLES = {"direktor": "Direktor", "administrator": "Administrator",
         "oqituvchi": "O'qituvchi", "marketolog": "Marketolog"}

ACCESS = {
    "administrator": ["bugun", "dashboard", "lidlar", "talabalar", "guruhlar", "jadval", "davomat",
                      "tolovlar", "vazifalar", "qidiruv"],
    "oqituvchi": ["kabinet", "bugun", "jadval", "davomat", "talabalar", "vazifalar", "qidiruv"],
    "marketolog": ["bugun", "lidlar", "marketing", "vazifalar", "jadval", "qidiruv"],
}
# Faqat direktor: boshqa xodimga ham berib bo'lmaydi.
DIRECTOR_ONLY = ["xodimlar", "jurnal", "zaxira"]
# Standart holatda faqat direktor, lekin direktor xodimga alohida ochib berishi mumkin.
ADMIN_ONLY = ["xarajatlar", "hisobotlar"] + DIRECTOR_ONLY

NAV = [
    ("kabinet", "Kabinetim", "book"),
    ("bugun", "Bugun", "sun"), ("dashboard", "Asosiy", "home"), ("lidlar", "Lidlar", "funnel"),
    ("talabalar", "Talabalar", "cap"), ("guruhlar", "Guruhlar", "users"), ("jadval", "Jadval", "cal"),
    ("davomat", "Davomat", "check"), ("tolovlar", "To'lovlar", "wallet"), ("vazifalar", "Vazifalar", "task"),
    ("marketing", "Marketing", "mega"), ("hisobotlar", "Hisobotlar", "chart"),
    ("xarajatlar", "Xarajatlar", "receipt"), ("xodimlar", "Xodimlar", "badge"),
    ("jurnal", "Jurnal", "clock"), ("zaxira", "Zaxira", "shield"), ("qidiruv", "Qidiruv", "search"),
]
SECTION_LABELS = {k: t for k, t, _ in NAV}
# Direktor xodimga belgilab berishi mumkin bo'lgan bo'limlar.
GRANTABLE = [k for k, _, _ in NAV if k not in DIRECTOR_ONLY]


def role_of(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return "direktor"
    staff = getattr(user, "staff", None)
    return staff.role if staff else "oqituvchi"


def sections_of(user):
    """Foydalanuvchiga ochiq bo'limlar ro'yxati (NAV tartibida)."""
    r = role_of(user)
    if r is None:
        return []
    if r == "direktor":
        return [k for k, _, _ in NAV]
    staff = getattr(user, "staff", None)
    custom = [k for k in (staff.sections if staff else None) or [] if k in GRANTABLE]
    base = custom or ACCESS.get(r, [])
    return [k for k, _, _ in NAV if k in base and k not in DIRECTOR_ONLY]


def allowed(user, section):
    return section in sections_of(user)


def can_money(user):
    return allowed(user, "tolovlar")


def is_director(user):
    return role_of(user) == "direktor"


def is_teacher_scoped(user):
    """O'qituvchi faqat o'z guruhlari ma'lumotini ko'radi."""
    return role_of(user) == "oqituvchi"


def home_section(user):
    secs = sections_of(user)
    for k in ("dashboard", "kabinet", "bugun"):
        if k in secs:
            return k
    return secs[0] if secs else "parol"


def section_required(section):
    """login_required + rol bo'yicha bo'limga ruxsat."""
    def deco(view):
        @login_required
        @wraps(view)
        def inner(request, *a, **kw):
            if not allowed(request.user, section):
                messages.error(request, "Bu bo'limga kirish huquqingiz yo'q.")
                return redirect(home_section(request.user))
            return view(request, *a, **kw)
        return inner
    return deco


def money_required(view):
    @login_required
    @wraps(view)
    def inner(request, *a, **kw):
        if not can_money(request.user):
            messages.error(request, "Moliyaviy amallarga kirish huquqingiz yo'q.")
            return redirect(home_section(request.user))
        return view(request, *a, **kw)
    return inner


def director_required(view):
    @login_required
    @wraps(view)
    def inner(request, *a, **kw):
        if not is_director(request.user):
            messages.error(request, "Bu amal faqat direktor uchun.")
            return redirect(home_section(request.user))
        return view(request, *a, **kw)
    return inner
