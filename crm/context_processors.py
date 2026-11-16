from .models import Center
from .roles import NAV, ROLES, allowed, can_money, is_director, role_of


def crm(request):
    u = getattr(request, "user", None)
    if not u or not u.is_authenticated:
        return {}
    role = role_of(u)
    return {
        "nav": [{"key": k, "label": t, "icon": i} for k, t, i in NAV if allowed(u, k)],
        "center": Center.get(),
        "my_role": role,
        "my_role_label": ROLES.get(role, ""),
        "can_money": can_money(u),
        "is_director": is_director(u),
    }
