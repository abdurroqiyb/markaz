from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from crm import auth_views as av

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
    path("", include("crm.urls")),
]
