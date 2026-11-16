"""Filiallar.

- Filial biriktirilgan xodim (direktor emas) faqat o'z filialini ko'radi: guruhlar, talabalar, lidlar,
  to'lovlar, xarajatlar, kassa. Uni o'zgartira olmaydi.
- Direktor va filialsiz xodim yon paneldagi tanlovdan "Barcha filiallar" yoki bitta filialni tanlaydi.
- Filial bo'lmasa hech narsa o'zgarmaydi (bitta markaz).
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Branch
from .roles import director_required, is_director, role_of

SESSION = "filial"


def locked_branch(user):
    """Xodimga biriktirilgan filial (direktor uchun None)."""
    if not user.is_authenticated or role_of(user) == "direktor":
        return None
    staff = getattr(user, "staff", None)
    return staff.filial_id if staff else None


class BranchMiddleware:
    """request.user.active_branch_id: tanlangan filial (None = barchasi)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = getattr(request, "user", None)
        if u is not None and u.is_authenticated:
            lock = locked_branch(u)
            u.branch_locked = bool(lock)
            if lock:
                u.active_branch_id = lock
            else:
                b = request.session.get(SESSION)
                u.active_branch_id = b if isinstance(b, int) and Branch.objects.filter(pk=b).exists() else None
        return self.get_response(request)


def active(request):
    return getattr(request.user, "active_branch_id", None)


def form_kw(request):
    """ModelForm uchun: joriy filial va (cheklangan xodimda) maydonni yashirish."""
    return {"branch": active(request), "lock_branch": getattr(request.user, "branch_locked", False)}


def stamp(request, obj):
    """Cheklangan xodim yaratgan yozuvga o'z filialini qo'yadi; aks holda tanlangan filial (bo'sh bo'lsa)."""
    b = active(request)
    if b and (getattr(request.user, "branch_locked", False) or not getattr(obj, "filial_id", None)):
        obj.filial_id = b
    return obj


@require_POST
def switch(request):
    if not request.user.is_authenticated or getattr(request.user, "branch_locked", False):
        return redirect("home")
    v = request.POST.get("filial", "")
    if v.isdigit() and Branch.objects.filter(pk=int(v)).exists():
        request.session[SESSION] = int(v)
    else:
        request.session.pop(SESSION, None)
    nxt = request.POST.get("next") or ""
    return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else "home")


@director_required
def filiallar(request, pk=None):
    from .forms import BranchForm
    from .models import Group, Staff, Student
    from .views import log
    obj = get_object_or_404(Branch, pk=pk) if pk else None
    form = BranchForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        b = form.save()
        Group.objects.filter(filial=b).update(branch=b.name)
        action = "o'zgartirildi" if obj else "qo'shildi"
        log(request, f"Filial {action}: {b.name}")
        messages.success(request, "Saqlandi")
        return redirect("filiallar")
    rows = []
    for b in Branch.objects.all():
        rows.append({"b": b, "groups": Group.objects.filter(filial=b).count(),
                     "students": Student.objects.filter(filial=b, status="faol").count(),
                     "staff": Staff.objects.filter(filial=b, user__is_active=True).select_related("user")})
    return render(request, "crm/filiallar.html", {"section": "filiallar", "form": form, "obj": obj, "rows": rows,
                                                   "free_groups": Group.objects.filter(filial=None).count()})


@director_required
@require_POST
def filial_delete(request, pk):
    from .views import log
    b = get_object_or_404(Branch, pk=pk)
    log(request, f"Filial o'chirildi: {b.name}")
    b.delete()
    messages.success(request, "Filial o'chirildi. Uning guruh va talabalari umumiy bo'lib qoldi.")
    return redirect(reverse("filiallar"))


def can_switch(user):
    return user.is_authenticated and not getattr(user, "branch_locked", False) and \
        (is_director(user) or locked_branch(user) is None)
