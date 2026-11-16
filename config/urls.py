from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from crm import auth_views as av
from crm import parent, public, pwa
from crm import telegram as tg

urlpatterns = [
    path(f"{settings.ADMIN_URL}login/", av.admin_login_redirect),
    path(settings.ADMIN_URL, admin.site.urls),
    path("kirish/", av.LoginView.as_view(), name="login"),
    path("kirish/kod/", av.login_2fa, name="login_2fa"),
    path("chiqish/", auth_views.LogoutView.as_view(), name="logout"),
    path("xavfsizlik/", av.xavfsizlik, name="xavfsizlik"),
    path("xavfsizlik/2fa/yoqish/", av.twofa_enable, name="twofa_enable"),
    path("xavfsizlik/2fa/ochirish/", av.twofa_disable, name="twofa_disable"),
    path("xavfsizlik/2fa/<int:pk>/tozalash/", av.twofa_reset, name="twofa_reset"),
    path("xavfsizlik/blokdan-chiqarish/", av.unlock, name="unlock"),
    path("manifest.webmanifest", pwa.manifest, name="manifest"),
    path("sw.js", pwa.service_worker, name="sw"),
    path("oflayn/", pwa.offline, name="offline"),
    path("ariza/", public.ariza, name="ariza"),
    path("ota-ona/", parent.kirish, name="parent_login"),
    path("ota-ona/kabinet/", parent.kabinet, name="parent_home"),
    path("ota-ona/chiqish/", parent.chiqish, name="parent_logout"),
    path("tg/hook/<str:secret>/", tg.webhook, name="tg_hook"),
    path("", include("crm.urls")),
]
