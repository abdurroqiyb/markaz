from .backup import ensure_daily_backup


class DailyBackupMiddleware:
    """Tizimdan foydalanilganda kuniga bir marta avtomatik zaxira nusxa oladi.

    Render free tarifida cron yo'q, shuning uchun nusxa birinchi so'rovdan keyin olinadi.
    Tekshiruv jarayon ichida 10 daqiqada bir marta, javob yuborilgandan keyin bajariladi.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and request.method == "GET":
            ensure_daily_backup()
        return response
