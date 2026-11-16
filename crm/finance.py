"""Moliya tahlili: 12 oylik foyda, guruhlar va filiallar foydaliligi, talabalar ketishi va sabablari,
qarzlar yoshi, o'rtacha daromad (ARPU) va talabaning umrbod qiymati (LTV)."""
from collections import Counter, defaultdict

from django.shortcuts import render

from . import services as sv
from .models import LEAVE_REASONS, Branch
from .roles import section_required


def _active_on(d, s, day):
    return d.status_on(s, day) == "faol" and bool(s.join_date and s.join_date <= day)


@section_required("moliya")
def moliya(request):
    d = sv.Data(request.user)
    end = sv.valid_month(request.GET.get("m"))
    months = [sv.shift_month(end, n) for n in range(-11, 1)]
    reasons = dict(LEAVE_REASONS)

    # --- oylar bo'yicha
    left_rows = defaultdict(list)
    for s in d.students:
        tl = d.timeline(s)
        for i, (dt, st) in enumerate(tl):
            if st == "tark" and i > 0 and dt.year > 1:
                left_rows[sv.mkey(dt)].append(s)
    rows = []
    for m in months:
        last = min(sv.month_end(m), d.TODAY)
        first = sv.month_end(sv.shift_month(m, -1))
        inc, exp = d.income(m), d.month_exp(m)
        act = sum(1 for s in d.students if _active_on(d, s, last))
        start = sum(1 for s in d.students if _active_on(d, s, first))
        new = sum(1 for s in d.students if s.join_date and sv.mkey(s.join_date) == m)
        left = len(left_rows.get(m, []))
        plan = d.expected_for(m)
        rows.append({"k": m, "label": sv.mlabel(m), "short": sv.SHORT[int(m[5:]) - 1], "i": inc, "e": exp,
                     "net": inc - exp, "margin": sv.pct(inc - exp, inc) if inc else None, "act": act, "new": new,
                     "left": left, "churn": sv.pct(left, start) if start else 0, "arpu": round(inc / act) if act else 0,
                     "plan": plan, "collect": sv.pct(inc, plan) if plan else None})
    # ma'lumot boshlanmagan oylarni grafik va jadvaldan olib tashlaymiz
    while len(rows) > 3 and not (rows[0]["i"] or rows[0]["e"] or rows[0]["act"]):
        rows.pop(0)
    tot_i, tot_e = sum(r["i"] for r in rows), sum(r["e"] for r in rows)

    # --- ketish sabablari (12 oy)
    from .models import StatusChange
    rc, why = Counter(), {}
    ids = set(d.student_map)
    for sid, reason, dt in StatusChange.objects.filter(status="tark").order_by("date").values_list(
            "student_id", "reason", "date"):
        why[sid] = reason
        if sid in ids and sv.mkey(dt) in months:
            rc[reason or ""] += 1
    reason_bars = [{"label": reasons.get(k, "Sabab ko'rsatilmagan"), "v": v, "sub": f"{v} ta talaba"}
                   for k, v in rc.most_common()]
    last6 = rows[-6:]
    avg_churn = round(sum(r["churn"] for r in last6) / len(last6), 1)
    # o'rtacha qolish muddati (oy): 1 / oylik ketish ulushi
    life = round(100 / avg_churn, 1) if avg_churn else None
    arpu = round(sum(r["arpu"] for r in rows[-3:]) / 3) if rows else 0

    # --- guruhlar (tanlangan oy va 12 oy)
    grp = []
    for g in d.groups:
        i12 = sum(d.group_income(g, m) for m in months)
        s12 = sum(d.group_salary(g, m) for m in months)
        im, sm = d.group_income(g, end), d.group_salary(g, end)
        grp.append({"g": g, "n": d.active_in(g), "im": im, "sm": sm, "rm": im - sm, "i12": i12, "r12": i12 - s12,
                    "fill": sv.pct(d.active_in(g), g.capacity) if g.capacity else None})
    grp.sort(key=lambda r: -r["r12"])

    # --- filiallar (faqat "Barcha filiallar" ko'rinishida)
    br_rows = []
    if not d.branch and Branch.objects.exists():
        all_payments = d.payments
        for b in list(Branch.objects.all()) + [None]:
            sids = {s.id for s in d.students if s.filial_id == (b.pk if b else None)}
            inc = sum(p.amount for p in all_payments if p.month == end and p.student_id in sids)
            exp = sum(x.amount for x in d.expenses if x.month == end and x.filial_id == (b.pk if b else None)) + \
                sum(a.amount for a in d.ads if a.month == end and a.filial_id == (b.pk if b else None))
            n = sum(1 for s in d.students if s.id in sids and s.status == "faol")
            if b is None and not (inc or exp or n):
                continue
            br_rows.append({"name": b.name if b else "Umumiy (filialsiz)", "inc": inc, "exp": exp, "net": inc - exp,
                            "n": n})

    # --- qarzlar yoshi
    aging = {"1": [0, 0], "2": [0, 0], "3": [0, 0]}
    for s in d.students:
        od = [m for m in d.months_of(s) if d.debt_for(s, m) > 0]
        if not od:
            continue
        oldest = len(d.months_of(s)) - d.months_of(s).index(od[0])
        key = "1" if oldest <= 1 else "2" if oldest == 2 else "3"
        aging[key][0] += 1
        aging[key][1] += sum(d.debt_for(s, m) for m in od)

    # --- to'lov turlari (oy)
    meth = Counter()
    for p in d.payments:
        if p.month == end:
            meth[p.method] += p.amount

    cur = rows[-1]
    return render(request, "crm/moliya.html", {
        "section": "moliya", "m": end, "m_label": sv.mlabel(end), "m_prev": sv.shift_month(end, -1),
        "m_next": sv.shift_month(end, 1), "rows": rows, "cur": cur, "tot_i": tot_i, "tot_e": tot_e,
        "tot_net": tot_i - tot_e, "tot_margin": sv.pct(tot_i - tot_e, tot_i) if tot_i else None,
        "reason_bars": reason_bars, "left_total": sum(rc.values()), "avg_churn": avg_churn, "life": life,
        "arpu": arpu, "ltv": round(arpu * life) if life else None, "grp": grp,
        "grp_bars": [{"label": r["g"].name, "v": r["r12"], "sub": f"12 oy tushum {sv.compact(r['i12'])}"}
                     for r in grp if r["i12"]],
        "br_rows": br_rows, "aging": aging, "debt_total": sum(v[1] for v in aging.values()),
        "meth": [{"label": k, "v": v, "sub": f"{sv.pct(v, sum(meth.values()))}%"} for k, v in meth.most_common()],
        "left_now": [{"s": s, "g": d.group_of(s), "why": reasons.get(why.get(s.id), "")}
                     for s in left_rows.get(end, [])],
        "reasons": reasons,
    })
