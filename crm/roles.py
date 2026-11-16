"""Rollar va bo'limlarga kirish huquqi (HTML versiyadagi ACCESS jadvali)."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

ROLES = {"direktor": "Direktor", "administrator": "Administrator",
         "oqituvchi": "O'qituvchi", "marketolog": "Marketolog"}

ACCESS = {
    "administrator": ["bugun", "dashboard", "lidlar", "talabalar", "guruhlar", "jadval", "davomat",
                      "tolovlar", "vazifalar", "qidiruv"],
    "oqituvchi": ["bugun", "jadval", "davomat", "talabalar", "vazifalar", "qidiruv"],
    "marketolog": ["bugun", "lidlar", "marketing", "vazifalar", "jadval", "qidiruv"],
}
ADMIN_ONLY = ["xarajatlar", "jurnal", "xodimlar", "hisobotlar"]

NAV = [
    ("bugun", "Bugun", "sun"), ("dashboard", "Asosiy", "home"), ("lidlar", "Lidlar", "funnel"),
    ("talabalar", "Talabalar", "cap"), ("guruhlar", "Guruhlar", "users"), ("jadval", "Jadval", "cal"),
    ("davomat", "Davomat", "check"), ("tolovlar", "To'lovlar", "wallet"), ("vazifalar", "Vazifalar", "task"),
    ("marketing", "Marketing", "mega"), ("hisobotlar", "Hisobotlar", "chart"),
    ("xarajatlar", "Xarajatlar", "receipt"), ("xodimlar", "Xodimlar", "badge"),
    ("jurnal", "Jurnal", "clock"), ("qidiruv", "Qidiruv", "search"),
]


def role_of(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return "direktor"
    staff = getattr(user, "staff", None)
    return staff.role if staff else "oqituvchi"


def allowed(user, section):
    r = role_of(user)
    if r is None:
        return False
    if r == "direktor":
        return True
    if section in ADMIN_ONLY:
        return False
    return section in ACCESS.get(r, [])


def can_money(user):
    return role_of(user) in ("direktor", "administrator")


def is_director(user):
    return role_of(user) == "direktor"


def home_section(user):
    return "dashboard" if allowed(user, "dashboard") else "bugun"


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
            messages.error(request, "Moliyaviy amallar faqat direktor va administrator uchun.")
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
