from django.conf import settings

from .models import Center
from .roles import NAV, NAV_GROUP, ROLES, allowed, can_money, is_director, is_teacher_scoped, role_of


def crm(request):
    u = getattr(request, "user", None)
    if not u or not u.is_authenticated:
        return {}
    role = role_of(u)
    director = is_director(u)
    return {
        "nav": [{"key": k, "label": t, "icon": i, "group": NAV_GROUP.get(k, "")} for k, t, i in NAV
                if allowed(u, k) and not (director and k == "kabinet")],
        "center": Center.get(),
        "my_role": role,
        "my_role_label": ROLES.get(role, ""),
        "can_money": can_money(u),
        "is_director": director,
        "can_edit_students": not is_teacher_scoped(u),
        "db_warning": director and not getattr(settings, "DB_PERSISTENT", True),
        "bell": _badge(u),
        **_branches(u),
    }


def _badge(u):
    try:
        from .notify import badge
        return badge(u)
    except Exception:  # bildirishnoma xatosi sahifani buzmasin
        return 0


def _branches(u):
    from .branches import can_switch
    from .models import Branch
    bs = list(Branch.objects.all())
    if not bs:
        return {}
    act = getattr(u, "active_branch_id", None)
    return {"branches_all": bs, "branch_active": next((b for b in bs if b.pk == act), None),
            "branch_switch": can_switch(u)}
