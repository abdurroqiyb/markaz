import json

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .. import services as sv

register = template.Library()


@register.filter
def som(n):
    """1234567 -> '1 234 567' (HTML versiyadagi fmt)."""
    return sv.fmt(n)


@register.filter
def mlabel(k):
    try:
        return sv.mlabel(k)
    except Exception:
        return k


@register.simple_tag
def avatar(name, size=""):
    name = str(name or "?").strip()
    parts = name.split()
    ini = ((parts[0][:1] if parts else "?") + (parts[1][:1] if len(parts) > 1 else "")).upper()
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return format_html('<span class="av av{}" aria-hidden="true">{}</span>', h % 6, ini or "?")


@register.simple_tag
def ring(p, size, sw, color, label, track="", txt=""):
    """charts.js uchun halqa grafik joyi."""
    data = {"p": float(p or 0), "size": int(size), "sw": int(sw), "col": color, "label": str(label),
            "track": track, "txt": txt}
    return format_html('<span class="ringph" data-ring="{}"></span>', json.dumps(data))


@register.simple_tag
def spark(values, color):
    return format_html('<span class="sparkph" data-spark="{}" data-col="{}"></span>',
                       json.dumps([float(v or 0) for v in values]), color)


@register.simple_tag
def icon(name, cls="ic"):
    return format_html('<svg class="{}"><use href="#i-{}"/></svg>', cls, name)


@register.filter
def pctof(a, b):
    return sv.pct(a or 0, b or 0)


@register.filter
def get(d, k):
    try:
        return d.get(k)
    except AttributeError:
        return None


@register.simple_tag(takes_context=True)
def qs(context, **kw):
    """Joriy GET parametrlarini saqlab, berilganlarini almashtiradi."""
    req = context["request"]
    q = req.GET.copy()
    for k, v in kw.items():
        if v in (None, ""):
            q.pop(k, None)
        else:
            q[k] = v
    s = q.urlencode()
    return mark_safe("?" + s if s else "?")
