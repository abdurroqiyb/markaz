# Markaz CRM (Django)

O'quv markazlar uchun CRM: lidlar voronkasi, talabalar, guruhlar, dars jadvali, davomat, baholar,
to'lovlar va qarzdorlik, xarajatlar va o'qituvchi oyligi, marketing (reklama, promokod, do'st olib kelish),
hisobotlar, vazifalar, xodimlar va rollar, faoliyat jurnali, Excel import/eksport.

Bitta HTML fayldagi ilova Django MVT asosida qayta yozilgan: ma'lumotlar endi brauzerda emas,
serverdagi ma'lumotlar bazasida saqlanadi (standart SQLite, `DATABASE_URL` berilsa PostgreSQL), kirish login/parol bilan.

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
Admin panel: http://127.0.0.1:8000/boshqaruv-panel/ (`ADMIN_URL`)

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

### Ma'lumotlar saqlanib qolishi uchun: bepul Neon PostgreSQL (tavsiya)

Render free tarifida disk **vaqtinchalik**: har deploy yoki qayta ishga tushishda (va 15 daqiqa
faolsizlikdan keyin uxlab qolganda) SQLite fayli o'chib ketadi. Buning bepul yechimi: ma'lumotlar
bazasini tashqi bepul PostgreSQL'da (Neon) saqlash. Ilova `DATABASE_URL` berilsa avtomatik
PostgreSQL'ga o'tadi, berilmasa SQLite ishlatadi.

1. https://neon.tech saytida ro'yxatdan o'ting (Google yoki GitHub bilan, karta so'ramaydi).
2. **Create project** bosing. Nomi: `markaz`, Region: **Europe (Frankfurt)** (Render'ga yaqin).
3. Ochilgan oynada **Connection string** ni nusxalang. U shunday ko'rinadi:
   `postgresql://neondb_owner:XXXX@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`
4. Render'da servisingizni oching → **Environment** → **Add Environment Variable**:
   Key: `DATABASE_URL`, Value: nusxalangan satr → **Save Changes**.
5. Render avtomatik qayta deploy qiladi. `start.sh` jadvallarni yaratadi va direktor hisobini qo'shadi.

Shundan keyin ma'lumotlar Neon'da saqlanadi va deploy/qayta ishga tushishda yo'qolmaydi.
Neon bepul tarifi kichik o'quv markaz uchun yetarli (0.5 GB joy).

Boshqa variant: pullik Render tarifida doimiy disk ulash. Buning uchun `render.yaml` dagi `disk`
blokini va `SQLITE_PATH=/var/data/db.sqlite3` qatorini izohdan chiqaring.

`DATABASE_URL` berilmagan bo'lsa, direktor har sahifada qizil ogohlantirishni ko'radi.

## Zaxira nusxa

- Tizimdan foydalanilganda **kuniga bir marta avtomatik** zaxira olinadi (gzip JSON, bazada, oxirgi 30 tasi saqlanadi).
- **Zaxira** bo'limi (faqat direktor): nusxalar ro'yxati, "Hozir zaxira olish", faylni yuklab olish,
  nusxadan yoki fayldan tiklash (TIKLASH so'zi bilan tasdiqlanadi, avval joriy holat ham zaxiralanadi).
- Buyruqlar: `python manage.py backup_db --file zaxira.json.gz`, `python manage.py restore_db zaxira.json.gz --yes`.
- Bazaning o'zi yo'qolsa ham qolishi uchun vaqti-vaqti bilan faylni kompyuterga yuklab oling.
  Excel eksport (**Asosiy → Excelga yuklab olish**) ham mavjud.

## Xavfsizlik

- **Login cheklovi**: bir login uchun 5 ta xato urinishdan keyin 15 daqiqa blok (bitta IP dan 20 ta xato bo'lsa IP ham bloklanadi).
  Direktor **Xavfsizlik** bo'limida blokni darhol ochishi mumkin.
- **Ikki bosqichli kirish (2FA)**: har bir xodim **Xavfsizlik** bo'limida Google/Microsoft Authenticator bilan yoqadi.
  Telefonini yo'qotgan xodimning 2FA sini direktor xodim sahifasida o'chiradi.
- **Kirishlar tarixi**: kim, qachon, qaysi qurilma/IP dan kirdi va xato urinishlar.
- **Avtomatik chiqish**: 2 soat faolsizlikdan keyin (`SESSION_IDLE_MINUTES`).
- **Admin panel** manzili `/admin/` emas, `ADMIN_URL` (standart `boshqaruv-panel/`); admin login ham 2FA va blokdan o'tadi.
- **Sarlavhalar**: CSP, HSTS (1 yil), Permissions-Policy, autentifikatsiyalangan sahifalar keshlanmaydi.
- **Zaxirani tashqariga yuborish**: Telegram (`BACKUP_TELEGRAM_BOT_TOKEN`, `BACKUP_TELEGRAM_CHAT_ID`) yoki
  e-pochta (`EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `BACKUP_EMAIL_TO`).

## Qo'shimcha imkoniyatlar

- **Ochiq ariza formasi**: `/ariza/` (kirishsiz). Saytga/Instagram'ga qo'yiladi, ariza "Sayt (ariza)" manbali lid bo'ladi.
  Markaz ma'lumotlarida yoqish/o'chirish mumkin. Spamdan himoya: yashirin maydon va IP bo'yicha cheklov.
- **Qarz eslatmasi**: har qarzdor yonida "Eslatma" (nusxalash) va "TG" (Telegram orqali yuborish). Matn shabloni markaz ma'lumotlarida.
- **Imtihonlar**: guruh bo'yicha ballarni bir yo'la kiritish, reyting va o'sish grafigi (o'qituvchi faqat o'z guruhlari).
- **Oylik hisobot PDF**: Hisobotlar → "PDF / chop etish" (brauzerda "PDF sifatida saqlash").
- **Xodim qo'shish**: Xodimlar → faqat ism va rolni yozing. Login (`dilnoza.karimova`) va kod (`kexa-4821`)
  avtomatik yaratiladi, o'qituvchiga guruhlari shu yerda biriktiriladi. Kirish ma'lumotlari bir marta ko'rsatiladi
  (nusxalash / Telegram / chop etish). Yo'qolsa: "Yangi kod". Login katta-kichik harfga qaramaydi.
- **Telegram bot** (`TELEGRAM_BOT_TOKEN`): darsga kelmasa, to'lov qabul qilinsa ota-onaga xabar; To'lovlar sahifasidan
  qarz eslatmasi; xodimlarga har kuni ertalab eslatma. Sozlash: CRM → Telegram bot.
- **Ota-ona kabineti**: `/ota-ona/` (telefon + farzandning 6 xonali kodi). Kod talaba profilida.
- **Oldindan to'lov**: to'lov formasida "Necha oy uchun". **Qisman birinchi oy**: markaz ma'lumotlarida yoqiladi.
- **Guruhga o'tkazish**: talaba profilida; eski oylar eski guruh narxida hisoblanadi, tarix profilda ko'rinadi.
- **Kunlik kassa**: To'lovlar → Kassa. Yopilgan kunga to'lov qo'shib bo'lmaydi; farq bo'lsa direktorga xabar.
- **Bildirishnomalar**: chap pastdagi qo'ng'iroqcha (muddati o'tgan vazifa, bugungi qo'ng'iroqlar, yangi ariza va h.k.).
- **Namuna**: Zaxira → "Namuna yuklash" (6 oylik to'liq markaz va har rol uchun demo login), keyin bir tugma bilan
  o'chiriladi. Buyruq: `python manage.py seed_demo` / `--delete`.
- **Haftalik kalendar**: Jadval → Kalendar. **Tungi rejim** tugmasi chap pastda. **PWA**: telefonda "Bosh ekranga qo'shish".

## Muhit o'zgaruvchilari

| Nomi | Vazifasi |
| --- | --- |
| `SECRET_KEY` | Django maxfiy kaliti (yo'q bo'lsa avtomatik yaratiladi) |
| `DEBUG` | `True`/`False`. Render'da standart `False` |
| `ALLOWED_HOSTS` | Vergul bilan: `crm.example.uz,localhost` |
| `CSRF_TRUSTED_ORIGINS` | O'z domeningiz bo'lsa: `https://crm.example.uz` |
| `DATABASE_URL` | PostgreSQL ulanish satri (masalan Neon). Bo'lsa SQLite o'rniga ishlatiladi |
| `SQLITE_PATH` | Ma'lumotlar bazasi fayli yo'li (doimiy disk uchun) |
| `TIME_ZONE` | Standart `Asia/Tashkent` |
| `DJANGO_SUPERUSER_USERNAME` / `_PASSWORD` / `_EMAIL` | Deployda direktor hisobini yaratish |
| `DJANGO_SUPERUSER_RESET_PASSWORD` | `true` bo'lsa mavjud direktor paroli yangilanadi |
| `ADMIN_URL` | Admin panel manzili (standart `boshqaruv-panel`) |
| `SESSION_IDLE_MINUTES` | Faolsizlikdan keyin chiqish, daqiqa (standart 120) |
| `LOGIN_LOCK_FAILS` / `LOGIN_LOCK_MINUTES` / `LOGIN_IP_FAILS` | Login cheklovi (5 / 15 / 20) |
| `BACKUP_TELEGRAM_BOT_TOKEN` / `BACKUP_TELEGRAM_CHAT_ID` | Kunlik zaxirani Telegramga yuborish |
| `TELEGRAM_BOT_TOKEN` | Ota-ona va xodimlar uchun Telegram bot (bo'lmasa zaxira boti ishlatiladi) |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `BACKUP_EMAIL_TO` | Zaxirani e-pochtaga yuborish |

## Rollar

- **Direktor** (superuser): hamma bo'lim, shu jumladan xarajat, hisobot, jurnal, xodimlar.
- **Administrator**: lid, talaba, guruh, jadval, davomat, to'lov, vazifa.
- **O'qituvchi**: o'z kabineti (guruhlari, bugungi darslar, davomat, o'z maoshi), faqat o'z guruhlari
  bo'yicha jadval, davomat, talabalar va baho (talaba qo'sha/o'chira olmaydi, pul ko'rinmaydi), vazifa.
  Guruh sozlamasida "O'qituvchi hisobi"ni tanlang (yoki guruhdagi o'qituvchi ismi xodimning to'liq ismi bilan bir xil bo'lsin).
- **Marketolog**: lid, marketing, vazifa, jadval.

Xodimlarni **Xodimlar** bo'limida login/parol bilan qo'shasiz va rol berasiz. "Huquq va parol" sahifasida
xodimga bo'limlarni alohida belgilash, parolini yangilash mumkin; bloklangan xodimni qayta tiklash mumkin.
Har bir xodim o'z parolini chap pastdagi **Parol** tugmasi orqali almashtiradi. Xodimlar, jurnal va zaxira faqat direktorga. Rollar server tomonida
tekshiriladi (HTML versiyadagidek faqat menyuni yashirish emas).

## HTML versiyaga nisbatan nima kuchaydi

- Ma'lumotlar serverda, haqiqiy login/parol va rol bo'yicha server tomonidagi cheklov.
- Har bir forma server tomonida tekshiriladi (CSRF himoyasi, majburiy maydonlar, summa chegaralari).
- Excel import/eksport serverda (openpyxl), brauzer kutubxonasiga bog'liq emas.
- Admin panel orqali barcha jadvallarni ko'rish va tahrirlash.
- Faoliyat jurnali har bir o'zgarishni foydalanuvchi bilan yozib boradi.
- Avtomatik testlar (`python manage.py test crm`).
