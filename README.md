# Markaz CRM (Django)

O'quv markazlar uchun CRM: lidlar voronkasi, talabalar, guruhlar, dars jadvali, davomat, baholar,
to'lovlar va qarzdorlik, xarajatlar va o'qituvchi oyligi, marketing (reklama, promokod, do'st olib kelish),
hisobotlar, vazifalar, xodimlar va rollar, faoliyat jurnali, Excel import/eksport.

Bitta HTML fayldagi ilova Django MVT asosida qayta yozilgan: ma'lumotlar endi brauzerda emas,
serverdagi ma'lumotlar bazasida (SQLite) saqlanadi, kirish login/parol bilan.

## Tuzilma

```
config/             Django sozlamalari (settings, urls, wsgi)
crm/models.py       17 ta model: Group, Lead, LeadCall, Student, Payment, Charge, Lesson, Attendance,
                    Grade, Expense, AdSpend, Promo, Script, Task, ActivityLog, Center, Staff
crm/services.py     Hisob-kitoblar: qarz, reja, oylik, ketish xavfi, jadval to'qnashuvi, marketing
crm/roles.py        Rollar: direktor, administrator, o'qituvchi, marketolog
crm/views.py        Barcha sahifalar va CRUD (server tomonida)
crm/forms.py        Formalar va tekshiruvlar
crm/templates/      base.html + har bir bo'lim uchun shablon
crm/static/crm/     app.css (dizayn), charts.js (grafikalar), app.js (UI qulayliklari)
crm/management/     ensure_superuser, seed_demo buyruqlari
build.sh, start.sh, render.yaml   Render deploy
```

## Lokal ishga tushirish

```bash
git clone https://github.com/abdurroqiyb/markaz.git
cd markaz
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # ixtiyoriy
python manage.py migrate
python manage.py createsuperuser   # direktor hisobi
python manage.py seed_demo         # ixtiyoriy: namunaviy ma'lumot
python manage.py runserver
```

Brauzerda http://127.0.0.1:8000 ni oching va yaratgan login/parolingiz bilan kiring.
Admin panel: http://127.0.0.1:8000/admin/

**SECRET_KEY**: `.env` da bo'lmasa, birinchi ishga tushishda avtomatik yaratilib `.env` fayliga yoziladi.
`.env` git'ga qo'shilmaydi.

Testlar: `python manage.py test crm`

## Render'ga joylash

1. Kodni GitHub'ga yuklang (bu repo).
2. https://dashboard.render.com da **New → Blueprint** ni tanlang va shu repo'ni ulang.
   Render `render.yaml` ni o'qib, `markaz-crm` web servisini yaratadi.
3. So'ralganda **DJANGO_SUPERUSER_PASSWORD** ni kiriting (kuchli parol). Login standart holatda `admin`.
4. **Apply** ni bosing. Build tugagach sayt `https://markaz-crm-xxxx.onrender.com` manzilida ochiladi.

Avtomatik bajariladiganlar:

- `SECRET_KEY` Render tomonidan yaratiladi (`generateValue: true`). U bo'lmasa ham ilova kalitni o'zi yaratib `.env` ga yozadi.
- `DEBUG` o'chiq, `ALLOWED_HOSTS` va `CSRF_TRUSTED_ORIGINS` ga Render manzili (`RENDER_EXTERNAL_HOSTNAME`) avtomatik qo'shiladi.
- Static fayllar WhiteNoise orqali beriladi (`collectstatic` build vaqtida).
- `build.sh` va `start.sh` migratsiya qiladi va `ensure_superuser` bilan direktor hisobini yaratadi.
- HTTPS, xavfsiz cookie va HSTS yoqilgan.

Render'siz (Blueprint ishlatmasdan) qo'lda yaratsangiz: **New → Web Service**, Runtime: Python,
Build Command: `./build.sh`, Start Command: `./start.sh`, va Environment bo'limiga
`SECRET_KEY` (Generate), `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD` qo'shing.

### Muhim: SQLite va Render free tarifi

Render free tarifida disk **vaqtinchalik**: har deploy yoki qayta ishga tushishda (va 15 daqiqa
faolsizlikdan keyin uxlab qolganda) `db.sqlite3` o'chib ketadi. Ya'ni kiritilgan ma'lumotlar yo'qoladi.
Sinab ko'rish uchun yetarli, lekin real ish uchun quyidagilardan birini qiling:

- **Doimiy disk** (Starter yoki undan yuqori tarif): `render.yaml` dagi `disk` blokini va
  `SQLITE_PATH=/var/data/db.sqlite3` qatorini oching. Ma'lumotlar diskda saqlanadi.
- Yoki keyinchalik PostgreSQL'ga o'tish (sozlamalarda faqat `DATABASES` o'zgaradi).

Muntazam zaxira uchun: **Asosiy → Excelga yuklab olish** barcha ma'lumotlarni .xlsx qilib beradi.

## Muhit o'zgaruvchilari

| Nomi | Vazifasi |
| --- | --- |
| `SECRET_KEY` | Django maxfiy kaliti (yo'q bo'lsa avtomatik yaratiladi) |
| `DEBUG` | `True`/`False`. Render'da standart `False` |
| `ALLOWED_HOSTS` | Vergul bilan: `crm.example.uz,localhost` |
| `CSRF_TRUSTED_ORIGINS` | O'z domeningiz bo'lsa: `https://crm.example.uz` |
| `SQLITE_PATH` | Ma'lumotlar bazasi fayli yo'li (doimiy disk uchun) |
| `TIME_ZONE` | Standart `Asia/Tashkent` |
| `DJANGO_SUPERUSER_USERNAME` / `_PASSWORD` / `_EMAIL` | Deployda direktor hisobini yaratish |
| `DJANGO_SUPERUSER_RESET_PASSWORD` | `true` bo'lsa mavjud direktor paroli yangilanadi |

## Rollar

- **Direktor** (superuser): hamma bo'lim, shu jumladan xarajat, hisobot, jurnal, xodimlar.
- **Administrator**: lid, talaba, guruh, jadval, davomat, to'lov, vazifa.
- **O'qituvchi**: jadval, davomat, baho, talabalar (pul ko'rinmaydi), vazifa.
- **Marketolog**: lid, marketing, vazifa, jadval.

Xodimlarni **Xodimlar** bo'limida login/parol bilan qo'shasiz va rol berasiz. Rollar server tomonida
tekshiriladi (HTML versiyadagidek faqat menyuni yashirish emas).

## HTML versiyaga nisbatan nima kuchaydi

- Ma'lumotlar serverda, haqiqiy login/parol va rol bo'yicha server tomonidagi cheklov.
- Har bir forma server tomonida tekshiriladi (CSRF himoyasi, majburiy maydonlar, summa chegaralari).
- Excel import/eksport serverda (openpyxl), brauzer kutubxonasiga bog'liq emas.
- Admin panel orqali barcha jadvallarni ko'rish va tahrirlash.
- Faoliyat jurnali har bir o'zgarishni foydalanuvchi bilan yozib boradi.
- Avtomatik testlar (`python manage.py test crm`).
