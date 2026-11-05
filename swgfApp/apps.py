from django.apps import AppConfig


class SwgfappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'swgfApp'

    def ready(self):
        # Importar o arquivo faz o Django registrar os sinais declarados nele.
        from . import signals  # noqa: F401
