"""Kirish (login), ikki bosqichli tasdiqlash va "Xavfsizlik" sahifasi."""
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth import views as dj
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import security as sec
from .models import LoginEvent, Staff
from .roles import director_required, is_director

User = get_user_model()
PENDING = "_2fa_uid"
PENDING_BACKEND = "_2fa_backend"
PENDING_NEXT = "_2fa_next"
SETUP = "_2fa_setup_secret"


def _safe_next(request, nxt):
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return "/"


class LoginView(dj.LoginView):
    redirect_authenticated_user = True

    def post(self, request, *a, **kw):
        username = request.POST.get("username", "").strip()
        locked, mins = sec.lock_status(username, sec.client_ip(request))
        if locked:
            sec.record(request, "blocked", username=username)
            form = self.get_form()
            form.errors.clear()
            return self.render_to_response(self.get_context_data(
                form=form, lock_msg=f"Juda ko'p xato urinish. {mins} daqiqadan keyin qayta urinib ko'ring."))
        return super().post(request, *a, **kw)

    def form_valid(self, form):
        user = form.get_user()
        if sec.needs_2fa(user):
            self.request.session[PENDING] = user.pk
            self.request.session[PENDING_BACKEND] = user.backend
            self.request.session[PENDING_NEXT] = self.get_redirect_url() or ""
            return redirect("login_2fa")
        return super().form_valid(form)


def login_2fa(request):
    uid = request.session.get(PENDING)
    user = User.objects.filter(pk=uid, is_active=True).select_related("staff").first() if uid else None
    if not user:
        return redirect("login")
    error = ""
    if request.method == "POST":
        locked, mins = sec.lock_status(user.username, sec.client_ip(request))
        if locked:
            error = f"Juda ko'p xato urinish. {mins} daqiqadan keyin qayta urinib ko'ring."
            sec.record(request, "blocked", user=user)
        elif sec.verify_totp(user.staff.totp_secret, request.POST.get("code")):
            backend = request.session.get(PENDING_BACKEND)
            nxt = request.session.get(PENDING_NEXT, "")
            for k in (PENDING, PENDING_BACKEND, PENDING_NEXT):
                request.session.pop(k, None)
            auth_login(request, user, backend=backend)
            return redirect(_safe_next(request, nxt))
        else:
            sec.record(request, "2fa_fail", user=user)
            error = "Kod noto'g'ri. Ilovadagi eng so'nggi 6 xonali kodni kiriting."
    return render(request, "registration/login_2fa.html", {"error": error, "u": user})


def admin_login_redirect(request):
    """Admin panelning o'z login sahifasi 2FA va blokni chetlab o'tmasligi uchun."""
    from django.urls import reverse
    nxt = request.GET.get("next") or reverse("admin:index")
    return redirect(f"{reverse('login')}?next={nxt}")


# ---------------------------------------------------------------- Xavfsizlik sahifasi
@login_required
def xavfsizlik(request):
    u = request.user
    staff, _ = Staff.objects.get_or_create(user=u, defaults={"role": "direktor" if u.is_superuser else "oqituvchi"})
    setup = None
    if not staff.totp_enabled:
        secret = request.session.get(SETUP)
        if not secret:
            secret = request.session[SETUP] = sec.new_secret()
        uri = sec.otpauth_uri(secret, u.username)
        setup = {"secret": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)), "qr": sec.qr_svg(uri)}
    mine = LoginEvent.objects.filter(user=u)[:15]
    ctx = {"section": "xavfsizlik", "staff": staff, "setup": setup, "mine": mine,
           "lock_fails": sec.LOCK_FAILS, "lock_minutes": sec.LOCK_MINUTES}
    if is_director(u):
        flt = request.GET.get("f", "")
        qs = LoginEvent.objects.select_related("user")
        if flt == "bad":
            qs = qs.filter(kind__in=("fail", "blocked", "2fa_fail"))
        ctx.update({"all_events": qs[:150], "flt": flt,
                    "locked": _locked_users(),
                    "no2fa": [x for x in User.objects.filter(is_active=True).select_related("staff")
                              if is_director(x) and not sec.needs_2fa(x)]})
    return render(request, "crm/xavfsizlik.html", ctx)


def _locked_users():
    from datetime import timedelta
    from django.utils import timezone
    since = timezone.now() - timedelta(minutes=sec.LOCK_MINUTES)
    names = set(LoginEvent.objects.filter(created_at__gte=since, kind__in=("fail", "2fa_fail"))
                .values_list("username", flat=True))
    return [n for n in sorted(names) if sec.lock_status(n, None)[0]]


@login_required
@require_POST
def twofa_enable(request):
    secret = request.session.get(SETUP)
    if not secret or not sec.verify_totp(secret, request.POST.get("code")):
        messages.error(request, "Kod noto'g'ri. Ilovaga kalitni qo'shib, ko'rsatilgan 6 xonali kodni kiriting.")
        return redirect("xavfsizlik")
    staff = request.user.staff
    staff.totp_secret, staff.totp_enabled = secret, True
    staff.save(update_fields=["totp_secret", "totp_enabled"])
    request.session.pop(SETUP, None)
    messages.success(request, "Ikki bosqichli kirish yoqildi. Endi har kirishda ilovadagi kod so'raladi.")
    return redirect("xavfsizlik")


@login_required
@require_POST
def twofa_disable(request):
    staff = getattr(request.user, "staff", None)
    if not staff or not staff.totp_enabled:
        return redirect("xavfsizlik")
    if not sec.verify_totp(staff.totp_secret, request.POST.get("code")):
        messages.error(request, "Kod noto'g'ri. O'chirish uchun ilovadagi joriy kodni kiriting.")
        return redirect("xavfsizlik")
    staff.totp_secret, staff.totp_enabled = "", False
    staff.save(update_fields=["totp_secret", "totp_enabled"])
    messages.success(request, "Ikki bosqichli kirish o'chirildi.")
    return redirect("xavfsizlik")


@director_required
@require_POST
def twofa_reset(request, pk):
    """Telefonini yo'qotgan xodim uchun direktor 2FA ni o'chiradi."""
    staff = Staff.objects.filter(user_id=pk).first()
    if staff and staff.user_id != request.user.pk:
        staff.totp_secret, staff.totp_enabled = "", False
        staff.save(update_fields=["totp_secret", "totp_enabled"])
        messages.success(request, "Xodimning ikki bosqichli kirishi o'chirildi.")
    return redirect("staff_edit", pk=pk)


@director_required
@require_POST
def unlock(request):
    from datetime import timedelta
    from django.utils import timezone
    name = request.POST.get("username", "")
    since = timezone.now() - timedelta(minutes=sec.LOCK_MINUTES)
    LoginEvent.objects.filter(username__iexact=name, created_at__gte=since,
                              kind__in=("fail", "2fa_fail")).delete()
    messages.success(request, f"{name} blokdan chiqarildi.")
    return redirect("xavfsizlik")
