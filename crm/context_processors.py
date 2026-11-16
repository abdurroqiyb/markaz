from django.conf import settings

from .models import Center
from .roles import NAV, ROLES, allowed, can_money, is_director, is_teacher_scoped, role_of


def crm(request):
    u = getattr(request, "user", None)
    if not u or not u.is_authenticated:
        return {}
    role = role_of(u)
    director = is_director(u)
    return {
        "nav": [{"key": k, "label": t, "icon": i} for k, t, i in NAV
                if allowed(u, k) and not (director and k == "kabinet")],
        "center": Center.get(),
        "my_role": role,
        "my_role_label": ROLES.get(role, ""),
        "can_money": can_money(u),
        "is_director": director,
        "can_edit_students": not is_teacher_scoped(u),
        "db_warning": director and not getattr(settings, "DB_PERSISTENT", True),
    }
