from django.contrib.auth.models import AbstractUser

from django.db import models

# criando um usuario customizado

class Usuario(AbstractUser):
    """
    CustomUser do sistema SWGF.
    Herda tudo do User padrão do Django (username, password, email, etc.)
    e adiciona campos específicos do nosso sistema.
    
    """
    is_adm = models.BooleanField(default=False, verbose_name="É administrador")
    status = models.CharField(max_length=50, default='ativo', verbose_name="Status")
    
class Meta:
    verbose_name = "Usuário"
    verbose_name_plural = "Usuários"
    
def __str__(self):
        return f"{self.username} ({'ADM' if self.is_adm else 'Atendente'})"