from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crm"
    verbose_name = "Markaz CRM"

    def ready(self):
        from . import security  # noqa: F401  (signal'lar: kirishlar tarixi)
