"""PWA: manifest, service worker va oflayn sahifa (telefonga ilova kabi o'rnatish uchun)."""
from django.contrib.staticfiles import finders
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import cache_control

from .models import Center


@cache_control(max_age=3600)
def manifest(request):
    name = Center.get().name or "Markaz CRM"
    return JsonResponse({
        "name": f"{name} · Markaz CRM", "short_name": "Markaz CRM", "lang": "uz", "start_url": "/",
        "scope": "/", "display": "standalone", "background_color": "#0E1726", "theme_color": "#0E1726",
        "description": "O'quv markaz boshqaruvi",
        "icons": [
            {"src": static("crm/icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("crm/icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": static("crm/icons/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"},
        ],
    }, content_type="application/manifest+json")


@cache_control(max_age=0, no_cache=True)
def service_worker(request):
    path = finders.find("crm/js/sw.js")
    with open(path, encoding="utf-8") as fh:
        body = fh.read()
    resp = HttpResponse(body, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    return resp


def offline(request):
    return render(request, "crm/offline.html")
