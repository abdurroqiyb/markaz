"""CSRF xatosini foydalanuvchiga tushunarli qilish.

Ko'p holatda sabab eskirgan sahifa: masalan login sahifasi bir tabda ochiq qolgan, boshqa tabda
kirilgan (Django kirishda CSRF tokenni yangilaydi), yoki brauzer cookie'larni tozalagan.
Bunday paytda 403 o'rniga sahifani yangi token bilan qayta ochamiz.
"""
import logging

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

log = logging.getLogger("crm.csrf")


def csrf_failure(request, reason=""):
    log.warning("CSRF rad etildi: %s %s (%s)", request.method, request.path, reason)
    user = getattr(request, "user", None)
    if request.path == reverse("login"):
        if user is not None and user.is_authenticated:
            return redirect(request.GET.get("next") or "home")
        messages.warning(request, "Sahifa eskirgan edi, yangilandi. Login va parolni qayta kiriting.")
        return redirect(request.get_full_path())
    back = request.META.get("HTTP_REFERER") or "/"
    if not back.startswith(("/", "https://", "http://")):
        back = "/"
    return render(request, "crm/csrf_failure.html", {"back": back}, status=403)
