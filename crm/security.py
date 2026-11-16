"""Xavfsizlik: login urinishlarini cheklash, kirishlar tarixi, ikki bosqichli kirish (TOTP), CSP.

- Bir login uchun LOCK_FAILS ta xato urinishdan keyin LOCK_MINUTES daqiqa blok.
  Bitta IP manzildan IP_FAILS ta xato bo'lsa, o'sha IP ham bloklanadi.
- TOTP: RFC 6238, Google Authenticator / Microsoft Authenticator bilan mos (6 raqam, 30 soniya).
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.utils import timezone

LOCK_FAILS = int(os.environ.get("LOGIN_LOCK_FAILS", "5"))
LOCK_MINUTES = int(os.environ.get("LOGIN_LOCK_MINUTES", "15"))
IP_FAILS = int(os.environ.get("LOGIN_IP_FAILS", "20"))


# ---------------------------------------------------------------- IP va qurilma
def client_ip(request):
    """Render (va boshqa proksi) ortida haqiqiy IP: X-Forwarded-For ning birinchi qiymati."""
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")
    return ip or None


def agent(request):
    return request.META.get("HTTP_USER_AGENT", "")[:300]


def record(request, kind, username="", user=None):
    from .models import LoginEvent
    try:
        LoginEvent.objects.create(user=user, username=(username or getattr(user, "username", ""))[:150],
                                  ip=client_ip(request) if request else None,
                                  agent=agent(request) if request else "", kind=kind)
    except Exception:  # tarix yozilmasa ham kirish ishlashi kerak
        pass


# ---------------------------------------------------------------- bloklash
def lock_status(username, ip):
    """(bloklanganmi, necha daqiqadan keyin ochiladi)."""
    from .models import LoginEvent
    since = timezone.now() - timedelta(minutes=LOCK_MINUTES)
    bad = LoginEvent.objects.filter(created_at__gte=since, kind__in=("fail", "2fa_fail"))
    by_user = list(bad.filter(username__iexact=username).order_by("-created_at")
                   .values_list("created_at", flat=True)[:LOCK_FAILS]) if username else []
    if len(by_user) >= LOCK_FAILS:
        # oxirgi muvaffaqiyatli kirishdan keyingi xatolargina hisoblanadi
        last_ok = LoginEvent.objects.filter(username__iexact=username, kind="ok").values_list(
            "created_at", flat=True).first()
        if not last_ok or by_user[-1] > last_ok:
            left = by_user[0] + timedelta(minutes=LOCK_MINUTES) - timezone.now()
            return True, max(1, round(left.total_seconds() / 60))
    if ip and bad.filter(ip=ip).count() >= IP_FAILS:
        last = bad.filter(ip=ip).order_by("-created_at").values_list("created_at", flat=True).first()
        left = last + timedelta(minutes=LOCK_MINUTES) - timezone.now()
        return True, max(1, round(left.total_seconds() / 60))
    return False, 0


@receiver(user_login_failed)
def _on_fail(sender, credentials, request=None, **kw):
    if request is not None and not getattr(request, "_login_blocked", False):
        record(request, "fail", username=credentials.get("username", ""))


@receiver(user_logged_in)
def _on_login(sender, request, user, **kw):
    if request is not None:
        record(request, "ok", user=user)


@receiver(user_logged_out)
def _on_logout(sender, request, user, **kw):
    if request is not None and user is not None:
        record(request, "logout", user=user)


# ---------------------------------------------------------------- TOTP (2FA)
def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret, counter):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return f"{(struct.unpack('>I', h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000:06d}"


def totp_now(secret, at=None):
    return _hotp(secret, int((at or time.time()) // 30))


def verify_totp(secret, code, window=1):
    code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if not secret or len(code) != 6:
        return False
    t = int(time.time() // 30)
    return any(hmac.compare_digest(_hotp(secret, t + w), code) for w in range(-window, window + 1))


def otpauth_uri(secret, username, issuer="Markaz CRM"):
    return (f"otpauth://totp/{quote(issuer)}:{quote(username)}?secret={secret}"
            f"&issuer={quote(issuer)}&digits=6&period=30")


def qr_svg(text):
    """QR kodni SVG ko'rinishida (segno o'rnatilgan bo'lsa)."""
    try:
        import segno
    except ImportError:
        return ""
    import io
    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="svg", scale=5, border=2, dark="#0F1A2B", light="#FFFFFF",
                                     xmldecl=False, svgns=True)
    return buf.getvalue().decode()


def needs_2fa(user):
    staff = getattr(user, "staff", None)
    return bool(staff and staff.totp_enabled and staff.totp_secret)


# ---------------------------------------------------------------- xavfsizlik sarlavhalari
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com data:",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "manifest-src 'self'",
    "worker-src 'self'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "base-uri 'self'",
    "object-src 'none'",
])


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(settings, "CSP_ENABLED", True):
            response.setdefault("Content-Security-Policy", CSP)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.user.is_authenticated if hasattr(request, "user") else False:
            response.setdefault("Cache-Control", "no-store, private")
        return response
