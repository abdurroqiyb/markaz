"""Namunaviy ma'lumot (is_demo=True bilan belgilanadi, keyin o'chirish mumkin)."""
from django.core.management.base import BaseCommand
from django.db import transaction

from crm import services as sv
from crm.models import Group, Lead, Payment, Student


@transaction.atomic
def create_demo():
    now = sv.now_month()
    today = sv.today()
    g1 = Group.objects.create(name="Ingliz tili A2 · kechki", course="Ingliz tili", teacher="Dilnoza Karimova",
                              days="Du-Chor-Ju", time="18:00-19:30", room="2-xona", price=450000, capacity=10,
                              is_demo=True)
    g2 = Group.objects.create(name="Matematika 9-sinf", course="Matematika", teacher="Sardor Aliyev",
                              days="Se-Pay-Sha", time="15:00-16:30", room="1-xona", price=380000, capacity=12,
                              is_demo=True)
    join = sv.shift_month(now, -2) + "-05"
    names = [("Aziza Rahimova", g1), ("Javohir Tursunov", g1), ("Madina Ergasheva", g2),
             ("Bekzod Olimov", g2), ("Sevara Yusupova", g1)]
    studs = [Student.objects.create(name=n, phone=f"+998 90 000 00 0{i + 1}", group=g, join_date=join,
                                    status="faol", is_demo=True) for i, (n, g) in enumerate(names)]
    for s, amt, m in [(studs[0], 450000, "Naqd"), (studs[2], 380000, "Karta"), (studs[3], 200000, "Naqd")]:
        Payment.objects.create(student=s, amount=amt, month=now, method=m, date=today, is_demo=True)
    for n, c, src, st in [("Nigora Hasanova", "Ingliz tili", "Instagram", "yangi"),
                          ("Otabek Normatov", "Matematika", "Telegram", "aloqa"),
                          ("Zilola Qodirova", "Ingliz tili", "Tanish-bilishlar", "sinov"),
                          ("Rustam Ismoilov", "IELTS", "Reklama", "yangi")]:
        Lead.objects.create(name=n, phone="+998 91 000 00 00", course=c, source=src, status=st, is_demo=True)


class Command(BaseCommand):
    help = "Namunaviy guruh, talaba, to'lov va lidlarni qo'shadi."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="Namunalarni o'chirish")

    def handle(self, *args, **opts):
        if opts["delete"]:
            for m in (Payment, Student, Lead, Group):
                m.objects.filter(is_demo=True).delete()
            self.stdout.write(self.style.SUCCESS("Namunalar o'chirildi."))
            return
        create_demo()
        self.stdout.write(self.style.SUCCESS("Namunaviy ma'lumot qo'shildi."))
